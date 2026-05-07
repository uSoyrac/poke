from __future__ import annotations

from pathlib import Path


APP_NAME = "Champion Poker Training OS"
APP_VERSION = "0.1.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "sample_data"
DB_PATH = DATA_DIR / "champion_training.sqlite3"
SCHEMA_PATH = APP_DIR / "db" / "schema.sql"
THEME_PATH = APP_DIR / "ui" / "theme" / "dark_flat.qss"

DEFAULT_AI_PROVIDER = "Offline mock coach"
SOURCE_CONFIDENCE = "Mock/demo solver"

