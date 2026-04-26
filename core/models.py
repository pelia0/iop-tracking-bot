from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from core.config import DATE_FORMAT, NO_DATE, NO_IMAGE, UNKNOWN_TITLE

@dataclass
class TrackedGame:
    title: str
    date: str = NO_DATE
    image_url: str = NO_IMAGE
    last_scanned: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_raw(cls, raw: Any) -> "TrackedGame":
        if isinstance(raw, cls):
            return raw

        if isinstance(raw, str):
            return cls(title=UNKNOWN_TITLE, date=raw if cls._looks_like_date(raw) else NO_DATE)

        if isinstance(raw, dict):
            return cls(
                title=str(raw.get("title", UNKNOWN_TITLE)) if raw.get("title") is not None else UNKNOWN_TITLE,
                date=str(raw.get("date", NO_DATE)) if raw.get("date") is not None else NO_DATE,
                image_url=str(raw.get("image_url", NO_IMAGE)) if raw.get("image_url") is not None else NO_IMAGE,
                last_scanned=str(raw.get("last_scanned", "")) if raw.get("last_scanned") is not None else "",
            )

        raise TypeError(f"Unsupported tracked game format: {type(raw)}")

    @classmethod
    def _looks_like_date(cls, value: str) -> bool:
        try:
            datetime.strptime(value, DATE_FORMAT)
            return True
        except ValueError:
            return False
