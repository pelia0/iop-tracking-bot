import os
import json
import tempfile
import shutil
import logging

TRACKED_GAMES_FILE = "tracked_games.json"

def load_tracked_games():
    try:
        with open(TRACKED_GAMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_tracked_games(data):
    if os.path.exists(TRACKED_GAMES_FILE):
        try:
            shutil.copy2(TRACKED_GAMES_FILE, TRACKED_GAMES_FILE + '.bak')
        except Exception as e:
            logging.error(f"Не удалось создать бекап: {e}")
            
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(TRACKED_GAMES_FILE)) or '.', suffix='.json')
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, TRACKED_GAMES_FILE)
    except Exception as e:
        os.unlink(tmp_path)
        logging.error(f"Ошибка при сохранении json: {e}")
        raise
