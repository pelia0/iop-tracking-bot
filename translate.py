import re

def translate_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # bot.py translations
    replacements = [
         # Headers/Comments
         (r"# --- 1. НАСТРОЙКА ---", r"# --- 1. SETTINGS ---"),
         (r"# --- 2. ОСНОВНАЯ ЗАДАЧА БОТА ---", r"# --- 2. MAIN BOT TASK ---"),
         (r"# --- 3. КОМАНДЫ DISCORD ---", r"# --- 3. DISCORD COMMANDS ---"),
         (r"# --- 4. ЗАПУСК БОТА ---", r"# --- 4. START BOT ---"),
         (r"Запускаем парсинг в отдельном потоке, чтобы не блокировать Discord бота", r"Run parsing in a separate thread to avoid blocking Discord bot"),
         (r"Перевіряємо лише 1 сторінку, бо CF блокує пагінацію, а нові ігри і так на першій.", r"Checking only 1 page because CF blocks pagination, and new games are on the first page anyway."),
         (r"Глибока перевірка \(Бекфіл\) для ігор: N\/A, або старіших за 7 днів", r"Deep check (Backfill) for games: N/A, or older than 7 days"),
         (r"Максимум 2 гри за 1 цикл \(15 хв\)", r"Maximum 2 games per 1 cycle (15 min)"),
         (r"Перевіряємо, чи ми вже робили глибоку перевірку цієї гри за останні 24 години", r"Check if we have already done a deep check for this game in the last 24 hours"),
         (r"Піддержка как старого формата дат \(строка\), так и нового \(словарь\)", r"Support for both old date format (string) and new (dict)"),
         (r"Створюємо кнопки", r"Create buttons"),
         (r"Просто тихо оновлюємо, якщо це перше знаходження після N\/A", r"Quietly update if this is the first finding after N/A"),
         (r"Ініціалізуємо драйвер у фоні при старті", r"Initialize driver in background on startup"),
         (r"Парсим в отдельном потоке", r"Parse in separate thread"),
         (r"Если не нашли на главной, попробуем загрузить страницу", r"If not found on main page, try loading the generic page"),
         (r"Закриваємо драйвер при зупинці", r"Closing driver on shutdown"),
         (r"КРИТИЧЕСКАЯ ОШИБКА: DISCORD_TOKEN или CHANNEL_ID не найдены!", r"CRITICAL ERROR: DISCORD_TOKEN or CHANNEL_ID not found!"),

         # Logs and UI Strings
         (r'Проверяю обновления отслеживаемых игр...', r'Checking for tracked game updates...'),
         (r'Список отслеживания пуст. Проверка завершена.', r'Tracking list is empty. Check completed.'),
         (r'Не удалось получить игры со страницы. Пропускаю проверку.', r'Failed to get games from page. Skipping check.'),
         (r'⚠️ \*\*КРИТИЧЕСКАЯ ОШИБКА\*\*: ПАРСЕР НЕ РАБОТАЕТ! ⚠️\\nУже 3 попытки подряд завершились неудачей. Требуется ручная проверка логов.', r'⚠️ **CRITICAL ERROR**: PARSER IS DOWN! ⚠️\n3 consecutive attempts failed. Manual check required.'),
         (r'ОШИБКА ПАРСЕРА', r'PARSER ERROR'),
         (r'Не удалось найти канал с ID:', r'Failed to find channel with ID:'),
         (r'ОБНОВЛЕНИЕ! Игра', r'UPDATE! Game'),
         (r'изменила дату с', r'changed date from'),
         (r'Перейти до гри', r'Go to Game'),
         (r'📅 Обновление игры:', r'📅 Game Update:'),
         (r'Дата обновления была изменена!', r'Update date has been changed!'),
         (r'Старая дата', r'Old Date'),
         (r'Новая дата', r'New Date'),
         (r'⏳ Затримка 5 хвилин перед наступною глибокою перевіркою \(анти-Cloudflare\)...', r'⏳ 5 minute delay before next deep check (anti-Cloudflare)...'),
         (r'🔍 Глибока перевірка сторінки:', r'🔍 Deep checking page:'),
         (r'✅ Оновлено дату після глибокої перевірки для', r'✅ Date updated after deep check for'),
         (r'Файл отслеживания обновлен новыми датами.', r'Tracking file updated with new dates.'),
         (r'Обновлений не найдено.', r'No updates found.'),
         (r'игр \| обн.', r'games | upd.'),
         (r'успешно подключился к Discord!', r'successfully connected to Discord!'),
         (r'Синхронізовано', r'Synchronized'),
         (r'slash-команд.', r'slash commands.'),
         (r'Помилка синхронізації slash-команд:', r'Error synchronizing slash commands:'),
         (r'Добавить URL игры для отслеживания', r'Add game URL to track'),
         (r'URL страницы игры на сайте', r'Game URL on the site'),
         (r'Эта игра уже отслеживается.', r'This game is already tracked.'),
         (r'Ищу игру на сайте... \(Это может занять до 30 секунд в фоне\)', r'Searching for game on the site... (Might take up to 30s in background)'),
         (r'Игра `\{game_info\[\'title\'\]\}` добавлена в список отслеживания с датой `\{game_info\[\'date\'\]\}`.', r'Game `{game_info[\'title\']}` added to tracking list with date `{game_info[\'date\']}`.'),
         (r'Игра `\{single_game_info\[\'title\'\]\}` добавлена. Точная дата будет обновлена позже.', r'Game `{single_game_info[\'title\']}` added. Exact date will be updated later.'),
         (r'URL добавлен в список. Игра не найдена на сайте, дата будет обновлена при ее появлении.', r'URL added to list. Game not found on site, date will be updated when it appears.'),
         (r'Удалить URL из списка отслеживания', r'Remove URL from tracking list'),
         (r'URL игры или её название из списка', r'Game URL or name from the list'),
         (r'Игра с URL `\{url\}` удалена из списка отслеживания.', r'Game with URL `{url}` removed from tracking list.'),
         (r'Игра с таким URL не найдена в списке.', r'Game with this URL not found in the list.'),
         (r'Показать список отслеживаемых игр \(с пагинацией\)', r'Show tracked games list (paginated)'),
         (r'Список отслеживаемых игр пуст.', r'Tracked games list is empty.'),
         (r'Отслеживаемые игры \(Сторінка', r'Tracked Games (Page'),
         (r'Оновлено:', r'Updated:'),
         (r'Начинаю принудительную проверку \(в фоне\)...', r'Starting forced check (in background)...'),
         (r'Принудительно проверить обновления в фоне', r'Force background update check'),
         (r'Показати статус бота', r'Show bot status'),
         (r'Статус IOP Tracking Bot', r'IOP Tracking Bot Status'),
         (r'Відстежуваних ігор', r'Tracked games'),
         (r'Остання перевірка', r'Last check'),
         (r'Ніколи', r'Never'),
         (r'Всього перевірок \(upt.\)', r'Total checks (uptime)'),
         (r'Помилок підряд', r'Consecutive errors'),
         (r'У вас нет прав для использования этой команды.', r'You do not have permission to use this command.'),
         (r'Ошибка команды:', r'Command error:'),

         # parser.py
         (r'Инициализация WebDriver... Проверка версии chromedriver.', r'Initializing WebDriver... Checking chromedriver version.'),
         (r'Используем системный chromedriver:', r'Using system chromedriver:'),
         (r'Chromedriver готов. Путь:', r'Chromedriver ready. Path:'),
         (r'Ошибка инициализации chromedriver:', r'Error initializing chromedriver:'),
         (r'Создаёт новый экземпляр Chrome WebDriver.', r'Creates a new Chrome WebDriver instance.'),
         (r'Путь к chromedriver не инициализирован.', r'Path to chromedriver is not initialized.'),
         (r'Существующий WebDriver не отвечает, пересоздаю...', r'Existing WebDriver is unresponsive, recreating...'),
         (r'Принудительно уничтожает текущий драйвер для пересоздания при следующем вызове.', r'Force kills current driver to recreate on next call.'),
         (r'Сброс WebDriver после ошибки...', r'Resetting WebDriver after error...'),
         (r'Синхронная блокирующая функция парсинга нескольких страниц с играми \(с retry\).', r'Synchronous blocking function for parsing multiple game pages (with retry).'),
         (r'Ожидание (.*) сек перед загрузкой страницы (.*) \(анти-спам\)...', r'Waiting \1 sec before loading page \2 (anti-spam)...'),
         (r'Selenium ожидает загрузки контента \(страница (.*)\)...', r'Selenium waiting for content load (page \1)...'),
         (r'Основной блок \'dle-content\' не найден на странице', r'Main block \'dle-content\' not found on page'),
         (r'Ошибка при парсинге страницы \(попытка (.*)\):', r'Error parsing page (attempt \1):'),
         (r'Все попытки парсинга исчерпаны.', r'All parsing attempts exhausted.'),
         (r'Повторная попытка с новым WebDriver...', r'Retrying with new WebDriver...'),
         (r'Синхронная функция парсинга отдельной страницы игры \(с retry\).', r'Synchronous function for parsing a single game page (with retry).'),
         (r'Остров Наслаждений!', r'Island of Pleasure!'),
         (r'Ошибка при парсинге отдельной страницы', r'Error parsing single page'),

         # health.py
         (r'Успішний запуск парсера', r'Successful parser run'),
         (r'Помилка парсингу', r'Parsing error'),

         # storage.py
         (r'Файл', r'File'),
         (r'не знайдено. Створено новий порожній список.', r'not found. Created a newly empty list.'),
         (r'Збережено резервну копію', r'Saved backup copy to'),
         (r'Дані успішно збережено в', r'Data successfully saved to'),
    ]

    for ukr, eng in replacements:
        content = re.sub(ukr, eng, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

translate_file('bot.py')
translate_file('core/parser.py')
translate_file('core/health.py')
translate_file('core/storage.py')
print("Translated successfully.")
