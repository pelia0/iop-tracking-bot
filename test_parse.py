import sys
import time
from bs4 import BeautifulSoup

sys.path.append('.')
from core.parser import parser_instance

def dump_pages():
    print("Initializing...")
    parser_instance.initialize()
    driver = parser_instance.get_driver()
    
    print("Loading games list...")
    driver.get("https://island-of-pleasure.site/games/")
    time.sleep(3)
    soup1 = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Extract navigation
    nav = soup1.find('div', class_='navigation')
    pages_str = ""
    if nav:
        pages_str = str(nav)
    else:
        for a in soup1.find_all('a'):
            if 'page' in a.get('href', ''):
                pages_str += str(a) + '\n'
                
    with open('pagination.html', 'w', encoding='utf-8') as f:
        f.write(pages_str)
        
    print("Loading single game...")
    driver.get("https://island-of-pleasure.site/15960-fashion-business-episode-1-v01-2018-rus-eng-ger-renpy-macos-demo-.html")
    time.sleep(3)
    soup2 = BeautifulSoup(driver.page_source, 'html.parser')
    
    with open('game_page.html', 'w', encoding='utf-8') as f:
        full_story = soup2.find('div', id='dle-content')
        if full_story:
            f.write(str(full_story))
        else:
            print("dle-content not found on game page.")
            
    print("Done")
    parser_instance.quit()

if __name__ == '__main__':
    dump_pages()
