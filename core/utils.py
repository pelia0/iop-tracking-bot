from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse, urlunparse


def normalize_game_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url

    if not urlparse(url).scheme:
        url = f"https://{url}"

    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip('/')
    if not path:
        path = '/'

    normalized = urlunparse((scheme, netloc, path, '', '', ''))
    return normalized


def parse_isoformat_lenient(value: str) -> datetime:
    """Parse an ISO-format timestamp, tolerating quirks like single-digit hours.

    Falls back to ``datetime.fromisoformat`` after normalising the time part
    so that ``2026-04-18T9:30:00`` is accepted.
    """
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        if "T" in value:
            date_part, time_part = value.split("T", maxsplit=1)
            parts = time_part.split(":")
            parts[0] = parts[0].zfill(2)
            return datetime.fromisoformat(f"{date_part}T{':'.join(parts)}")
        raise