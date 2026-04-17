import sys
import time
from bs4 import BeautifulSoup
sys.path.append('.')
from core.parser import parser_instance

parser_instance.initialize()
driver = parser_instance.get_driver()

driver.get("https://island-of-pleasure.site/15960-fashion-business-episode-1-v01-2018-rus-eng-ger-renpy-macos-demo-.html")
time.sleep(3)
with open('game_page.html', 'w', encoding='utf-8') as f:
    f.write(driver.page_source)

parser_instance.quit()
