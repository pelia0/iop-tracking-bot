import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.health import health
from core.storage import async_load_tracked_games
from core.updater import IOPUpdater


class StatusCog(commands.Cog):
    """Cog for status and manual check commands."""

    def __init__(self, bot: commands.Bot, check_updates_loop: tasks.Loop, updater: IOPUpdater):
        self.bot = bot
        self.check_updates_loop = check_updates_loop
        self.updater = updater

    @app_commands.command(
        name='checknow', description='Force background update check'
    )
    @app_commands.default_permissions(administrator=True)
    async def force_check(self, interaction: discord.Interaction):
        logging.info(f"Slash command '/checknow' triggered by {interaction.user}. Triggering FORCE check...")
        await interaction.response.send_message(
            'Starting forced check in background...'
        )
        task = asyncio.create_task(self.updater.check_for_updates(self.bot, force=True))
        task.add_done_callback(self._on_force_check_done)

    @staticmethod
    def _on_force_check_done(task: asyncio.Task) -> None:
        """Log any exception raised by the background force-check task."""
        if task.cancelled():
            logging.warning("Force check task was cancelled.")
            return
        exc = task.exception()
        if exc is not None:
            logging.error(f"Force check task failed with error: {exc}", exc_info=exc)

    @app_commands.command(name='status', description='Show bot status')
    async def show_status(self, interaction: discord.Interaction):
        tracked = await async_load_tracked_games()
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