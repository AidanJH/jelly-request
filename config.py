"""
Configuration management for Jelly Request application.
Handles environment variables, logging setup, and application settings.
"""

import os
import sys
import json
import logging

# === ENVIRONMENT VARIABLES ===
JELLYSEERR_URL = os.environ.get('JELLYSEERR_URL', 'http://192.168.0.29:5054')
API_KEY = os.environ.get('API_KEY', 'MTY3MzkzMTU4MjI1NzNmZWQ4OGQ1LWQ1NDMtNDY0OC1hYzI3LWQ3ODAyMTM5OWUwNyk=')

# IMDB_URL supports any IMDb list URL (Legacy support)
_LEGACY_IMDB_URL = os.environ.get('IMDB_URL', 'https://www.imdb.com/chart/moviemeter')

# LIST_URLS supports multiple IMDb list URLs (Legacy/General support)
LIST_URLS_ENV = os.environ.get('LIST_URLS', '')

# Type-specific lists
MOVIE_LISTS_ENV = os.environ.get('MOVIE_LISTS', '')
TV_LISTS_ENV = os.environ.get('TV_LISTS', '')
ANIME_LISTS_ENV = os.environ.get('ANIME_LISTS', '')

def parse_list_urls(env_urls, legacy_url=None):
    """Parse environment variable for lists (JSON or comma-separated)."""
    if env_urls:
        try:
            # Try parsing as JSON first
            return json.loads(env_urls)
        except json.JSONDecodeError:
            # Fallback to comma-separated
            return [url.strip() for url in env_urls.split(',') if url.strip()]
    
    # Fallback to legacy URL if provided and env_urls is empty
    return [legacy_url] if legacy_url else []

# Parse all list configurations
IMDB_URLS = parse_list_urls(LIST_URLS_ENV, _LEGACY_IMDB_URL)
MOVIE_LISTS = parse_list_urls(MOVIE_LISTS_ENV)
TV_LISTS = parse_list_urls(TV_LISTS_ENV)
ANIME_LISTS = parse_list_urls(ANIME_LISTS_ENV)

MOVIE_LIMIT = int(os.environ.get('MOVIE_LIMIT', 50))
RUN_INTERVAL_DAYS = int(os.environ.get('RUN_INTERVAL_DAYS', 7))
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'SIMPLE').upper()
IS_4K_REQUEST = os.environ.get('IS_4K_REQUEST', 'false').lower() == 'true'
# Delay (in seconds) to wait after each new request is made. This throttles how fast
# Seerr fires auto-approval notifications (e.g. Discord webhooks), avoiding 429 rate limits.
REQUEST_DELAY_SECONDS = float(os.environ.get('REQUEST_DELAY_SECONDS', 5))
# Logging configuration
# In Docker, we map /logs. Locally, we'll use a local logs directory if /logs isn't writable/existent
if os.path.exists('/logs'):
    LOG_FILE = "/logs/imdb_jellyseerr.log"
else:
    os.makedirs('logs', exist_ok=True)
    LOG_FILE = "logs/imdb_jellyseerr.log"

# === LOGGING SETUP ===
def setup_logging():
    """Configure logging for the application."""
    logging_level = logging.DEBUG if DEBUG_MODE == 'VERBOSE' else logging.INFO
    logger = logging.getLogger(__name__)
    logger.setLevel(logging_level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    # Console handler to duplicate logs to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

    return logger

# Initialize logger
logger = setup_logging()
