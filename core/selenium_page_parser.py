import logging
import random
import time
from datetime import datetime
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from core.base_parser import PageParser
from core.config import BASE_URL, CONTENT_ID, DATE_FORMAT, IGNORED_URLS, MAX_RETRIES, NEXT_BTN_SELECTOR, NO_DATE, NO_IMAGE, SITE_ORIGIN
from core.utils import normalize_game_url
from core.webdriver_manager import WebDriverManager


class SeleniumPageParser(PageParser):
    """Parser for game listing pages using Selenium."""

    def __init__(self, webdriver_manager: WebDriverManager | None = None):
        self.webdriver_manager = webdriver_manager or WebDriverManager()

    def parse_games_on_page(self, pages_to_check: int = 20, stop_date: Any = None) -> tuple[dict[str, dict[str, str]], int]:
        """Synchronous blocking function for parsing several game pages."""
        all_games = {}
        base_url = BASE_URL
        last_scanned_page = 0

        for page in range(1, pages_to_check + 1):
            page_url = base_url if page == 1 else f"{base_url}page/{page}/"
            logging.info(f"--- Processing page {page} ---")
            last_scanned_page = page

            page_parsed_successfully = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    driver = self.webdriver_manager.get_driver()

                    if page == 1:
                        logging.info(f"Loading {page_url} (initial page, attempt {attempt}/{MAX_RETRIES})...")
                        driver.get(page_url)
                    else:
                        delay = random.uniform(3.0, 6.0)
                        logging.info(f"Waiting {delay:.1f} sec before clicking next page {page} (anti-spam, attempt {attempt})...")
                        time.sleep(delay)

                        try:
                            self._dismiss_popups(driver)
                            next_btn_selector = NEXT_BTN_SELECTOR
                            wait = WebDriverWait(driver, 10)
                            next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_btn_selector)))

                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                            time.sleep(1)

                            logging.info(f"Clicking 'Next' button to navigate to page {page}...")
                            try:
                                next_btn.click()
                            except Exception as click_error:
                                logging.warning(f"Regular click failed: {click_error}. Trying JavaScript click...")
                                try:
                                    driver.execute_script("arguments[0].click();", next_btn)
                                    logging.info("JavaScript click succeeded")
                                except Exception as js_error:
                                    logging.warning(f"JavaScript click also failed: {js_error}")
                                    raise click_error
                        except Exception as click_err:
                            logging.warning(f"Failed to click next button: {click_err}. Falling back to direct URL navigation.")
                            driver.get(page_url)

                    logging.info(f"Selenium waiting for content load (page {page})...")
                    wait = WebDriverWait(driver, 30)
                    wait.until(EC.presence_of_element_located((By.ID, CONTENT_ID)))

                    time.sleep(2)  # Manual delay for AJAX content stability

                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')

                    content = soup.find(id=CONTENT_ID)
                    if not content:
                        raise ValueError(f"Element '{CONTENT_ID}' not found on page.")

                    game_blocks = content.find_all('div', class_='shortstory-in')
                    logging.info(f"Found {len(game_blocks)} articles on page {page}.")

                    for block in game_blocks:
                        h4_element = block.find('h4', class_='short-link')
                        if not h4_element:
                            continue
                        title_element = h4_element.find('a')
                        if not title_element:
                            continue

                        raw_game_url = str(title_element['href'])
                        game_url = normalize_game_url(raw_game_url)
                        if game_url in IGNORED_URLS:
                            continue

                        game_title = title_element.get('title', title_element.text.strip())

                        date_element = block.find('div', class_='update_date')
                        game_date_str = date_element.text.strip() if date_element else NO_DATE

                        # Early exit logic
                        if stop_date and game_date_str != NO_DATE:
                            try:
                                game_date = datetime.strptime(game_date_str, DATE_FORMAT)
                                if game_date.date() < stop_date.date():
                                    logging.info(f"Stopping scan: encountered an older date {game_date.strftime('%d.%m.%Y')} (last full check was on {stop_date.strftime('%d.%m.%Y')})")
                                    return all_games, last_scanned_page
                            except (ValueError, TypeError):
                                pass

                        image_element = block.find('img')
                        if image_element and 'src' in image_element.attrs:
                            src = image_element['src']
                            if isinstance(src, list):
                                src = src[0] if src else ""
                            image_url = str(src)
                        else:
                            image_url = NO_IMAGE
                        if image_url != NO_IMAGE and not image_url.startswith('http'):
                            image_url = SITE_ORIGIN + image_url

                        all_games[game_url] = {
                            'title': game_title,
                            'date': game_date_str,
                            'image_url': image_url
                        }

                    page_parsed_successfully = True
                    break  # Success on this page

                except Exception as e:
                    logging.error(f"Error parsing page {page} (attempt {attempt}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES:
                        logging.warning("Resetting WebDriver after error...")
                        self.webdriver_manager.quit()
                        time.sleep(2)
                        logging.info("Retrying current page with new WebDriver...")
                    else:
                        logging.error(f"Max retries reached for page {page}. Skipping.")
                        raise RuntimeError(f"Failed to parse page {page} after {MAX_RETRIES} attempts. Last error: {e}")

            if not page_parsed_successfully:
                break

        return all_games, last_scanned_page

    def quit(self) -> None:
        """Clean up resources."""
        self.webdriver_manager.quit()

    def _dismiss_popups(self, driver: Any) -> None:
        """Try to dismiss common popup elements that might block clicks."""
        try:
            popup_selectors = [
                "button[class*='close']",
                "button[class*='dismiss']",
                ".popup-close",
                ".modal-close",
                ".close-button",
                "[data-dismiss='modal']",
                ".fa-times",
                ".fa-close",
                ".overlay",
                ".popup-overlay",
                ".modal-backdrop",
                ".cookie-banner .close",
                ".newsletter-popup .close",
                ".subscription-popup .close"
            ]

            for selector in popup_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            driver.execute_script("arguments[0].click();", element)
                            logging.info(f"Dismissed popup with selector: {selector}")
                            time.sleep(0.5)
                            break
                except Exception:
                    continue

            # Try to click anywhere on overlay to dismiss
            try:
                overlays = driver.find_elements(By.CSS_SELECTOR, ".popup-overlay, .modal-backdrop, .overlay")
                for overlay in overlays:
                    if overlay.is_displayed():
                        driver.execute_script("arguments[0].click();", overlay)
                        logging.info("Clicked overlay to dismiss popup")
                        time.sleep(0.5)
                        break
            except Exception:
                pass

        except Exception as e:
            logging.debug(f"Popup dismissal attempt failed: {e}")