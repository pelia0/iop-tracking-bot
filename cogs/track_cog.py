import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from core.config import NO_DATE, NO_IMAGE
from core.models import TrackedGame
from core.parser import parser_instance
from core.storage import async_load_tracked_games, async_save_tracked_games
from core.utils import normalize_game_url


class TrackCog(commands.Cog):
    """Cog for tracking and untracking games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='track', description='Add game URL to track')
    @app_commands.describe(url='Game URL on the site')
    @app_commands.default_permissions(administrator=True)
    async def track_game(self, interaction: discord.Interaction, url: str):
        logging.info(f"Slash command '/track' triggered by {interaction.user} with URL: {url}")
        await interaction.response.defer()
        normalized_url = normalize_game_url(url)
        tracked_games = await async_load_tracked_games()

        if normalized_url in tracked_games:
            await interaction.followup.send('This game is already tracked.')
            return

        # Try single page first (fast) before scanning all pages
        await interaction.followup.send(
            'Searching for game on the site... '
            '(Might take up to 30s in background)'
        )

        single_game_info = await parser_instance.async_parse_single_game_page(normalized_url)
        now_iso = datetime.now().isoformat()

        if single_game_info:
            tracked_game = TrackedGame.from_raw(single_game_info)
            tracked_game.last_scanned = now_iso
            tracked_games[normalized_url] = tracked_game
            await async_save_tracked_games(tracked_games)
            await interaction.followup.send(
                f'Game `{tracked_game.title}` added to tracking list with date `{tracked_game.date}`.'
            )
            return

        # Fallback: search all pages if single page parsing failed
        logging.info(f"Single page parse failed for {normalized_url}, searching all pages...")
        games_on_page, _ = await parser_instance.async_parse_games_on_page()
        game_info = games_on_page.get(normalized_url)

        if game_info:
            tracked_game = TrackedGame.from_raw(game_info)
            tracked_game.last_scanned = now_iso
            tracked_games[normalized_url] = tracked_game
            await async_save_tracked_games(tracked_games)
            await interaction.followup.send(
                f'Game `{tracked_game.title}` added to tracking list with date `{tracked_game.date}`.'
            )
            return

        tracked_games[normalized_url] = TrackedGame(
            title='Unknown',
            date=NO_DATE,
            image_url=NO_IMAGE,
            last_scanned=now_iso,
        )
        await async_save_tracked_games(tracked_games)
        await interaction.followup.send(
            'URL added to list. Game not found on site, date will be updated when it appears.'
        )

    async def untrack_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        tracked_games = await async_load_tracked_games()
        choices: list[app_commands.Choice[str]] = []
        for game_url, game_data in tracked_games.items():
            title = game_data.title if isinstance(game_data, TrackedGame) else str(game_data)
            if current.lower() in title.lower() or current.lower() in game_url.lower():
                display_name = title[:100]
                choices.append(app_commands.Choice(name=display_name, value=game_url))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name='untrack', description='Remove URL from tracking list')
    @app_commands.describe(url='Game URL or name from the list')
    @app_commands.autocomplete(url=untrack_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def untrack_game(self, interaction: discord.Interaction, url: str):
        logging.info(f"Slash command '/untrack' triggered by {interaction.user} for URL: {url}")
        await interaction.response.defer()
        tracked_games = await async_load_tracked_games()
        if url in tracked_games:
            del tracked_games[url]
            await async_save_tracked_games(tracked_games)
            await interaction.followup.send(f'Game with URL `{url}` removed from tracking list.')
            return

        await interaction.followup.send('Game with this URL not found in the list.')