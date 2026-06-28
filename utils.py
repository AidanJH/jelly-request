"""
Utility functions for Jelly Request application.
Contains common helpers, HTTP session management, and retry logic.
"""

import re
import html
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def decode_html_entities(text):
    """Decode HTML entities like &amp; to & and &quot; to "."""
    if not text:
        return text
    return html.unescape(text)

def normalize_title(title):
    """Normalize titles by removing special characters, spaces, and numbers."""
    if not title:
        return ""
    # First decode HTML entities
    title = decode_html_entities(title)
    # Remove special characters, keep letters and numbers
    title = re.sub(r'[^\w\s]', '', title.lower())
    # Remove extra spaces
    title = ' '.join(title.split())
    return title

def strip_sequel_suffix(title):
    """
    Strip common sequel/season markers from a title to recover the base series name.

    Many MAL titles are seasonal (e.g. "Grand Blue Season 3", "Youjo Senki II",
    "Clevatess II: Majuu no Ou ...") but TMDB/Seerr only index the base series, so a
    verbatim search returns no results. This produces the base title for a fallback search.

    Examples:
        "Grand Blue Season 3"            -> "Grand Blue"
        "You Shou Yan 6th Season"        -> "You Shou Yan"
        "Youjo Senki II"                 -> "Youjo Senki"
        "Clevatess II: Majuu no Ou ..."  -> "Clevatess"
        "Bungou Stray Dogs Wan! 2"       -> "Bungou Stray Dogs Wan!"
    """
    if not title:
        return ""

    cleaned = title
    # Remove explicit season/part/cour markers anywhere in the string
    season_patterns = [
        r'\b\d+(?:st|nd|rd|th)\s+season\b',
        r'\bseason\s+\d+\b',
        r'\b\d+(?:st|nd|rd|th)\s+cour\b',
        r'\bcour\s+\d+\b',
        r'\bpart\s+\d+\b',
        r'\bfinal\s+season\b',
    ]
    for pattern in season_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Remove a trailing roman numeral (II-X) plus anything after it (often ": subtitle")
    cleaned = re.sub(r'\s+(?:II|III|IV|V|VI|VII|VIII|IX|X)\b.*$', '', cleaned)
    # Remove a trailing standalone arabic number (e.g. "... 2")
    cleaned = re.sub(r'\s+\d+\s*$', '', cleaned)
    # Trim leftover separators/whitespace
    cleaned = re.sub(r'[\s:\-\u2013,]+$', '', cleaned)
    cleaned = ' '.join(cleaned.split()).strip()
    return cleaned

def generate_search_candidates(title):
    """
    Build an ordered, de-duplicated list of search queries to try for a title.

    The original title is always tried first; a sequel/season-stripped variant is
    appended as a fallback so seasonal anime can match their base TMDB entry.
    """
    candidates = [title]
    stripped = strip_sequel_suffix(title)
    if stripped and len(stripped) >= 2 and stripped.lower() != title.lower():
        candidates.append(stripped)
    return candidates

def create_session_with_retries():
    """Create a requests session with retry configuration."""
    session = requests.Session()
    retries = Retry(
        total=3, 
        backoff_factor=1, 
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session
