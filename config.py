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

# LIST_URLS supports multiple IMDb list URLs
# Can be a comma-separated string or a JSON array
# Examples:
# - "https://www.imdb.com/chart/moviemeter,https://www.imdb.com/chart/top"
# - '["https://www.imdb.com/chart/moviemeter", "https://www.imdb.com/chart/top"]'
LIST_URLS_ENV = os.environ.get('LIST_URLS', '')

def parse_list_urls(env_urls, legacy_url):
    """Parse LIST_URLS or fall back to IMDB_URL."""
    if env_urls:
        try:
            # Try parsing as JSON first
            return json.loads(env_urls)
        except json.JSONDecodeError:
            # Fallback to comma-separated
            return [url.strip() for url in env_urls.split(',') if url.strip()]
    
    # Fallback to legacy IMDB_URL if LIST_URLS is not set
    return [legacy_url] if legacy_url else []

IMDB_URLS = parse_list_urls(LIST_URLS_ENV, _LEGACY_IMDB_URL)

MOVIE_LIMIT = int(os.environ.get('MOVIE_LIMIT', 50))
RUN_INTERVAL_DAYS = int(os.environ.get('RUN_INTERVAL_DAYS', 7))
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'SIMPLE').upper()
IS_4K_REQUEST = os.environ.get('IS_4K_REQUEST', 'true').lower() == 'true'
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
