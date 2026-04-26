import discord
from discord import app_commands
from discord.ext import commands

from core.config import NO_DATE, UNKNOWN_TITLE
from core.models import TrackedGame
from core.storage import async_load_tracked_games


class ListCog(commands.Cog):
    """Cog for listing tracked games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='list', description='Show tracked games list (paginated)')
    async def tracking_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tracked_games = await async_load_tracked_games()
        if not tracked_games:
            await interaction.followup.send('Tracked games list is empty.')
            return

        pages: list[discord.Embed] = []
        items_per_page = 10
        items = list(tracked_games.items())

        for page_start in range(0, len(items), items_per_page):
            chunk = items[page_start:page_start + items_per_page]
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            current_page_num = page_start // items_per_page + 1
            
            embed = discord.Embed(
                title=f'Tracked Games (Page {current_page_num}/{total_pages})',
                color=discord.Color.blue(),
            )
            description = ''

            for url, raw_data in chunk:
                game = raw_data if isinstance(raw_data, TrackedGame) else TrackedGame.from_raw(raw_data)
                short_url = url.split('/')[-1].replace('.html', '')
                date = game.date
                title = game.title if game.title != UNKNOWN_TITLE else short_url
                
                # Cleanup and truncate title
                title = title.split('»')[0].strip()
                if len(title) > 120:
                    title = title[:117] + '...'
                    
                status_emoji = '✅' if date != NO_DATE else '🔍'
                if 'Completed' in title or 'Completed' in short_url:
                    status_emoji = '🏁'
                elif 'Abandoned' in title or 'Abandoned' in short_url:
                    status_emoji = '⚠️'

                description += f'{status_emoji} **[{title}]({url})**\n   Updated: `{date}`\n\n'

            embed.description = description.strip()
            pages.append(embed)

        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
        else:
            view = TrackingListView(pages)
            await interaction.followup.send(embed=pages[0], view=view)


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

    async def on_timeout(self) -> None:
        """Disable buttons when the view expires."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True