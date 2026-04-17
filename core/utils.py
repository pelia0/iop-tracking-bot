from __future__ import annotations
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