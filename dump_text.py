from bs4 import BeautifulSoup
import re

with open('game_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

text = soup.get_text(separator='\n', strip=True)

for i, line in enumerate(text.split('\n')):
    print(str(i) + ': ' + line)
