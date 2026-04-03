import os
import logging
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core.storage import load_tracked_games, save_tracked_games
from core.parser import parser_instance

# --- 1. НАСТРОЙКА ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', 0))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 2. ОСНОВНАЯ ЗАДАЧА БОТА ---

@tasks.loop(minutes=15)
async def check_for_updates():
    logging.info("Проверяю обновления отслеживаемых игр...")
    tracked_games = load_tracked_games()
    if not tracked_games:
        logging.info("Список отслеживания пуст. Проверка завершена.")
        return

    # Запускаем парсинг в отдельном потоке, чтобы не блокировать Discord бота
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page)
    
    if not games_on_page:
        logging.warning("Не удалось получить игры со страницы. Пропускаю проверку.")
        return

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

            if current_date != last_known_date:
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
    
    if updated_in_config:
        save_tracked_games(tracked_games)
        logging.info("Файл отслеживания обновлен новыми датами.")
    else:
        logging.info("Обновлений не найдено.")

# --- 3. КОМАНДЫ DISCORD ---

@bot.event
async def on_ready():
    logging.info(f'{bot.user} успешно подключился к Discord!')
    # Ініціалізуємо драйвер у фоні при старті
    await asyncio.to_thread(parser_instance.initialize)
    check_for_updates.start()

@bot.command(name='track', help='Добавить URL игры для отслеживания. Пример: !track <URL>')
@commands.has_permissions(administrator=True)
async def track_game(ctx, url: str):
    normalized_url = url.strip().lower().replace("www.", "").rstrip('/')
    if normalized_url.startswith("http://"):
        normalized_url = normalized_url.replace("http://", "https://")

    tracked_games = load_tracked_games()
    if normalized_url in tracked_games:
        await ctx.send(f"⚠️ Эта игра уже отслеживается.")
        return

    await ctx.send("🔍 Ищу игру на сайте... (Это может занять до 30 секунд в фоне)")
    
    # Парсим в отдельном потоке
    games_on_page = await asyncio.to_thread(parser_instance.parse_games_on_page)
    game_info = games_on_page.get(normalized_url)

    if game_info:
        tracked_games[normalized_url] = {"title": game_info['title'], "date": game_info['date']}
        save_tracked_games(tracked_games)
        await ctx.send(f"✅ Игра `{game_info['title']}` добавлена в список отслеживания с датой `{game_info['date']}`.")
    else:
        # Если не нашли на главной, попробуем загрузить страницу
        single_game_info = await asyncio.to_thread(parser_instance.parse_single_game_page, normalized_url)
        if single_game_info:
            tracked_games[normalized_url] = single_game_info
            save_tracked_games(tracked_games)
            await ctx.send(f"✅ Игра `{single_game_info['title']}` добавлена. Точная дата будет обновлена позже.")
        else:
            tracked_games[normalized_url] = {"title": "Unknown", "date": "N/A"}
            save_tracked_games(tracked_games)
            await ctx.send(f"✅ URL добавлен в список. Игра не найдена на сайте, дата будет обновлена при ее появлении.")

@bot.command(name='untrack', help='Удалить URL из списка отслеживания.')
@commands.has_permissions(administrator=True)
async def untrack_game(ctx, url: str):
    tracked_games = load_tracked_games()
    if url in tracked_games:
        del tracked_games[url]
        save_tracked_games(tracked_games)
        await ctx.send(f"✅ Игра с URL `{url}` удалена из списка отслеживания.")
    else:
        await ctx.send("⚠️ Игра с таким URL не найдена в списке.")

@bot.command(name='trackinglist', help='Показать список отслеживаемых игр.')
async def tracking_list(ctx):
    tracked_games = load_tracked_games()
    if not tracked_games:
        await ctx.send("Список отслеживаемых игр пуст.")
        return
        
    embed = discord.Embed(title="Отслеживаемые игры", color=discord.Color.blue())
    description = ""
    for i, (url, data) in enumerate(tracked_games.items(), 1):
        short_url = url.split('/')[-1].replace('.html', '')
        date = data if isinstance(data, str) else data.get("date", "N/A")
        title = data.get("title", short_url) if isinstance(data, dict) else short_url
        description += f"**{i}. [{title}]({url})**\n   Последняя дата: `{date}`\n"

    embed.description = description
    await ctx.send(embed=embed)
    
@bot.command(name='checknow', help='Принудительно проверить обновления.')
@commands.has_permissions(administrator=True)
async def force_check(ctx):
    await ctx.send("✅ Начинаю принудительную проверку (в фоне)...")
    check_for_updates.restart()

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