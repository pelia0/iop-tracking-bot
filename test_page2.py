import sys
import time
sys.path.append('.')
from core.parser import parser_instance
from bs4 import BeautifulSoup

parser_instance.initialize()
driver = parser_instance.get_driver()

print("Loading page 1")
driver.get("https://island-of-pleasure.site/games/")
time.sleep(3)

print("Loading page 2")
driver.get("https://island-of-pleasure.site/games/page/2/")
time.sleep(10)

soup = BeautifulSoup(driver.page_source, 'html.parser')
content = soup.find('div', id='dle-content')
if content:
    print("dle-content found on page 2!")
else:
    print("dle-content NOT found on page 2. Saving error.html")
    with open('error.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)

parser_instance.quit()
