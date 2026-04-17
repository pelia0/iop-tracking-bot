from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

DATE_FORMAT = "%d.%m.%Y"

@dataclass
class TrackedGame:
    title: str
    date: str = "N/A"
    image_url: str = "N/A"
    last_scanned: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_raw(cls, raw: Any) -> "TrackedGame":
        if isinstance(raw, cls):
            return raw

        if isinstance(raw, str):
            return cls(title="Unknown", date=raw if cls._looks_like_date(raw) else "N/A")

        if isinstance(raw, dict):
            return cls(
                title=str(raw.get("title", "Unknown")) if raw.get("title") is not None else "Unknown",
                date=str(raw.get("date", "N/A")) if raw.get("date") is not None else "N/A",
                image_url=str(raw.get("image_url", "N/A")) if raw.get("image_url") is not None else "N/A",
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
