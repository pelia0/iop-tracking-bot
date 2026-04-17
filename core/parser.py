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

    def parse_games_on_page(self, base_url='https://island-of-pleasure.site/games/', pages_to_check=20, stop_date=None):
        """Synchronous blocking function for parsing several game pages.
        Retries are now handled per-page to avoid restarting from page 1 on failure.
        """
        all_games = {}
        import time
        import random
        from datetime import datetime
        
        for page in range(1, pages_to_check + 1):
            page_url = base_url if page == 1 else f"{base_url}page/{page}/"
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
                    
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content_div = soup.find('div', id='dle-content')
                    if not content_div:
                        logging.warning(f"Main block 'dle-content' not found on page {page}.")
                        # Depending on structure, this might mean we should retry or skip
                        page_parsed_successfully = True # Avoid infinite retries for empty pages
                        break

                    game_blocks = content_div.find_all('div', class_=lambda c: c and 'shortstory-in' in c and 'story_news' in c)
                    
                    for block in game_blocks:
                        title_element = block.find('h4', class_='short-link').find('a')
                        if not title_element: continue

                        game_url = title_element['href']
                        game_title = title_element.get('title', title_element.text.strip())
                        
                        date_element = block.find('div', class_='update_date')
                        game_date_str = date_element.text.strip() if date_element else "N/A"
                        
                        # Early exit logic: if game date < stop_date, we found historical entries
                        if stop_date and game_date_str != "N/A":
                            try:
                                game_dt = datetime.strptime(game_date_str, "%d.%m.%Y")
                                if game_dt < stop_date:
                                    logging.info(f"Stopping scan: encountered date {game_date_str} < stop_date {stop_date.strftime('%d.%m.%Y')}")
                                    return all_games
                            except ValueError:
                                pass

                        image_element = block.find('img')
                        game_image_url = "N/A"
                        if image_element:
                            img_src = image_element['src']
                            game_image_url = f'https://island-of-pleasure.site{img_src}' if img_src.startswith('/') else img_src

                        all_games[game_url] = {
                            "title": game_title,
                            "date": game_date_str,
                            "image_url": game_image_url
                        }
                    
                    page_parsed_successfully = True
                    break # Success on this page, break attempt loop
                except Exception as e:
                    logging.error(f"Error parsing page {page} (attempt {attempt}/{MAX_RETRIES}): {e}")
                    self._reset_driver()
                    if attempt == MAX_RETRIES:
                        logging.error(f"Failed to parse page {page} after {MAX_RETRIES} attempts.")
                        raise e
                    logging.info("Retrying current page with new WebDriver...")
            
            if not page_parsed_successfully:
                break # Should not happen due to raise e above, but for safety.

        return all_games

    def parse_single_game_page(self, url: str):
        """Synchronous function for parsing a single game page (with retry)."""
        import re
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
                match = re.search(r'Обновлен[оа]?\s*:?\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})', html, re.IGNORECASE)
                game_date = match.group(1) if match else "N/A"
                
                logging.info(f"parse_single_game_page {url} -> title: {game_title}, date: {game_date}")
                return {"title": game_title, "date": game_date, "image_url": "N/A"} # image_url just in case
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
