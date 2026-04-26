from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PageParser(ABC):
    """Abstract base for parsers that scan listing pages."""

    @abstractmethod
    def parse_games_on_page(
        self, pages_to_check: int = 20, stop_date: Any = None
    ) -> tuple[dict[str, dict[str, str]], int]:
        """Parse games across multiple listing pages."""

    @abstractmethod
    def quit(self) -> None:
        """Release resources."""


class SingleGameParser(ABC):
    """Abstract base for parsers that scrape individual game pages."""

    @abstractmethod
    def parse_single_game_page(self, url: str) -> dict[str, str] | None:
        """Parse a single game detail page."""

    @abstractmethod
    def quit(self) -> None:
        """Release resources."""