import os
import logging
import asyncio
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core.storage import load_tracked_games, save_tracked_games
from core.parser import parser_instance
from core.health import health

# --- 1. НАСТРОЙКА ---
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

# --- 2. ОСНОВНАЯ ЗАДАЧА БОТА ---
last_deep_check_time = {}

@tasks.loop(minutes=15)
async def check_for_updates():
    logging.info("Проверяю обновления отслеживаемых игр...")
    tracked_games = load_tracked_games()
    if not tracked_games:
        logging.info("Список отслеживания пуст. Проверка завершена.")
        health.record_success()
        return

    # Запускаем парсинг в отдельном потоке, чтобы не блокировать Discord бота
    # Перевіряємо лише 1 сторінку, бо CF блокує пагінацію, а нові ігри і так на першій.
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page, pages_to_check=1)
    
    if not games_on_page:
        logging.warning("Не удалось получить игры со страницы. Пропускаю проверку.")
        should_alert = health.record_failure()
        if should_alert:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send("⚠️ **КРИТИЧЕСКАЯ ОШИБКА**: ПАРСЕР НЕ РАБОТАЕТ! ⚠️\nУже 3 попытки подряд завершились неудачей. Требуется ручная проверка логов.")
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="ОШИБКА ПАРСЕРА"))
        return

    health.record_success()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        logging.error(f"Не удалось найти канал с ID: {CHANNEL_ID}")
        return
        
    updated_in_config = False
    for url, current_info in games_on_page.items():
        if url in tracked_games:
            # Поддержка как старого формата дат (строка), так и нового (словарь)
            game_data = tracked_games[url]
            last_known_date = game_data if isinstance(game_data, str) else game_data.get("date", "N/A")
            current_date = current_info['date']

            if current_date != last_known_date and last_known_date != "N/A":
                logging.info(f"ОБНОВЛЕНИЕ! Игра '{current_info['title']}' изменила дату с '{last_known_date}' на '{current_date}'")

                # Створюємо кнопки
                view = discord.ui.View()
                btn = discord.ui.Button(label="Перейти до гри", url=url, style=discord.ButtonStyle.link)
                view.add_item(btn)

                embed = discord.Embed(
                    title=f"📅 Обновление игры: {current_info['title']}",
                    url=url,
                    description="Дата обновления была изменена!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Старая дата", value=f"`{last_known_date}`", inline=True)
                embed.add_field(name="Новая дата", value=f"`{current_date}`", inline=True)
                embed.set_thumbnail(url=current_info['image_url'])
                embed.set_footer(text=f"URL: {url}")
                await channel.send(embed=embed, view=view)

                if isinstance(tracked_games[url], dict):
                    tracked_games[url]["date"] = current_date
                else:
                    tracked_games[url] = current_date
                updated_in_config = True
            elif current_date != last_known_date and last_known_date == "N/A":
                # Просто тихо оновлюємо, якщо це перше знаходження після N/A
                if isinstance(tracked_games[url], dict):
                    tracked_games[url]["date"] = current_date
                    tracked_games[url]["image_url"] = current_info.get("image_url", "N/A")
                else:
                    tracked_games[url] = {"title": current_info['title'], "date": current_date, "image_url": current_info.get("image_url", "N/A")}
                updated_in_config = True
                
    # Глибока перевірка (Бекфіл) для ігор: N/A, або старіших за 7 днів
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
            # Перевіряємо, чи ми вже робили глибоку перевірку цієї гри за останні 24 години
            last_checked = last_deep_check_time.get(url, None)
            if last_checked is None or (now - last_checked).total_seconds() > 24 * 3600:
                games_to_deep_check.append(url)
                if len(games_to_deep_check) >= 2: # Максимум 2 гри за 1 цикл (15 хв)
                    break
                    
    for i, check_url in enumerate(games_to_deep_check):
        if i > 0:
            logging.info("⏳ Затримка 5 хвилин перед наступною глибокою перевіркою (анти-Cloudflare)...")
            await asyncio.sleep(300)
            
        logging.info(f"🔍 Глибока перевірка сторінки: {check_url}")
        
        single_info = await asyncio.to_thread(parser_instance.parse_single_game_page, check_url)
        last_deep_check_time[check_url] = datetime.now()
        
        if single_info and single_info.get("date") not in ["N/A", None]:
            old_date = tracked_games[check_url] if isinstance(tracked_games[check_url], str) else tracked_games[check_url].get("date", "N/A")
            new_date = single_info["date"]
            
            if isinstance(tracked_games[check_url], dict):
                tracked_games[check_url]["date"] = new_date
                tracked_games[check_url]["title"] = single_info["title"]
            else:
                tracked_games[check_url] = {"title": single_info["title"], "date": new_date, "image_url": "N/A"}
                
            if old_date != new_date:
                updated_in_config = True
                logging.info(f"✅ Оновлено дату після глибокої перевірки для {single_info['title']}: {new_date}")

    if updated_in_config:
        save_tracked_games(tracked_games)
        logging.info("Файл отслеживания обновлен новыми датами.")
    else:
        logging.info("Обновлений не найдено.")
        
    now_str = datetime.now().strftime("%H:%M")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(tracked_games)} игр | обн. {now_str}"))

# --- 3. КОМАНДЫ DISCORD ---

@bot.event
async def on_ready():
    logging.info(f'{bot.user} успешно подключился к Discord!')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Синхронізовано {len(synced)} slash-команд.")
    except Exception as e:
        logging.error(f"Помилка синхронізації slash-команд: {e}")
        
    # Ініціалізуємо драйвер у фоні при старті
    await asyncio.to_thread(parser_instance.initialize)
    check_for_updates.start()

@bot.tree.command(name='track', description='Добавить URL игры для отслеживания')
@app_commands.describe(url="URL страницы игры на сайте")
@app_commands.default_permissions(administrator=True)
async def track_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    
    normalized_url = url.strip().lower().replace("www.", "").rstrip('/')
    if normalized_url.startswith("http://"):
        normalized_url = normalized_url.replace("http://", "https://")

    tracked_games = load_tracked_games()
    if normalized_url in tracked_games:
        await interaction.followup.send(f"⚠️ Эта игра уже отслеживается.")
        return

    await interaction.followup.send("🔍 Ищу игру на сайте... (Это может занять до 30 секунд в фоне)")
    
    # Парсим в отдельном потоке
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page)
    game_info = games_on_page.get(normalized_url)

    if game_info:
        tracked_games[normalized_url] = {"title": game_info['title'], "date": game_info['date'], "image_url": game_info['image_url']}
        save_tracked_games(tracked_games)
        await interaction.channel.send(f"✅ Игра `{game_info['title']}` добавлена в список отслеживания с датой `{game_info['date']}`.")
    else:
        # Если не нашли на главной, попробуем загрузить страницу
        single_game_info = await asyncio.to_thread(parser_instance.parse_single_game_page, normalized_url)
        if single_game_info:
            tracked_games[normalized_url] = single_game_info
            save_tracked_games(tracked_games)
            await interaction.channel.send(f"✅ Игра `{single_game_info['title']}` добавлена. Точная дата будет обновлена позже.")
        else:
            tracked_games[normalized_url] = {"title": "Unknown", "date": "N/A", "image_url": "N/A"}
            save_tracked_games(tracked_games)
            await interaction.channel.send(f"✅ URL добавлен в список. Игра не найдена на сайте, дата будет обновлена при ее появлении.")

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

@bot.tree.command(name='untrack', description='Удалить URL из списка отслеживания')
@app_commands.describe(url="URL игры или её название из списка")
@app_commands.autocomplete(url=untrack_autocomplete)
@app_commands.default_permissions(administrator=True)
async def untrack_game(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if url in tracked_games:
        del tracked_games[url]
        save_tracked_games(tracked_games)
        await interaction.followup.send(f"✅ Игра с URL `{url}` удалена из списка отслеживания.")
    else:
        await interaction.followup.send("⚠️ Игра с таким URL не найдена в списке.")

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

@bot.tree.command(name='list', description='Показать список отслеживаемых игр (с пагинацией)')
async def tracking_list(interaction: discord.Interaction):
    await interaction.response.defer()
    tracked_games = load_tracked_games()
    if not tracked_games:
        await interaction.followup.send("Список отслеживаемых игр пуст.")
        return
        
    pages = []
    items_per_page = 15
    items = list(tracked_games.items())
    
    for page_idx in range(0, len(items), items_per_page):
        embed = discord.Embed(
            title=f"Отслеживаемые игры (Сторінка {page_idx//items_per_page + 1}/{(len(items)+items_per_page-1)//items_per_page})", 
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
                
            description += f"{status_emoji} **[{title}]({url})**\n   Оновлено: `{date}`\n"

        embed.description = description
        pages.append(embed)

    if len(pages) == 1:
        await interaction.followup.send(embed=pages[0])
    else:
        view = TrackingListView(pages)
        await interaction.followup.send(embed=pages[0], view=view)
    
@bot.tree.command(name='checknow', description='Принудительно проверить обновления в фоне')
@app_commands.default_permissions(administrator=True)
async def force_check(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Начинаю принудительную проверку (в фоне)...")
    check_for_updates.restart()
    
@bot.tree.command(name='status', description='Показати статус бота')
async def bot_status(interaction: discord.Interaction):
    from core.health import health
    tracked = load_tracked_games()
    
    embed = discord.Embed(title="📊 Статус IOP Tracking Bot", color=discord.Color.green() if health.consecutive_failures == 0 else discord.Color.red())
    embed.add_field(name="Відстежуваних ігор", value=f"{len(tracked)}")
    
    last_check = health.last_successful_check.strftime("%Y-%m-%d %H:%M") if health.last_successful_check else "Ніколи"
    embed.add_field(name="Остання перевірка", value=last_check)
    embed.add_field(name="Всього перевірок (upt.)", value=str(health.total_checks))
    if health.consecutive_failures > 0:
         embed.add_field(name="⚠️ Помилок підряд", value=str(health.consecutive_failures))
         
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ У вас нет прав для использования этой команды.")
    else:
        logging.error(f"Ошибка команды: {error}")

# --- 4. ЗАПУСК БОТА ---
if __name__ == "__main__":
    if not TOKEN or not CHANNEL_ID:
        logging.critical("КРИТИЧЕСКАЯ ОШИБКА: DISCORD_TOKEN или CHANNEL_ID не найдены!")
    else:
        try:
            bot.run(TOKEN)
        finally:
            # Закриваємо драйвер при зупинці
            parser_instance.quit()