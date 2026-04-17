with open('game_page.html', 'r', encoding='utf-8') as f:
    html = f.read()
import re
# look for date pattern
matches = re.finditer(r'([0-9]{2}\.[0-9]{2}\.[0-9]{4})', html)
for match in matches:
    start = max(0, match.start() - 50)
    end = min(len(html), match.end() + 50)
    print("MATCH:", html[start:end])
