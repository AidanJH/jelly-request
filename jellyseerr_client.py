"""
Jellyseerr API client for Jelly Request application.
Handles all interactions with the Jellyseerr API including search and requests.
"""

import urllib.parse
import json
import time
from datetime import datetime
from config import JELLYSEERR_URL, API_KEY, IS_4K_REQUEST, DEBUG_MODE, logger
from utils import normalize_title, create_session_with_retries, decode_html_entities

class JellyseerrClient:
    """Client for interacting with Jellyseerr API."""
    
    def __init__(self):
        self.base_url = JELLYSEERR_URL
        self.headers = {
            "X-Api-Key": API_KEY, 
            "Connection": "close"
        }
        self.existing_requests = []
        self.skip_list = {}
    
    def search_media(self, media_name, max_retries=3):
        """
        Search for media (movie or tv) in Jellyseerr.
        
        Args:
            media_name (str): Name of the media to search for
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            dict or None: JSON response from Jellyseerr API
        """
        encoded_query = urllib.parse.quote(media_name, safe='')
        logger.debug(f"Searching Jellyseerr for '{media_name}' with encoded query: {encoded_query}")
        start_time = datetime.now()
        
        for attempt in range(1, max_retries + 1):
            try:
                with create_session_with_retries() as session:
                    logger.debug(f"Attempt {attempt} for '{media_name}': Sending request...")
                    res = session.get(
                        f"{self.base_url}/api/v1/search", 
                        params={"query": encoded_query}, 
                        headers=self.headers, 
                        timeout=(5, 15)
                    )
                    
                    logger.debug(f"Attempt {attempt} for '{media_name}': Response received with status {res.status_code}")
                    elapsed = (datetime.now() - start_time).total_seconds()
                    logger.debug(f"Jellyseerr search for '{media_name}' attempt {attempt} took {elapsed:.2f}s, headers: {res.headers}, response_size: {len(res.text)} bytes")
                    
                    if res.status_code != 200:
                        logger.error(f"Jellyseerr search failed for '{media_name}' on attempt {attempt}: {res.text}")
                        print(f"❌ Jellyseerr search failed for '{media_name}': {res.text}")
                        if attempt == max_retries:
                            logger.warning(f"Max retries reached for '{media_name}', skipping")
                            print(f"❌ Max retries reached for '{media_name}', skipping")
                            return None
                        continue
                    
                    logger.debug(f"Jellyseerr full response for '{media_name}': {res.text[:500]}")
                    if DEBUG_MODE == 'VERBOSE':
                        print(f"Jellyseerr response for '{media_name}': {res.text[:500]}")
                    return res.json()
                    
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.error(f"Error querying Jellyseerr for '{media_name}' on attempt {attempt} after {elapsed:.2f}s: {e}")
                print(f"❌ Error querying Jellyseerr for '{media_name}': {e}")
                if attempt == max_retries:
                    logger.warning(f"Max retries reached for '{media_name}', skipping")
                    print(f"❌ Max retries reached for '{media_name}', skipping")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
                
        return None
    
    # Alias for backward compatibility if needed, though we'll update calls
    search_movie = search_media

    def get_media_details(self, media_name, json_data, preferred_media_type=None):
        """
        Extract media details (movie or tv) from Jellyseerr search response.
        
        Args:
            media_name (str): Original media name being searched
            json_data (dict): JSON response from Jellyseerr search
            preferred_media_type (str, optional): "movie" or "tv" to prioritize
            
        Returns:
            tuple: (imdb_id, media_id, tmdb_id, media_type) or (None, None, None, None)
        """
        if not json_data or "results" not in json_data:
            logger.error(f"No results in Jellyseerr response for '{media_name}'")
            print(f"❌ No results in Jellyseerr response for '{media_name}'")
            return None, None, None, None
            
        normalized_query_name = normalize_title(media_name)
        results = json_data["results"]
        
        # Debug logging for results
        logger.debug(f"Processing {len(results)} results for '{media_name}'")
        
        # Helper to check a single result
        def check_result(result):
            media_type = result.get("mediaType")
            if media_type not in ["movie", "tv"]:
                return None
                
            # Movies have 'title', TV shows have 'name'
            title = result.get("title") or result.get("name") or ""
            original_title = result.get("originalTitle") or result.get("originalName") or ""
            
            # Decode HTML entities
            title = decode_html_entities(title)
            original_title = decode_html_entities(original_title)
            
            normalized_title = normalize_title(title)
            normalized_original = normalize_title(original_title)
            
            imdb_id = result.get("mediaInfo", {}).get("imdbId") or result.get("imdbId")
            media_id = result.get("id")
            tmdb_id = result.get("tmdbId", media_id)
            
            if not media_id or not title:
                return None
                
            # Check for match in title OR original title
            if normalized_query_name in normalized_title or normalized_query_name in normalized_original:
                logger.info(f"Found {media_type}: '{media_name}' matches '{title}' (Original: '{original_title}')")
                print(f"✅ Found {media_type}: '{media_name}' (Matches: '{title}')")
                return imdb_id, media_id, tmdb_id, media_type
            
            return None

        # 1. If preferred type is specified, try to find a match of that type first
        if preferred_media_type:
            for result in results:
                if result.get("mediaType") == preferred_media_type:
                    match = check_result(result)
                    if match:
                        return match
        
        # 2. If no match found yet (or no preference), check all results
        for result in results:
            # Skip if we already checked it (optimization: check if type matches preferred)
            if preferred_media_type and result.get("mediaType") == preferred_media_type:
                continue
                
            match = check_result(result)
            if match:
                return match
                    
        logger.warning(f"No matching media found in Jellyseerr for '{media_name}'")
        print(f"❌ No matching media found in Jellyseerr for '{media_name}'")
        
        # Debug: Print available titles in results to help user trace
        print(f"   🔎 Checked {len(results)} results in Jellyseerr:")
        for i, res in enumerate(results[:5]): # Print top 5
            m_type = res.get("mediaType")
            t = res.get("title") or res.get("name") or "N/A"
            ot = res.get("originalTitle") or res.get("originalName") or "N/A"
            print(f"      {i+1}. [{m_type}] {t} (Org: {ot})")
            
        return None, None, None, None
    
    def make_request(self, tmdb_id, media_id, media_type="movie"):
        """
        Make a request for media in Jellyseerr.
        
        Args:
            tmdb_id (int): TMDB ID of the media
            media_id (int): Media ID from Jellyseerr
            media_type (str): Type of media ("movie" or "tv")
            
        Returns:
            tuple: (success: bool, message: str)
        """
        payload = {
            "mediaType": media_type,
            "tmdbId": tmdb_id,
            "mediaId": media_id,
            "is4k": IS_4K_REQUEST
        }
        
        if media_type == "tv":
            # For TV shows, verify if we need to add specific parameters like 'seasons'
            # Defaulting to basic request for now.
            pass
        
        logger.debug(f"Making request for {media_type} (tmdbId: {tmdb_id}, mediaId: {media_id}), payload: {json.dumps(payload)}")
        
        try:
            with create_session_with_retries() as session:
                res = session.post(
                    f"{self.base_url}/api/v1/request", 
                    json=payload, 
                    headers=self.headers, 
                    timeout=(5, 15)
                )
                
                if res.status_code == 201:
                    logger.info(f"Successfully requested {media_type} (tmdbId: {tmdb_id}, mediaId: {media_id})")
                    print(f"✅ Requested {media_type} (tmdbId: {tmdb_id}, mediaId: {media_id})")
                    return True, res.text
                else:
                    logger.info(f"Request skipped for mediaId {media_id}: {res.text}")
                    print(f"ℹ️ Request skipped for mediaId {media_id}: {res.text}")
                    return False, res.text
                    
        except Exception as e:
            logger.error(f"Error requesting {media_type} (tmdbId: {tmdb_id}, mediaId: {media_id}): {e}")
            print(f"❌ Error requesting {media_type}: {e}")
            return False, str(e)

    def get_existing_requests(self, max_retries=3):
        """
        Fetch all existing requests from Jellyseerr to build skip list.
        
        Args:
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            list: List of existing requests or empty list on error
        """
        print("Fetching existing Jellyseerr requests...")
        logger.info("Fetching existing Jellyseerr requests for duplicate prevention")
        
        for attempt in range(1, max_retries + 1):
            try:
                with create_session_with_retries() as session:
                    # Fetch a large number of requests to ensure we get all of them
                    res = session.get(
                        f"{self.base_url}/api/v1/request",
                        params={"take": 1000},
                        headers=self.headers,
                        timeout=(5, 15)
                    )
                    
                    if res.status_code != 200:
                        logger.error(f"Failed to fetch requests on attempt {attempt}: {res.text}")
                        if attempt == max_retries:
                            logger.warning("Max retries reached for fetching requests, proceeding without duplicate prevention")
                            print("⚠️ Could not fetch existing requests, duplicate prevention disabled")
                            return []
                        continue
                    
                    data = res.json()
                    requests = data.get("results", [])
                    total_requests = len(requests)
                    
                    logger.info(f"Successfully fetched {total_requests} existing requests")
                    print(f"✅ Found {total_requests} existing requests in Jellyseerr")
                    
                    self.existing_requests = requests
                    self._build_skip_list()
                    
                    return requests
                    
            except Exception as e:
                logger.error(f"Error fetching existing requests on attempt {attempt}: {e}")
                if attempt == max_retries:
                    logger.warning("Max retries reached for fetching requests, proceeding without duplicate prevention")
                    print("⚠️ Error fetching existing requests, duplicate prevention disabled")
                    return []
                time.sleep(2 ** attempt)
        
        return []
    
    def _build_skip_list(self):
        """Build internal skip list from existing requests for fast lookups."""
        self.skip_list = {}
        skip_count = 0
        
        logger.debug(f"Processing {len(self.existing_requests)} existing requests for skip list")
        
        for i, request in enumerate(self.existing_requests):
            if i < 3:  # Log first 3 requests for debugging
                logger.debug(f"Request {i+1} structure: {request}")
            
            media = request.get("media", {})
            tmdb_id = media.get("tmdbId")
            imdb_id = media.get("imdbId")
            title = media.get("title", "Unknown")
            status = request.get("status", "unknown")
            media_type = request.get("type") or media.get("mediaType") or "movie"
            
            # Only skip requests that are not failed or declined
            if status not in ["DECLINED", "FAILED", 3]:  # Status 3 = declined
                if tmdb_id:
                    # Typed key
                    self.skip_list[f"tmdb_{media_type}_{tmdb_id}"] = {
                        "reason": f"Already requested (Status: {status})",
                        "request_id": request.get("id"),
                        "title": title,
                        "status": status,
                        "created": request.get("createdAt", ""),
                        "is_4k": request.get("is4k", False),
                        "media_type": media_type
                    }
                    # Legacy key for fallback
                    if media_type == "movie":
                         self.skip_list[f"tmdb_{tmdb_id}"] = self.skip_list[f"tmdb_{media_type}_{tmdb_id}"]
                    skip_count += 1
                
                if imdb_id:
                    self.skip_list[f"imdb_{imdb_id}"] = {
                        "reason": f"Already requested (Status: {status})",
                        "request_id": request.get("id"),
                        "title": title,
                        "status": status,
                        "created": request.get("createdAt", ""),
                        "is_4k": request.get("is4k", False),
                        "media_type": media_type
                    }
        
        print(f"✅ Skip list built: {skip_count} items to skip (requested/available)")
        logger.info(f"Built skip list with {skip_count} items to prevent duplicates")
    
    def check_media_availability(self, tmdb_id, media_type="movie", max_retries=3):
        """
        Check if media is already available in the library.
        
        Args:
            tmdb_id (int): TMDB ID of the media
            media_type (str): Type of media ("movie" or "tv")
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            dict or None: Availability info or None if not available/error
        """
        endpoint = "movie" if media_type == "movie" else "tv"
        
        for attempt in range(1, max_retries + 1):
            try:
                with create_session_with_retries() as session:
                    url = f"{self.base_url}/api/v1/{endpoint}/{tmdb_id}"
                    res = session.get(
                        url,
                        headers=self.headers,
                        timeout=(5, 15)
                    )
                    
                    if res.status_code == 200:
                        data = res.json()
                        media_info = data.get("mediaInfo", {})
                        status = media_info.get("status")
                        
                        # Check status. For TV shows, status might be different or partial?
                        # Status 5 = Available. 4 = Part Available.
                        if status == 5:  # Status 5 = Available
                            return {
                                "available": True,
                                "status": "AVAILABLE",
                                "title": data.get("title", "Unknown") if media_type == "movie" else data.get("name", "Unknown"),
                                "added_date": media_info.get("createdAt", "")
                            }
                    
                    return None
                    
            except Exception as e:
                logger.debug(f"Error checking availability for {media_type} tmdbId {tmdb_id} on attempt {attempt}: {e}")
                if attempt == max_retries:
                    return None
                time.sleep(1)
        
        return None
    
    def is_already_requested_or_available(self, tmdb_id, media_type="movie", imdb_id=None, title=None):
        """
        Check if media is already requested or available using multiple matching methods.
        
        Args:
            tmdb_id (int): TMDB ID of the media
            media_type (str): "movie" or "tv"
            imdb_id (str, optional): IMDb ID of the media
            title (str, optional): Title of the media for logging
            
        Returns:
            tuple: (should_skip: bool, skip_reason: str, skip_details: dict)
        """
        # Method 1: Check skip list (existing requests) by TMDB ID
        # Try typed key
        tmdb_key = f"tmdb_{media_type}_{tmdb_id}"
        if tmdb_key in self.skip_list:
            details = self.skip_list[tmdb_key]
            return True, details["reason"], details
            
        # Try legacy key (only for movies to avoid false positives)
        if media_type == "movie":
            tmdb_key_legacy = f"tmdb_{tmdb_id}"
            if tmdb_key_legacy in self.skip_list:
                details = self.skip_list[tmdb_key_legacy]
                return True, details["reason"], details
        
        # Method 2: Check skip list by IMDb ID (backup)
        if imdb_id and isinstance(imdb_id, str):
            imdb_key = f"imdb_{imdb_id}"
            if imdb_key in self.skip_list:
                details = self.skip_list[imdb_key]
                return True, details["reason"], details
        
        # Method 3: Check if already available in library
        availability = self.check_media_availability(tmdb_id, media_type)
        if availability and availability.get("available"):
            return True, "Already available in library", {
                "status": "AVAILABLE",
                "title": availability.get("title", title or "Unknown"),
                "added_date": availability.get("added_date", ""),
                "reason": "Already available in library (Status: AVAILABLE)"
            }
        
        # Media is not requested and not available - can be requested
        return False, f"New {media_type} not in system", {}
