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
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from core.utils import normalize_game_url

MAX_RETRIES = 2
IGNORED_URLS = {
    "https://island-of-pleasure.site/40996-videourok-po-perevodu-igr-na-dvizhke-renpy-rpgm-i-unity-v261225-2025-rus.html",
    "https://island-of-pleasure.site/15499-obschie-pravila-na-sayte.html",
    "https://island-of-pleasure.site/37669-hochu-stat-perevodchikom.html"
}

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
            logging.info("Initializing WebDriver... Checking chromedriver version.")
            system_chromedriver = "/usr/bin/chromedriver"
            if os.path.exists(system_chromedriver):
                self.chromedriver_path = system_chromedriver
                logging.info(f"Using system chromedriver: {self.chromedriver_path}")
            else:
                try:
                    self.chromedriver_path = ChromeDriverManager().install()
                    logging.info(f"Chromedriver ready. Path: {self.chromedriver_path}")
                except Exception as e:
                    logging.critical(f"Error initializing chromedriver: {e}")
                    self.chromedriver_path = None

    def _create_fresh_driver(self):
        """Creates a new Chrome WebDriver instance."""
        if not self.chromedriver_path:
            self.initialize()
            if not self.chromedriver_path:
                raise Exception("Path to chromedriver is not initialized.")

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
                logging.warning("Existing WebDriver is unresponsive, recreating...")
                self.quit()

        self.driver = self._create_fresh_driver()
        return self.driver

    def _reset_driver(self):
        """Force kills current driver to recreate on next call."""
        logging.warning("Resetting WebDriver after error...")
        self.quit()

    def parse_games_on_page(self, pages_to_check=20, stop_date=None):
        """Synchronous blocking function for parsing several game pages.
        Retries are now handled per-page to avoid restarting from page 1 on failure.
        """
        all_games = {}
        base_url = "https://island-of-pleasure.site/games/"
        import time
        import random
        from datetime import datetime
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        from bs4 import BeautifulSoup

        last_scanned_page = 0
        for page in range(1, pages_to_check + 1):
            page_url = base_url if page == 1 else f"{base_url}page/{page}/"
            logging.info(f"--- Processing page {page} ---")
            last_scanned_page = page
            
            page_parsed_successfully = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    driver = self.get_driver()
                    
                    if page == 1:
                        logging.info(f"Loading {page_url} (initial page, attempt {attempt}/{MAX_RETRIES})...")
                        driver.get(page_url)
                    else:
                        delay = random.uniform(3.0, 6.0)
                        logging.info(f"Waiting {delay:.1f} sec before clicking next page {page} (anti-spam, attempt {attempt})...")
                        time.sleep(delay)
                        
                        try:
                            # Search for the "Next" button selector observed in the HTML
                            next_btn_selector = ".pages-next a"
                            wait = WebDriverWait(driver, 10)
                            next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_btn_selector)))
                            
                            # Scroll to button to make it more 'human'
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                            time.sleep(1)
                            
                            logging.info(f"Clicking 'Next' button to navigate to page {page}...")
                            next_btn.click()
                        except Exception as click_err:
                            logging.warning(f"Failed to click next button: {click_err}. Falling back to direct URL navigation.")
                            driver.get(page_url)
                    
                    logging.info(f"Selenium waiting for content load (page {page})...")
                    wait = WebDriverWait(driver, 30)
                    wait.until(EC.presence_of_element_located((By.ID, "dle-content")))
                    
                    # Manual delay for AJAX content stability
                    time.sleep(2)
                    
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content = soup.find(id='dle-content')
                    if not content:
                        raise ValueError("Element 'dle-content' not found on page.")
                    
                    game_blocks = content.find_all('div', class_='shortstory-in')
                    logging.info(f"Found {len(game_blocks)} articles on page {page}.")
                    
                    for block in game_blocks:
                        title_element = block.find('h4', class_='short-link').find('a')
                        if not title_element: continue

                        raw_game_url = title_element['href']
                        game_url = normalize_game_url(raw_game_url)
                        if game_url in IGNORED_URLS:
                            continue

                        game_title = title_element.get('title', title_element.text.strip())
                        
                        date_element = block.find('div', class_='update_date')
                        game_date_str = date_element.text.strip() if date_element else "N/A"
                        
                        # Early exit logic
                        if stop_date and game_date_str != "N/A":
                            try:
                                game_date = datetime.strptime(game_date_str, "%d.%m.%Y")
                                if game_date.date() < stop_date.date():
                                    logging.info(f"Stopping scan: encountered an older date {game_date.strftime('%d.%m.%Y')} (last full check was on {stop_date.strftime('%d.%m.%Y')})")
                                    return all_games, last_scanned_page
                            except (ValueError, TypeError):
                                pass

                        image_element = block.find('img')
                        image_url = image_element['src'] if image_element else "N/A"
                        if image_url != "N/A" and not image_url.startswith('http'):
                            image_url = "https://island-of-pleasure.site" + image_url
                            
                        all_games[game_url] = {
                            'title': game_title,
                            'date': game_date_str,
                            'image_url': image_url
                        }
                    
                    page_parsed_successfully = True
                    break # Success on this page
                    
                except Exception as e:
                    logging.error(f"Error parsing page {page} (attempt {attempt}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES:
                        logging.warning("Resetting WebDriver after error...")
                        self.quit()
                        time.sleep(2)
                        logging.info("Retrying current page with new WebDriver...")
                    else:
                        logging.error(f"Max retries reached for page {page}. Skipping.")
                        return all_games, last_scanned_page
            
            if not page_parsed_successfully:
                break
                
        return all_games, last_scanned_page

    def parse_single_game_page(self, url: str):
        """Synchronous function for parsing a single game page (with retry)."""
        import time
        import re
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        from bs4 import BeautifulSoup
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                driver = self.get_driver()
                driver.get(url)
                wait = WebDriverWait(driver, 45)  # Extended wait for Cloudflare challenge
                wait.until(EC.presence_of_element_located((By.ID, "dle-content")))
                
                game_title = driver.title
                if "» 18+ Island of Pleasure!" in game_title:
                    game_title = game_title.split("»")[0].strip()
                    
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                main_content = soup.find(id='dle-content')
                main_text = main_content.text if main_content else html
                
                game_date = "N/A"
                
                # 1. Try "Дата - DD-MM-YYYY"
                match = re.search(r'Дата\s*[:-]\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                if match:
                    d, m, y = match.group(1), match.group(2), match.group(3)
                    game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"
                
                # 2. Try "Тему отредактировал: ... - DD-MM-YYYY"
                if game_date == "N/A":
                    match_edit = re.search(r'Тему отредактировал:.*?\s*-\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                    if match_edit:
                        d, m, y = match_edit.group(1), match_edit.group(2), match_edit.group(3)
                        game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"
                
                # 3. Try "Загрузил: ... (DD MONTH YYYY)"
                if game_date == "N/A":
                    months_map = {
                        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
                        'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
                        'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
                    }
                    match_upload = re.search(r'Загрузил:.*?\(\s*([0-9]{1,2})\s*([а-я]+)\s*([0-9]{4})', main_text, re.IGNORECASE)
                    if match_upload:
                        d, m_name, y = match_upload.group(1), match_upload.group(2).lower(), match_upload.group(3)
                        if m_name in months_map:
                            game_date = f"{d.zfill(2)}.{months_map[m_name]}.{y}"

                # 4. Fallback to general "Обновлено" search
                if game_date == "N/A":
                    match_fallback = re.search(r'Обновлен[оа]?\s*[:-]\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                    if match_fallback:
                        d, m, y = match_fallback.group(1), match_fallback.group(2), match_fallback.group(3)
                        game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"
                
                logging.info(f"parse_single_game_page {url} -> title: {game_title}, date: {game_date}")
                return {"title": game_title, "date": game_date, "image_url": "N/A"}
            except TimeoutException:
                logging.warning(f"Cloudflare block or Timeout on single page {url} (attempt {attempt}/{MAX_RETRIES}): Element 'dle-content' not found (probably CAPTCHA).")
                self._reset_driver()
                if attempt == MAX_RETRIES:
                    return None
            except Exception as e:
                logging.error(f"Error parsing single page {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
                self._reset_driver()
                if attempt == MAX_RETRIES:
                    return None
                logging.info("Retrying with new WebDriver...")

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

parser_instance = GameParser()
