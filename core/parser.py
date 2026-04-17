import os
import logging
import threading
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

MAX_RETRIES = 2

class GameParser:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GameParser, cls).__new__(cls)
                cls._instance.driver = None
                cls._instance.chromedriver_path = None
            return cls._instance

    def initialize(self):
        """Init chromedriver path once"""
        if not self.chromedriver_path:
            logging.info("Инициализация WebDriver... Проверка версии chromedriver.")
            system_chromedriver = "/usr/bin/chromedriver"
            if os.path.exists(system_chromedriver):
                self.chromedriver_path = system_chromedriver
                logging.info(f"Используем системный chromedriver: {self.chromedriver_path}")
            else:
                try:
                    self.chromedriver_path = ChromeDriverManager().install()
                    logging.info(f"Chromedriver готов. Путь: {self.chromedriver_path}")
                except Exception as e:
                    logging.critical(f"Ошибка инициализации chromedriver: {e}")
                    self.chromedriver_path = None

    def _create_fresh_driver(self):
        """Создаёт новый экземпляр Chrome WebDriver."""
        if not self.chromedriver_path:
            self.initialize()
            if not self.chromedriver_path:
                raise Exception("Путь к chromedriver не инициализирован.")

        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
        
        service = ChromeService(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def get_driver(self):
        if self.driver:
            try:
                _ = self.driver.title
                return self.driver
            except Exception:
                logging.warning("Существующий WebDriver не отвечает, пересоздаю...")
                self.quit()

        self.driver = self._create_fresh_driver()
        return self.driver

    def _reset_driver(self):
        """Принудительно уничтожает текущий драйвер для пересоздания при следующем вызове."""
        logging.warning("Сброс WebDriver после ошибки...")
        self.quit()

    def parse_games_on_page(self, base_url='https://island-of-pleasure.site/games/', pages_to_check=3):
        """Синхронная блокирующая функция парсинга нескольких страниц с играми (с retry)."""
        all_games = {}
        import time
        import random
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                driver = self.get_driver()
                
                for page in range(1, pages_to_check + 1):
                    page_url = base_url if page == 1 else f"{base_url}page/{page}/"
                    
                    if page > 1:
                        delay = random.uniform(3.0, 6.0)
                        logging.info(f"Ожидание {delay:.1f} сек перед загрузкой страницы {page} (анти-спам)...")
                        time.sleep(delay)
                        
                    driver.get(page_url)
                    
                    logging.info(f"Selenium ожидает загрузки контента (страница {page})...")
                    wait = WebDriverWait(driver, 30)
                    wait.until(EC.presence_of_element_located((By.ID, "dle-content")))
                    
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content_div = soup.find('div', id='dle-content')
                    if not content_div:
                        logging.warning(f"Основной блок 'dle-content' не найден на странице {page}.")
                        continue

                    game_blocks = content_div.find_all('div', class_=lambda c: c and 'shortstory-in' in c and 'story_news' in c)
                    
                    for block in game_blocks:
                        title_element = block.find('h4', class_='short-link').find('a')
                        if not title_element: continue

                        game_url = title_element['href']
                        game_title = title_element.get('title', title_element.text.strip())
                        
                        date_element = block.find('div', class_='update_date')
                        game_date = date_element.text.strip() if date_element else "N/A"
                        
                        image_element = block.find('img')
                        game_image_url = "N/A"
                        if image_element:
                            img_src = image_element['src']
                            game_image_url = f'https://island-of-pleasure.site{img_src}' if img_src.startswith('/') else img_src

                        all_games[game_url] = {
                            "title": game_title,
                            "date": game_date,
                            "image_url": game_image_url
                        }
                return all_games
            except Exception as e:
                logging.error(f"Ошибка при парсинге страницы (попытка {attempt}/{MAX_RETRIES}): {e}")
                self._reset_driver()
                if attempt == MAX_RETRIES:
                    logging.error("Все попытки парсинга исчерпаны.")
                    return {}
                logging.info("Повторная попытка с новым WebDriver...")

    def parse_single_game_page(self, url: str):
        """Синхронная функция парсинга отдельной страницы игры (с retry)."""
        import re
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                driver = self.get_driver()
                driver.get(url)
                wait = WebDriverWait(driver, 30)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                game_title = driver.title
                if "» 18+ Остров Наслаждений!" in game_title:
                    game_title = game_title.split("»")[0].strip()
                    
                html = driver.page_source
                match = re.search(r'Обновлен[оа]?\s*:?\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})', html, re.IGNORECASE)
                game_date = match.group(1) if match else "N/A"
                
                logging.info(f"parse_single_game_page {url} -> title: {game_title}, date: {game_date}")
                return {"title": game_title, "date": game_date, "image_url": "N/A"} # image_url just in case
            except Exception as e:
                logging.error(f"Ошибка при парсинге отдельной страницы {url} (попытка {attempt}/{MAX_RETRIES}): {e}")
                self._reset_driver()
                if attempt == MAX_RETRIES:
                    return None
                logging.info("Повторная попытка с новым WebDriver...")

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

parser_instance = GameParser()
