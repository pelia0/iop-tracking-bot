import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options


class WebDriverManager:
    """Manages Chrome WebDriver instance."""

    def __init__(self):
        self.driver: webdriver.Chrome | None = None

    def create_driver(self) -> webdriver.Chrome:
        """Creates a new Chrome WebDriver instance."""

        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        )

        system_chromedriver = "/usr/bin/chromedriver"
        if os.path.exists(system_chromedriver):
            service = ChromeService(executable_path=system_chromedriver)
        else:
            service = ChromeService()
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def get_driver(self) -> webdriver.Chrome:
        """Get or create driver instance."""
        if self.driver:
            try:
                _ = self.driver.title  # Check if driver is alive
                return self.driver
            except Exception:
                logging.warning("Existing WebDriver is unresponsive, recreating...")
                self.quit()

        self.driver = self.create_driver()
        return self.driver

    def quit(self) -> None:
        """Quit the driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None