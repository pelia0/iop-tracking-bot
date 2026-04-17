import os
import logging
import asyncio
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core.storage import load_tracked_games, save_tracked_games, load_settings, save_settings
from core.parser import parser_instance
from core.health import health
from selenium.common.exceptions import TimeoutException

# --- 1. SETTINGS ---
import logging.handlers
log_handler = logging.handlers.RotatingFileHandler(
    filename='bot.log',
    encoding='utf-8',
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=2
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[log_handler, logging.StreamHandler()]
)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', 0))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 2. MAIN BOT TASK ---
last_deep_check_time = {}

@tasks.loop(minutes=15)
async def check_for_updates():
    settings = load_settings()
    last_check_str = settings.get("last_full_check", "1970-01-01T00:00:00")
    last_check_dt = datetime.fromisoformat(last_check_str)
    now = datetime.now()
    
    elapsed_minutes = (now - last_check_dt).total_seconds() / 60
    
    if elapsed_minutes < 15:
        wait_min = int(15 - elapsed_minutes)
        logging.info(f"Skipping check. Last check was {int(elapsed_minutes)}m ago. Next check in ~{wait_min}m.")
        return

    logging.info(f"Starting intelligent scan (last check: {last_check_dt.strftime('%d.%m.%Y %H:%M')})...")
    
    tracked_games = load_tracked_games()
    if not tracked_games:
        logging.info("Tracking list is empty. Check completed.")
        health.record_success()
        return

    try:
        # Run parsing in a separate thread to avoid blocking Discord bot
        # Intelligent stop: scan up to 20 pages, but stop if we hit dates older than last_check_dt
        games_on_page = await asyncio.to_thread(
            parser_instance.parse_games_on_page, 
            pages_to_check=20, 
            stop_date=last_check_dt
        )
    except TimeoutException:
        logging.warning("Cloudflare block detected during update check!")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("⚠️ **Cloudflare Block Detected**: The bot was prevented from scanning pages. Adding extra delay.")
        health.record_failure()
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="CLOUDFLARE BLOCK"))
        return
    except Exception as e:
        logging.error(f"Unexpected error during update check: {e}")
        health.record_failure()
        return

    if not games_on_page:
        logging.warning("Failed to get games from page (empty result).")
        # Record failure if it's consistently failing to get content
        health.record_failure()
        return

    # Update last successful check time
    settings["last_full_check"] = now.isoformat()
    save_settings(settings)

    health.record_success()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        logging.error(f"Failed to find channel with ID: {CHANNEL_ID}")
        return
        
    updated_in_config = False
    for url, current_info in games_on_page.items():
        if url in tracked_games:
            # Поддержка как старого формата дат (строка), так и нового (словарь)
            game_data = tracked_games[url]
            last_known_date = game_data if isinstance(game_data, str) else game_data.get("date", "N/A")
            current_date = current_info['date']

            if current_date != last_known_date:
                logging.info(f"UPDATE! Game '{current_info['title']}' changed date from '{last_known_date}' to '{current_date}'")

                # Create buttons
                view = discord.ui.View()
                btn = discord.ui.Button(label="Go to Game", url=url, style=discord.ButtonStyle.link)
                view.add_item(btn)

                embed = discord.Embed(
                    title=f"📅 Game Update: {current_info['title']}",
                    url=url,
                    description="Update date has been found/changed!" if last_known_date == "N/A" else "Update date has been changed!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Old Date", value=f"`{last_known_date}`", inline=True)
                embed.add_field(name="New Date", value=f"`{current_date}`", inline=True)
                embed.set_thumbnail(url=current_info['image_url'])
                embed.set_footer(text=f"URL: {url}")
                await channel.send(embed=embed, view=view)

                if isinstance(tracked_games[url], dict):
                    tracked_games[url]["date"] = current_date
                    tracked_games[url]["image_url"] = current_info.get("image_url", "N/A")
                else:
                    tracked_games[url] = {"title": current_info['title'], "date": current_date, "image_url": current_info.get("image_url", "N/A")}
                updated_in_config = True
                
    # Deep check (Backfill) for games: N/A, or older than 7 days
    games_to_deep_check = []
    now = datetime.now()
    
    for url, game_data in list(tracked_games.items()):
        date_str = game_data if isinstance(game_data, str) else game_data.get("date", "N/A")
        
        needs_check = False
        if date_str == "N/A":
            needs_check = True
        else:
            try:
                game_date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                if (now - game_date_obj).days > 7:
                    needs_check = True
            except ValueError:
                needs_check = True
                
        if needs_check:
            # Check if we have already done a deep check for this game in the last 24 hours
            last_checked = last_deep_check_time.get(url, None)
            if last_checked is None or (now - last_checked).total_seconds() > 24 * 3600:
                games_to_deep_check.append(url)
                if len(games_to_deep_check) >= 2: # Maximum 2 games per 1 cycle (15 min)
                    break
                    
    import random
    for i, check_url in enumerate(games_to_deep_check):
        delay_seconds = 300 if i > 0 else random.randint(30, 60)
        logging.info(f"⏳ {delay_seconds} second delay before deep check (simulating human)...")
        await asyncio.sleep(delay_seconds)
            
        logging.info(f"🔍 Deep checking page: {check_url}")
        
        single_info = await asyncio.to_thread(parser_instance.parse_single_game_page, check_url)
        last_deep_check_time[check_url] = datetime.now()
        
        if single_info and single_info.get("date") not in ["N/A", None]:
            old_date = tracked_games[check_url] if isinstance(tracked_games[check_url], str) else tracked_games[check_url].get("date", "N/A")
            new_date = single_info["date"]
            
            if old_date != new_date:
                # Відправляємо повідомлення в дискорд при глибокій перевірці
                view = discord.ui.View()
                btn = discord.ui.Button(label="Go to Game", url=check_url, style=discord.ButtonStyle.link)
                view.add_item(btn)

                embed = discord.Embed(
                    title=f"🔍 Backfill Update: {single_info['title']}",
                    url=check_url,
                    description="Update date has been found via deep check!" if old_date == "N/A" else "Update date has been changed via deep check!",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Old Date", value=f"`{old_date}`", inline=True)
                embed.add_field(name="New Date", value=f"`{new_date}`", inline=True)
                existing_image = tracked_games[check_url].get("image_url", "N/A") if isinstance(tracked_games[check_url], dict) else "N/A"
                if existing_image != "N/A":
                    embed.set_thumbnail(url=existing_image)
                embed.set_footer(text=f"URL: {check_url}")
                await channel.send(embed=embed, view=view)

                if isinstance(tracked_games[check_url], dict):
                    tracked_games[check_url]["date"] = new_date
                    tracked_games[check_url]["title"] = single_info["title"]
                else:
                    tracked_games[check_url] = {"title": single_info["title"], "date": new_date, "image_url": "N/A"}

                updated_in_config = True
                save_tracked_games(tracked_games)
                logging.info(f"✅ Date updated after deep check for {single_info['title']}: {new_date}. Progress saved.")

    if updated_in_config:
        logging.info("Deep check loop complete. Tracking file is up-to-date.")
    else:
        logging.info("No updates found.")
        
    now_str = datetime.now().strftime("%H:%M")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(tracked_games)} games | upd. {now_str}"))

# --- 3. DISCORD COMMANDS ---

@bot.event
async def on_ready():
    logging.info(f'{bot.user} successfully connected to Discord!')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synchronized {len(synced)} slash commands.")
    except Exception as e:
        logging.error(f"Помилка синхронізації slash commands. {e}")
        
    # Initialize driver in background on startup
    await asyncio.to_thread(parser_instance.initialize)
    check_for_updates.start()

@bot.tree.command(name='track', description='Add game URL to track')
@app_commands.describe(url="Game URL on the site")
@app_commands.default_permissions(administrator=True)
async def track_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    
    normalized_url = url.strip().lower().replace("www.", "").rstrip('/')
    if normalized_url.startswith("http://"):
        normalized_url = normalized_url.replace("http://", "https://")

    tracked_games = load_tracked_games()
    if normalized_url in tracked_games:
        await interaction.followup.send(f"⚠️ This game is already tracked.")
        return

    await interaction.followup.send("🔍 Searching for game on the site... (Might take up to 30s in background)")
    
    # Parse in separate thread
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page)
    game_info = games_on_page.get(normalized_url)

    if game_info:
        tracked_games[normalized_url] = {"title": game_info['title'], "date": game_info['date'], "image_url": game_info['image_url']}
        save_tracked_games(tracked_games)
        await interaction.channel.send(f"✅ Game `{game_info['title']}` added to tracking list with date `{game_info['date']}`.")
    else:
        # If not found on main page, try loading the generic page
        single_game_info = await asyncio.to_thread(parser_instance.parse_single_game_page, normalized_url)
        if single_game_info:
            tracked_games[normalized_url] = single_game_info
            save_tracked_games(tracked_games)
            await interaction.channel.send(f"✅ Game `{single_game_info['title']}` added. Exact date will be updated later.")
        else:
            tracked_games[normalized_url] = {"title": "Unknown", "date": "N/A", "image_url": "N/A"}
            save_tracked_games(tracked_games)
            await interaction.channel.send(f"✅ URL added to list. Game not found on site, date will be updated when it appears.")

async def untrack_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    tracked_games = load_tracked_games()
    choices = []
    for g_url, data in tracked_games.items():
        title = data.get("title", g_url) if isinstance(data, dict) else g_url
        if current.lower() in title.lower() or current.lower() in g_url.lower():
            display_name = f"{title}"[:100]
            choices.append(app_commands.Choice(name=display_name, value=g_url))
        if len(choices) >= 25:
            break
    return choices

@bot.tree.command(name='untrack', description='Remove URL from tracking list')
@app_commands.describe(url="Game URL or name from the list")
@app_commands.autocomplete(url=untrack_autocomplete)
@app_commands.default_permissions(administrator=True)
async def untrack_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if url in tracked_games:
        del tracked_games[url]
        save_tracked_games(tracked_games)
        await interaction.followup.send(f"✅ Game with URL `{url}` removed from tracking list.")
    else:
        await interaction.followup.send("⚠️ Game with this URL not found in the list.")

class TrackingListView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev_btn")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="next_btn")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        await interaction.response.edit_message(embed=self.pages[self.current])

@bot.tree.command(name='list', description='Show tracked games list (paginated)')
async def tracking_list(interaction: discord.Interaction):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if not tracked_games:
        await interaction.followup.send("Tracked games list is empty.")
        return
        
    pages = []
    items_per_page = 15
    items = list(tracked_games.items())
    
    for page_idx in range(0, len(items), items_per_page):
        embed = discord.Embed(
            title=f"Tracked Games (Page {page_idx//items_per_page + 1}/{(len(items)+items_per_page-1)//items_per_page})", 
            color=discord.Color.blue()
        )
        description = ""
        chunk = items[page_idx:page_idx+items_per_page]
        
        for url, data in chunk:
            short_url = url.split('/')[-1].replace('.html', '')
            date = data if isinstance(data, str) else data.get("date", "N/A")
            title = data.get("title", short_url) if isinstance(data, dict) else short_url
            
            # Simple categorization via emoji
            status_emoji = "🟢" if date != "N/A" else "🔴"
            if "Completed" in title or "Completed" in short_url:
                status_emoji = "🏁"
            elif "Abandoned" in title or "Abandoned" in short_url:
                status_emoji = "⚠️"
                
            description += f"{status_emoji} **[{title}]({url})**\n   Updated: `{date}`\n"

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
    await interaction.response.send_message("✅ Starting forced check (in background)...")
    check_for_updates.restart()
    
@bot.tree.command(name='status', description='Show bot status')
async def bot_status(interaction: discord.Interaction):
    from core.health import health
    tracked = load_tracked_games()
    
    embed = discord.Embed(title="📊 IOP Tracking Bot Status", color=discord.Color.green() if health.consecutive_failures == 0 else discord.Color.red())
    embed.add_field(name="Tracked games", value=f"{len(tracked)}")
    
    last_check = health.last_successful_check.strftime("%Y-%m-%d %H:%M") if health.last_successful_check else "Never"
    embed.add_field(name="Last check", value=last_check)
    embed.add_field(name="Total checks (uptime)", value=str(health.total_checks))
    if health.consecutive_failures > 0:
         embed.add_field(name="⚠️ Consecutive errors", value=str(health.consecutive_failures))
         
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ You do not have permission to use this command.")
    else:
        logging.error(f"Command error: {error}")

# --- 4. START BOT ---
if __name__ == "__main__":
    if not TOKEN or not CHANNEL_ID:
        logging.critical("CRITICAL ERROR: DISCORD_TOKEN or CHANNEL_ID not found!")
    else:
        try:
            bot.run(TOKEN)
        finally:
            # Closing driver on shutdown
            parser_instance.quit()