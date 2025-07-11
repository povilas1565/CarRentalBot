import json
from pathlib import Path

POPULAR_CITIES_PATH = Path(__file__).parent / "popular_cities.json"

with open(POPULAR_CITIES_PATH, "r", encoding="utf-8") as f:
    POPULAR_CITIES = json.load(f)