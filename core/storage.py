import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from core.models import TrackedGame

TRACKED_GAMES_FILE = Path("tracked_games.json")
SETTINGS_FILE = Path("settings.json")

storage_lock = asyncio.Lock()
_games_lock = asyncio.Lock()
_settings_lock = asyncio.Lock()


def load_tracked_games() -> dict[str, TrackedGame]:
    if not TRACKED_GAMES_FILE.exists():
        return {}

    try:
        with TRACKED_GAMES_FILE.open('r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        logging.error(f"Failed to load tracked games: {error}")
        return {}

    games: dict[str, TrackedGame] = {}
    for url, value in (raw_data or {}).items():
        try:
            games[url] = TrackedGame.from_raw(value)
        except TypeError:
            logging.warning(f"Skipping invalid tracked game entry: {url}")
    return games


def save_tracked_games(data: dict[str, TrackedGame]) -> None:
    if TRACKED_GAMES_FILE.exists():
        try:
            shutil.copy2(TRACKED_GAMES_FILE, TRACKED_GAMES_FILE.with_suffix('.json.bak'))
        except Exception as error:
            logging.error(f"Failed to create backup: {error}")

    TRACKED_GAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(TRACKED_GAMES_FILE.parent), suffix='.json')
    try:
        with open(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump({url: game.to_dict() for url, game in data.items()}, f, indent=4, ensure_ascii=False)
        Path(tmp_path).replace(TRACKED_GAMES_FILE)
    except Exception as error:
        Path(tmp_path).unlink(missing_ok=True)
        logging.error(f"Error saving tracked games: {error}")
        raise


def load_settings() -> dict[str, str]:
    if not SETTINGS_FILE.exists():
        return {"last_full_check": "1970-01-01T00:00:00"}

    try:
        with SETTINGS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError) as error:
        logging.error(f"Failed to load settings: {error}")

    return {"last_full_check": "1970-01-01T00:00:00"}


def save_settings(data: dict[str, str]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with SETTINGS_FILE.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as error:
        logging.error(f"Error saving settings: {error}")
        raise


async def async_load_tracked_games() -> dict[str, TrackedGame]:
    async with _games_lock:
        return await asyncio.to_thread(load_tracked_games)

async def async_save_tracked_games(data: dict[str, TrackedGame]) -> None:
    async with _games_lock:
        await asyncio.to_thread(save_tracked_games, data)

async def async_load_settings() -> dict[str, str]:
    async with _settings_lock:
        return await asyncio.to_thread(load_settings)

async def async_save_settings(data: dict[str, str]) -> None:
    async with _settings_lock:
        await asyncio.to_thread(save_settings, data)
