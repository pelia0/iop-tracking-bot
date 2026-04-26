from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from core.config import (
    DEEP_CHECK_INTERVAL_HOURS,
    DEEP_CHECK_LIMIT_PER_CYCLE,
    MAX_PAGES_PER_SCAN,
    MINUTES_BETWEEN_FULL_CHECK,
    NO_DATE,
    NO_IMAGE,
)
from core.health import health
from core.models import TrackedGame
from core.notifications import NotificationSender
from core.parser import parser_instance
from core.storage import async_load_settings, async_save_settings, async_load_tracked_games, async_save_tracked_games
from core.utils import normalize_game_url, parse_isoformat_lenient


class IOPUpdater:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.last_deep_check_time: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def check_for_updates(self, bot: commands.Bot, force: bool = False) -> None:
        settings = await async_load_settings()
        tracked_games = await async_load_tracked_games()
        if not tracked_games:
            logging.info("Tracking list is empty. Check completed.")
            health.record_success()
            return

        now = datetime.now()
        last_check_str = settings.get("last_full_check", "1970-01-01T00:00:00")
        last_check_dt = parse_isoformat_lenient(last_check_str)
        elapsed_minutes = (now - last_check_dt).total_seconds() / 60

        games_on_page: dict[str, dict[str, str]] = {}
        should_scan_main = force or (elapsed_minutes >= MINUTES_BETWEEN_FULL_CHECK)

        if should_scan_main:
            if force:
                logging.info("====================================================")
                logging.info("🔥 FORCED check triggered manually via command!")
            else:
                logging.info("====================================================")
                logging.info(f"🚀 Starting simple check (last full check: {last_check_dt.strftime('%d.%m.%Y %H:%M')})...")
            try:
                games_on_page, pages_processed = await parser_instance.async_parse_games_on_page(
                    pages_to_check=MAX_PAGES_PER_SCAN,
                    stop_date=last_check_dt,
                )

                if pages_processed > 1:
                    logging.info("--- Re-checking Page 1 for race-condition updates ---")
                    extra_games, _ = await parser_instance.async_parse_games_on_page(
                        pages_to_check=1,
                    )
                    games_on_page.update(extra_games)

                settings["last_full_check"] = now.isoformat()
                await async_save_settings(settings)
                health.record_success()
            except Exception as error:
                logging.error(f"Error during update check: {error}")
                if health.record_failure():
                    logging.critical("⚠️ CRITICAL ERROR: PARSER IS DOWN! 3 consecutive failures.")
        else:
            wait_min = int(MINUTES_BETWEEN_FULL_CHECK - elapsed_minutes)
            logging.info(f"⏭️ Skipping simple check. Last full scan was {int(elapsed_minutes)}m ago (next in ~{wait_min}m).")
            logging.info("🔍 Proceeding directly to verify games that need deep check...")

        if games_on_page:
            logging.info(f"✅ Simple check finished: Found {len(games_on_page)} actual games on processed pages.")
        elif should_scan_main:
            logging.warning("⚠️ Simple check finished with no games found.")

        channel = bot.get_channel(self.channel_id)
        if channel is None:
            logging.error(f"Failed to find channel with ID: {self.channel_id}")
            return

        await self._update_tracked_games(tracked_games, games_on_page, channel)
        deep_check_urls = self._find_deep_check_candidates(tracked_games, now)
        await self._perform_deep_checks(deep_check_urls, tracked_games, channel)

        logging.info("🏁 Full scan cycle complete.")
        logging.info("====================================================")

        try:
            now_str = datetime.now().strftime("%H:%M")
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(tracked_games)} games | upd. {now_str}",
                ),
            )
        except Exception as e:
            logging.warning(f"Failed to update bot presence: {e}")

    # ------------------------------------------------------------------
    # Private — tracked games update
    # ------------------------------------------------------------------

    async def _update_tracked_games(
        self,
        tracked_games: dict[str, TrackedGame],
        games_on_page: dict[str, dict[str, str]],
        channel: discord.TextChannel,
    ) -> None:
        now = datetime.now().isoformat()

        for raw_url, current_info in games_on_page.items():
            url = normalize_game_url(raw_url)
            if url not in tracked_games:
                continue

            tracked_game = tracked_games[url]
            tracked_game.last_scanned = now
            current_date = current_info.get("date", NO_DATE)
            last_known_date = tracked_game.date

            if current_date == last_known_date:
                continue

            logging.info(
                f"✨ UPDATE! Game '{current_info['title']}' changed date from '{last_known_date}' to '{current_date}'"
            )
            description = "New date found!" if last_known_date == NO_DATE else "Update date has been changed!"
            await self._send_game_update(
                channel=channel,
                title=current_info["title"],
                url=url,
                image_url=current_info.get("image_url", NO_IMAGE),
                old_date=last_known_date,
                new_date=current_date,
                description=description,
            )
            tracked_game.title = current_info["title"]
            tracked_game.date = current_date
            tracked_game.image_url = current_info.get("image_url", NO_IMAGE)
            await async_save_tracked_games(tracked_games)

    # ------------------------------------------------------------------
    # Private — deep check scheduling
    # ------------------------------------------------------------------

    def _find_deep_check_candidates(self, tracked_games: dict[str, TrackedGame], now: datetime) -> list[str]:
        candidates: list[str] = []
        for url, game in tracked_games.items():
            if self._needs_deep_check(game, now):
                last_check = self.last_deep_check_time.get(url)
                if last_check is None or (now - last_check) >= timedelta(hours=DEEP_CHECK_INTERVAL_HOURS):
                    candidates.append(url)
                    if len(candidates) >= DEEP_CHECK_LIMIT_PER_CYCLE:
                        break
        return candidates

    def _needs_deep_check(self, game: TrackedGame, now: datetime) -> bool:
        if game.date == NO_DATE:
            return True

        if not game.last_scanned:
            return True

        try:
            last_scanned_dt = datetime.fromisoformat(game.last_scanned)
            return (now - last_scanned_dt).days >= 7
        except ValueError:
            return True

    async def _perform_deep_checks(
        self,
        urls: list[str],
        tracked_games: dict[str, TrackedGame],
        channel: discord.TextChannel,
    ) -> None:
        for index, raw_url in enumerate(urls):
            delay_seconds = random.randint(30, 60) if index == 0 else random.randint(60, 120)
            logging.info(f"⏳ Waiting {delay_seconds}s before deep checking next game...")
            await asyncio.sleep(delay_seconds)

            url = normalize_game_url(raw_url)
            logging.info(f"🔍 Starting deep check for game: {url}")
            try:
                single_info = await parser_instance.async_parse_single_game_page(url)
                if not single_info:
                    logging.warning(f"Deep check returned empty info for {url}")
                    continue

                self.last_deep_check_time[url] = datetime.now()
                tracked_game = tracked_games.get(url)
                if not tracked_game:
                    tracked_game = TrackedGame.from_raw(single_info)
                    tracked_games[url] = tracked_game

                old_date = tracked_game.date
                new_date = single_info.get("date", NO_DATE)
                tracked_game.last_scanned = datetime.now().isoformat()
                tracked_game.title = single_info.get("title", tracked_game.title)

                if new_date != NO_DATE:
                    tracked_game.date = new_date

                if new_date != NO_DATE and new_date != old_date:
                    await self._send_game_update(
                        channel=channel,
                        title=tracked_game.title,
                        url=url,
                        image_url=tracked_game.image_url,
                        old_date=old_date,
                        new_date=new_date,
                        description="Backfill update found.",
                    )
                    logging.info(f"✨ Date changed during backfill for {tracked_game.title}!")

                # Always save after deep check to persist last_scanned/title updates
                await async_save_tracked_games(tracked_games)

                logging.info(f"✅ Game checked, recorded in JSON: {url}")
            except Exception as e:
                logging.error(f"Deep check failed for {url}: {e}")

    # ------------------------------------------------------------------
    # Private — notification helper (DRY)
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_game_update(
        channel: discord.TextChannel,
        title: str,
        url: str,
        image_url: str,
        old_date: str,
        new_date: str,
        description: str,
    ) -> None:
        """Wrapper around NotificationSender — centralises the call."""
        await NotificationSender.send_update_notification(
            channel=channel,
            title=title,
            url=url,
            image_url=image_url,
            old_date=old_date,
            new_date=new_date,
            description=description,
        )
