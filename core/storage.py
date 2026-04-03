import os
import json

TRACKED_GAMES_FILE = "tracked_games.json"

def load_tracked_games():
    try:
        with open(TRACKED_GAMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_tracked_games(data):
    with open(TRACKED_GAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
