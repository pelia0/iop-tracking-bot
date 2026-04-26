# --- Sentinel values ---
UNKNOWN_TITLE = "Unknown"
NO_DATE = "N/A"
NO_IMAGE = "N/A"

# --- Date format ---
DATE_FORMAT = "%d.%m.%Y"

# --- Scraping ---
MAX_RETRIES = 2
BASE_URL = "https://island-of-pleasure.site/games/"
SITE_ORIGIN = "https://island-of-pleasure.site"
CONTENT_ID = "dle-content"
NEXT_BTN_SELECTOR = ".pages-next a"
IGNORED_URLS = {
    "https://island-of-pleasure.site/40996-videourok-po-perevodu-igr-na-dvizhke-renpy-rpgm-i-unity-v261225-2025-rus.html",
    "https://island-of-pleasure.site/15499-obschie-pravila-na-sayte.html",
    "https://island-of-pleasure.site/37669-hochu-stat-perevodchikom.html",
}

# --- Updater timing ---
MAX_PAGES_PER_SCAN = 20
DEEP_CHECK_LIMIT_PER_CYCLE = 10
DEEP_CHECK_INTERVAL_HOURS = 24
MINUTES_BETWEEN_FULL_CHECK = 60
