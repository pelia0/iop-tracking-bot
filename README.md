# IOP Tracking Bot

A Discord tracking bot designed to monitor Visual Novel releases and updates on the Island of Pleasure (IOP) website. It scrapes game updates silently in the background and sends Discord alerts when tracked games get updated.

## Architecture

The bot follows a modular architecture:

- **`bot.py`**: Main Discord bot with slash commands and task scheduling
- **`core/updater.py`**: Game update checking logic and notification handling
- **`core/parser.py`**: Selenium-based web scraping with Cloudflare bypass
- **`core/storage.py`**: JSON persistence with atomic writes and backups
- **`core/models.py`**: Data models for tracked games
- **`core/utils.py`**: Utility functions for URL normalization
- **`core/health.py`**: Health monitoring and failure tracking

## Features

- **Automated Tracking**: Background polling every hour to check for updates on tracked games.
- **Deep Date Backfilling**: Automatically fixes games with missing dates (N/A) by running deep singular checks spaced out safely.
- **Cloudflare Bypass**: Implements randomized delays and specialized scraping logic to prevent Cloudflare restrictions.
- **Slash Commands**: Manage your tracked list natively in Discord (`/track`, `/untrack`, `/list`, `/status`, `/checknow`).
- **Interactive UI**: The `/list` command supports button-driven pagination and visual status emojis.
- **Health Monitoring**: Watches for scraping failures and automatically changes bot presence if the parser crashes.
- **Atomic Operations**: Safe, corruption-proof JSON backups on every save (`tracked_games.json.bak`).

## Installation

### Prerequisites
- Python 3.10+
- Google Chrome & ChromeDriver (Automatically managed by `webdriver_manager`)
- Discord Bot Token with `message_content` intent enabled.

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/pelia0/iop-tracking-bot.git
   cd iop-tracking-bot
   ```
2. Create and activate a Virtual Environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configuration:
   Rename `.env.example` to `.env` and enter your credentials:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   CHANNEL_ID=your_discord_notification_channel_id_here
   ```

## Usage

Start the bot locally:
```bash
python bot.py
```

### Commands
- `/track <url>`: Add a game to the tracker list via its exact IOP url.
- `/untrack <url>`: Remove a game from tracking (Supports smart autocomplete).
- `/list`: Display all currently tracked games with their dates.
- `/status`: Show bot uptime, number of tracked games, and current parser health info.
- `/checknow`: Manually trigger the scraper task to run immediately in the background.

## Production Deployment
The project contains a `setup_bot.sh` script specifically for Ubuntu/Oracle Cloud environments which performs headless testing and sets up an auto-restarting `systemd` service.

1. Configure `.env` on your server.
2. Run `bash setup_bot.sh`.
