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

    def get_driver(self):
        if not self.chromedriver_path:
            self.initialize()
            if not self.chromedriver_path:
                raise Exception("Путь к chromedriver не инициализирован.")

        if self.driver:
            try:
                # Check if driver is still alive
                title = self.driver.title
                return self.driver
            except Exception:
                self.quit()

        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')
        
        service = ChromeService(self.chromedriver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return self.driver

    def parse_games_on_page(self, site_url='https://island-of-pleasure.site/games/'):
        """Синхронная блокирующая функция парсинга всех игр на главной"""
        try:
            driver = self.get_driver()
            driver.get(site_url)
            
            logging.info("Selenium ожидает загрузки контента...")
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.ID, "dle-content")))
            
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            games_on_page = {}
            content_div = soup.find('div', id='dle-content')
            if not content_div:
                logging.warning("Основной блок 'dle-content' не найден.")
                return {}

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

                games_on_page[game_url] = {
                    "title": game_title,
                    "date": game_date,
                    "image_url": game_image_url
                }
            return games_on_page
        except Exception as e:
            logging.error(f"Ошибка при парсинге страницы: {e}")
            return {}

    def parse_single_game_page(self, url: str):
        """Синхронная функция парсинга отдельной страницы игры"""
        try:
            driver = self.get_driver()
            driver.get(url)
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            game_title = driver.title
            if "» 18+ Остров Наслаждений!" in game_title:
                game_title = game_title.split("»")[0].strip()
            
            return {"title": game_title, "date": "N/A"}
        except Exception as e:
            logging.error(f"Ошибка при парсинге отдельной страницы {url}: {e}")
            return None

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

parser_instance = GameParser()
