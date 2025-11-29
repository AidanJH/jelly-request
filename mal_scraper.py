"""
MyAnimeList scraping functionality for Jelly Request application.
Handles web scraping of MyAnimeList's seasonal anime chart.
"""

import requests
from bs4 import BeautifulSoup
from config import MOVIE_LIMIT, logger
from utils import normalize_title, decode_html_entities

def scrape_mal_season(url, limit=MOVIE_LIMIT):
    """
    Scrape top anime from MyAnimeList's seasonal chart.
    
    Args:
        url (str): MyAnimeList seasonal URL (e.g. https://myanimelist.net/anime/season)
        limit (int): Maximum number of anime to scrape
        
    Returns:
        list: List of anime titles
    """
    try:
        # MAL is strict with User-Agents, use a realistic one
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        logger.info(f"Scraping MAL URL: {url}")
        response = requests.get(url, headers=headers, timeout=(10, 20))
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch MAL page: {response.status_code}")
            print(f"❌ Failed to fetch MAL page: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract anime titles
        # MAL seasonal page structure: .seasonal-anime .h2_anime_title a
        anime_elements = soup.select(".seasonal-anime .h2_anime_title a")
        
        if not anime_elements:
            # Fallback for other list views or layout changes
            anime_elements = soup.select(".link-title")
            
        logger.debug(f"Found {len(anime_elements)} anime elements before slicing")
        
        anime_elements = anime_elements[:limit]
        if not anime_elements:
            logger.error("No anime titles found with selector")
            print(f"❌ No anime titles found with selector")
            return []
    
        movies = []
        seen_titles = set()
        
        for element in anime_elements:
            title = element.get_text().strip()
            if title:
                title = decode_html_entities(title)
                norm_title = normalize_title(title)
                
                if norm_title and norm_title not in seen_titles:
                    movies.append(title)
                    seen_titles.add(norm_title)
                    
        logger.info(f"Scraped {len(movies)} unique anime from MAL: {movies}")
        print(f"Scraped {len(movies)} unique anime from MAL")
        return movies
        
    except Exception as e:
        logger.error(f"Error scraping MAL: {e}")
        print(f"❌ Error scraping MAL: {e}")
        return []
