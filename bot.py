from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core.health import health
from core.models import TrackedGame
from core.parser import parser_instance
from core.storage import load_tracked_games, save_tracked_games
from core.updater import IOPUpdater
from core.utils import normalize_game_url

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8', mode='a'),
    ],
)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '0'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
updater = IOPUpdater(CHANNEL_ID)


@tasks.loop(hours=1)
async def check_for_updates():
    await updater.check_for_updates(bot)


@bot.event
async def on_ready():
    logging.info(f'{bot.user} successfully connected to Discord!')
    try:
        synced = await bot.tree.sync()
        logging.info(f'Synchronized {len(synced)} slash commands.')
    except Exception as error:
        logging.error(f'Failed to sync slash commands: {error}')

    await asyncio.to_thread(parser_instance.initialize)
    if not check_for_updates.is_running():
        check_for_updates.start()


@bot.tree.command(name='track', description='Add game URL to track')
@app_commands.describe(url='Game URL on the site')
@app_commands.default_permissions(administrator=True)
async def track_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    normalized_url = normalize_game_url(url)
    tracked_games = load_tracked_games()

    if normalized_url in tracked_games:
        await interaction.followup.send('This game is already tracked.')
        return

    await interaction.followup.send('Searching for game on the site... (Might take up to 30s in background)')
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page)
    game_info = games_on_page.get(normalized_url)
    now_iso = datetime.now().isoformat()

    if game_info:
        tracked_game = TrackedGame.from_raw(game_info)
        tracked_game.last_scanned = now_iso
        tracked_games[normalized_url] = tracked_game
        save_tracked_games(tracked_games)
        await interaction.channel.send(
            f'Game `{tracked_game.title}` added to tracking list with date `{tracked_game.date}`.'
        )
        return

    single_game_info = await asyncio.to_thread(parser_instance.parse_single_game_page, normalized_url)
    if single_game_info:
        tracked_game = TrackedGame.from_raw(single_game_info)
        tracked_game.last_scanned = now_iso
        tracked_games[normalized_url] = tracked_game
        save_tracked_games(tracked_games)
        await interaction.channel.send(
            f'Game `{tracked_game.title}` added. Exact date will be updated later.'
        )
        return

    tracked_games[normalized_url] = TrackedGame(
        title='Unknown',
        date='N/A',
        image_url='N/A',
        last_scanned=now_iso,
    )
    save_tracked_games(tracked_games)
    await interaction.channel.send(
        'URL added to list. Game not found on site, date will be updated when it appears.'
    )


async def untrack_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    tracked_games = load_tracked_games()
    choices: list[app_commands.Choice[str]] = []
    for game_url, game_data in tracked_games.items():
        title = game_data.title if isinstance(game_data, TrackedGame) else str(game_data)
        if current.lower() in title.lower() or current.lower() in game_url.lower():
            display_name = title[:100]
            choices.append(app_commands.Choice(name=display_name, value=game_url))
        if len(choices) >= 25:
            break
    return choices


@bot.tree.command(name='untrack', description='Remove URL from tracking list')
@app_commands.describe(url='Game URL or name from the list')
@app_commands.autocomplete(url=untrack_autocomplete)
@app_commands.default_permissions(administrator=True)
async def untrack_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if url in tracked_games:
        del tracked_games[url]
        save_tracked_games(tracked_games)
        await interaction.followup.send(f'Game with URL `{url}` removed from tracking list.')
        return

    await interaction.followup.send('Game with this URL not found in the list.')


class TrackingListView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0

    @discord.ui.button(label='<', style=discord.ButtonStyle.secondary, custom_id='prev_btn')
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(label='>', style=discord.ButtonStyle.secondary, custom_id='next_btn')
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        await interaction.response.edit_message(embed=self.pages[self.current])


@bot.tree.command(name='list', description='Show tracked games list (paginated)')
async def tracking_list(interaction: discord.Interaction):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if not tracked_games:
        await interaction.followup.send('Tracked games list is empty.')
        return

    pages: list[discord.Embed] = []
    items_per_page = 15
    items = list(tracked_games.items())

    for page_start in range(0, len(items), items_per_page):
        chunk = items[page_start:page_start + items_per_page]
        embed = discord.Embed(
            title=f'Tracked Games (Page {page_start // items_per_page + 1}/{(len(items) + items_per_page - 1) // items_per_page})',
            color=discord.Color.blue(),
        )
        description = ''

        for url, raw_data in chunk:
            game = raw_data if isinstance(raw_data, TrackedGame) else TrackedGame.from_raw(raw_data)
            short_url = url.split('/')[-1].replace('.html', '')
            date = game.date
            title = game.title if game.title != 'Unknown' else short_url
            status_emoji = '[OK]' if date != 'N/A' else '[N/A]'
            if 'Completed' in title or 'Completed' in short_url:
                status_emoji = '[DONE]'
            elif 'Abandoned' in title or 'Abandoned' in short_url:
                status_emoji = '[WARN]'

            description += f'{status_emoji} **[{title}]({url})**\\n   Updated: `{date}`\\n'

        embed.description = description
        pages.append(embed)

    if len(pages) == 1:
        await interaction.followup.send(embed=pages[0])
    else:
        view = TrackingListView(pages)
        await interaction.followup.send(embed=pages[0], view=view)


@bot.tree.command(name='checknow', description='Force background update check')
@app_commands.default_permissions(administrator=True)
async def force_check(interaction: discord.Interaction):
    await interaction.response.send_message('Starting forced check in background...')
    if check_for_updates.is_running():
        check_for_updates.restart()
    else:
        check_for_updates.start()


@bot.tree.command(name='status', description='Show bot status')
async def bot_status(interaction: discord.Interaction):
    tracked = load_tracked_games()
    embed = discord.Embed(
        title='IOP Tracking Bot Status',
        color=discord.Color.green() if health.consecutive_failures == 0 else discord.Color.red(),
    )
    embed.add_field(name='Tracked games', value=str(len(tracked)))

    last_check = health.last_successful_check.strftime('%Y-%m-%d %H:%M') if health.last_successful_check else 'Never'
    embed.add_field(name='Last check', value=last_check)
    embed.add_field(name='Total checks (uptime)', value=str(health.total_checks))
    if health.consecutive_failures > 0:
        embed.add_field(name='Consecutive errors', value=str(health.consecutive_failures))

    await interaction.response.send_message(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('You do not have permission to use this command.')
    else:
        logging.error(f'Command error: {error}')


if __name__ == '__main__':
    if not TOKEN or not CHANNEL_ID:
        logging.critical('CRITICAL ERROR: DISCORD_TOKEN or CHANNEL_ID not found!')
    else:
        try:
            bot.run(TOKEN)
        finally:
            parser_instance.quit()
