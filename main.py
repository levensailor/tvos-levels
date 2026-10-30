"""Uvicorn entry point: `uv run uvicorn main:app --reload --port "${PORT:-8000}"`."""

from dotenv import load_dotenv

from level_bridge.api import create_app
from level_bridge.logging_config import configure_logging
from level_bridge.settings import Settings

load_dotenv()
configure_logging()
app = create_app(Settings.from_env())
