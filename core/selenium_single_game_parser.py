import logging
import re
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from core.base_parser import SingleGameParser
from core.config import CONTENT_ID, MAX_RETRIES, NO_DATE, NO_IMAGE
from core.webdriver_manager import WebDriverManager


class SeleniumSingleGameParser(SingleGameParser):
    """Parser for individual game pages using Selenium."""

    def __init__(self, webdriver_manager: WebDriverManager | None = None):
        self.webdriver_manager = webdriver_manager or WebDriverManager()

    def parse_single_game_page(self, url: str) -> dict[str, str] | None:
        """Parse single game page."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                driver = self.webdriver_manager.get_driver()
                driver.get(url)
                wait = WebDriverWait(driver, 45)  # Extended wait for Cloudflare challenge
                wait.until(EC.presence_of_element_located((By.ID, CONTENT_ID)))

                game_title = driver.title
                if "» 18+ Island of Pleasure!" in game_title:
                    game_title = game_title.split("»")[0].strip()

                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                main_content = soup.find(id=CONTENT_ID)
                main_text = main_content.text if main_content else html

                game_date = NO_DATE

                # 1. Try "Дата - DD-MM-YYYY"
                match = re.search(r'Дата\s*[:-]\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                if match:
                    d, m, y = match.group(1), match.group(2), match.group(3)
                    game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"

                # 2. Try "Тему отредактировал: ... - DD-MM-YYYY"
                if game_date == NO_DATE:
                    match_edit = re.search(r'Тему отредактировал:.*?\s*-\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                    if match_edit:
                        d, m, y = match_edit.group(1), match_edit.group(2), match_edit.group(3)
                        game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"

                # 3. Try "Загрузил: ... (DD MONTH YYYY)"
                if game_date == NO_DATE:
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
                if game_date == NO_DATE:
                    match_fallback = re.search(r'Обновлен[оа]?\s*[:-]\s*([0-9]{1,2})[.-]([0-9]{1,2})[.-]([0-9]{4})', main_text, re.IGNORECASE)
                    if match_fallback:
                        d, m, y = match_fallback.group(1), match_fallback.group(2), match_fallback.group(3)
                        game_date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"

                logging.info(f"parse_single_game_page {url} -> title: {game_title}, date: {game_date}")
                return {"title": game_title, "date": game_date, "image_url": NO_IMAGE}
            except Exception as e:
                logging.error(f"Error parsing single page {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
                self.webdriver_manager.quit()
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"Failed to parse single page {url} after {MAX_RETRIES} attempts. Last error: {e}")
                logging.info("Retrying with new WebDriver...")

    def quit(self) -> None:
        """Clean up resources."""
        self.webdriver_manager.quit()