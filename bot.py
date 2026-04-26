from __future__ import annotations
import logging
import os

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core.parser import parser_instance
from core.updater import IOPUpdater
from cogs.list_cog import ListCog
from cogs.status_cog import StatusCog
from cogs.track_cog import TrackCog

from logging.handlers import RotatingFileHandler

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', encoding='utf-8', maxBytes=5*1024*1024, backupCount=3),
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
async def setup_hook():
    """Runs once when the bot starts. Register cogs and sync commands here."""
    await bot.add_cog(TrackCog(bot))
    await bot.add_cog(ListCog(bot))
    await bot.add_cog(StatusCog(bot, check_for_updates, updater))

    try:
        synced = await bot.tree.sync()
        logging.info(f'Synchronized {len(synced)} slash commands.')
    except Exception as error:
        logging.error(f'Failed to sync slash commands: {error}')


@bot.event
async def on_ready():
    logging.info(f'{bot.user} successfully connected to Discord!')
    if not check_for_updates.is_running():
        check_for_updates.start()


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
            if check_for_updates.is_running():
                check_for_updates.cancel()
            parser_instance.quit()
