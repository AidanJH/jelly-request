import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add current directory to path so we can import main
sys.path.append(os.getcwd())

from main import aggregate_media, process_movies

class TestMediaAggregation(unittest.TestCase):
    
    @patch('main.scrape_imdb_top_movies')
    @patch('main.scrape_mal_season')
    def test_aggregation_all_lists(self, mock_mal, mock_imdb):
        """Test 1: The system correctly aggregates media from MOVIE_LISTS, TV_LISTS, ANIME_LISTS, and IMDB_URLS."""
        # Setup mocks
        mock_imdb.side_effect = lambda url: [f"Item from {url}"]
        mock_mal.side_effect = lambda url: [f"Item from {url}"]
        
        movie_lists = ["http://movie.com"]
        tv_lists = ["http://tv.com"]
        anime_lists = ["http://myanimelist.net/season"]
        imdb_urls = ["http://legacy.com"]
        
        result = aggregate_media(movie_lists, tv_lists, anime_lists, imdb_urls)
        
        # Verify items are present
        titles = [item['title'] for item in result]
        self.assertIn("Item from http://movie.com", titles)
        self.assertIn("Item from http://tv.com", titles)
        self.assertIn("Item from http://myanimelist.net/season", titles)
        self.assertIn("Item from http://legacy.com", titles)
        
    @patch('main.scrape_imdb_top_movies')
    def test_movie_type_assignment(self, mock_imdb):
        """Test 2: Media scraped from MOVIE_LISTS are correctly assigned the 'movie' type."""
        mock_imdb.return_value = ["Movie Title"]
        
        result = aggregate_media(["http://movie.com"], [], [], [])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'movie')
        
    @patch('main.scrape_imdb_top_movies')
    def test_tv_type_assignment(self, mock_imdb):
        """Test 3: Media scraped from TV_LISTS are correctly assigned the 'tv' type."""
        mock_imdb.return_value = ["TV Show"]
        
        result = aggregate_media([], ["http://tv.com"], [], [])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'tv')
        
    @patch('main.scrape_mal_season')
    def test_anime_type_assignment(self, mock_mal):
        """Test 4: Media scraped from ANIME_LISTS are correctly assigned the 'tv' type."""
        mock_mal.return_value = ["Anime Show"]
        
        result = aggregate_media([], [], ["http://myanimelist.net/season"], [])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'tv')
        
    @patch('main.scrape_imdb_top_movies')
    def test_forced_type_override(self, mock_imdb):
        """Test 5: When a 'forced_type' is specified in a list group, it correctly overrides the scraper's detected type."""
        # Scenario: A URL is processed as a TV list (forced_type="tv"), 
        # but the scraper (IMDb) defaults to "movie".
        # We want to ensure "tv" is used.
        
        mock_imdb.return_value = ["Forced TV Show"]
        
        # Passing an IMDb-like URL to TV_LISTS which enforces "tv"
        result = aggregate_media([], ["http://imdb.com/list"], [], [])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], "Forced TV Show")
        self.assertEqual(result[0]['type'], 'tv')

class TestJellyseerrInteraction(unittest.TestCase):

    def test_request_format(self):
        """Test 6: Ensure that a request is sent to jellyseerr in the correct format, using the correct data."""
        mock_client = MagicMock()
        
        # Setup mock behavior
        # 1. search_media found result
        mock_client.search_media.return_value = {"results": [{"id": 1}]}
        
        # 2. get_media_details returns (imdb_id, media_id, tmdb_id, media_type)
        # simulating a movie that exists in TMDB (id=123) but not yet in Jellyseerr (media_id=None)
        mock_client.get_media_details.return_value = ("tt1234567", None, 123, "movie")
        
        # 3. is_already_requested_or_available returns False (should request)
        mock_client.is_already_requested_or_available.return_value = (False, "New", {})
        
        # 4. make_request returns Success
        mock_client.make_request.return_value = (True, "Success")
        
        media_items = [{"title": "Test Movie", "type": "movie"}]
        
        process_movies(mock_client, media_items)
        
        # Verify make_request was called with correct arguments
        # make_request(tmdb_id, media_id, media_type)
        mock_client.make_request.assert_called_once_with(123, None, "movie")
        
        # Also verify the flow leading up to it
        mock_client.search_media.assert_called_with("Test Movie")
        mock_client.get_media_details.assert_called_with("Test Movie", {"results": [{"id": 1}]}, "movie")
        mock_client.is_already_requested_or_available.assert_called_with(123, "movie", "tt1234567", "Test Movie")

if __name__ == '__main__':
    unittest.main()
