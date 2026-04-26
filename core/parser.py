from __future__ import annotations

import asyncio
import threading
from typing import Any

from core.selenium_page_parser import SeleniumPageParser
from core.selenium_single_game_parser import SeleniumSingleGameParser
from core.webdriver_manager import WebDriverManager


class GameParser:
    """Main game parser that composes page and single game parsing.

    Uses a shared WebDriverManager so both parsers reuse the same
    browser session. Thread-safe singleton created at module level.
    """

    def __init__(self) -> None:
        shared_wdm = WebDriverManager()
        self.page_parser = SeleniumPageParser(shared_wdm)
        self.single_parser = SeleniumSingleGameParser(shared_wdm)
        self._async_lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create the asyncio.Lock inside the running event loop."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def parse_games_on_page(
        self, pages_to_check: int = 20, stop_date: Any = None
    ) -> tuple[dict[str, dict[str, str]], int]:
        """Parse games on page (synchronous)."""
        return self.page_parser.parse_games_on_page(pages_to_check, stop_date)

    def parse_single_game_page(self, url: str) -> dict[str, str] | None:
        """Parse single game page (synchronous)."""
        return self.single_parser.parse_single_game_page(url)

    async def async_parse_games_on_page(
        self, pages_to_check: int = 20, stop_date: Any = None
    ) -> tuple[dict[str, dict[str, str]], int]:
        """Async wrapper with lock for parsing games on page."""
        async with self._get_lock():
            return await asyncio.to_thread(
                self.parse_games_on_page, pages_to_check, stop_date
            )

    async def async_parse_single_game_page(
        self, url: str
    ) -> dict[str, str] | None:
        """Async wrapper with lock for parsing a single game page."""
        async with self._get_lock():
            return await asyncio.to_thread(self.parse_single_game_page, url)

    def quit(self) -> None:
        """Clean up resources."""
        self.page_parser.quit()
        # single_parser shares the same WebDriverManager, no need to quit separately


# Module-level singleton
parser_instance = GameParser()
