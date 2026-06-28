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
        logger.info(f"Searching Jellyseerr for '{media_name}' with encoded query: {encoded_query}")
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
                    
                    logger.info(f"Jellyseerr full response for '{media_name}': {res.text[:500]}")
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

    def get_full_media_details(self, media_id, media_type="movie"):
        """
        Fetch full media details from Jellyseerr including alternative titles/keywords.
        
        Args:
            media_id (int): Media ID
            media_type (str): "movie" or "tv"
            
        Returns:
            dict or None: Full details JSON
        """
        endpoint = "movie" if media_type == "movie" else "tv"
        try:
            with create_session_with_retries() as session:
                # Fetch details
                res = session.get(
                    f"{self.base_url}/api/v1/{endpoint}/{media_id}", 
                    headers=self.headers,
                    timeout=(5, 15)
                )
                if res.status_code == 200:
                    return res.json()
                else:
                    logger.warning(f"Failed to fetch full details for {media_type} {media_id}: {res.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching full details for {media_type} {media_id}: {e}")
            return None

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
        logger.info(f"Processing {len(results)} results for '{media_name}'")
        
        # Helper to check a single result
        def check_result(result, preferred_check=False, is_top_result=False):
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
            
            if DEBUG_MODE == 'VERBOSE' or True: # Enforce logging
                logger.info(f"Checking result - Type: {media_type}, Title: '{title}', Org: '{original_title}'")
                logger.info(f"Normalized Query: '{normalized_query_name}' vs Title: '{normalized_title}' vs Org: '{normalized_original}'")

            imdb_id = result.get("mediaInfo", {}).get("imdbId") or result.get("imdbId")
            # Jellyseerr internal ID is ONLY in mediaInfo. 'id' is TMDB ID.
            # If mediaInfo is missing, the item is not in Jellyseerr DB yet.
            jellyseerr_id = result.get("mediaInfo", {}).get("id")
            
            # TMDB ID is usually 'id' in search results
            tmdb_id = result.get("id")
            # Some results might have explicit tmdbId
            if result.get("tmdbId"):
                tmdb_id = result.get("tmdbId")
            
            if not tmdb_id or not title:
                return None
                
            # Check for match in title OR original title
            # Use substring matching, but verify that at least the normalized query is "in" the target title
            # For Japanese titles, sometimes the Romanji is slightly different.
            if normalized_query_name in normalized_title or normalized_query_name in normalized_original:
                logger.info(f"Found {media_type}: '{media_name}' matches '{title}' (Original: '{original_title}')")
                print(f"✅ Found {media_type}: '{media_name}' (Matches: '{title}')")
                return imdb_id, jellyseerr_id, tmdb_id, media_type
            
            # Reverse check: if the result title is inside the query name (sometimes query is longer or has extra info)
            if normalized_title and len(normalized_title) > 5 and normalized_title in normalized_query_name:
                logger.info(f"Found {media_type}: '{media_name}' matches '{title}' (Reverse match)")
                print(f"✅ Found {media_type}: '{media_name}' (Reverse Match: '{title}')")
                return imdb_id, jellyseerr_id, tmdb_id, media_type
            
            # DEEP CHECK: If this is the top result and we haven't matched yet, check aliases
            if is_top_result:
                logger.info(f"Top result failed basic match, performing deep check for aliases on {tmdb_id}...")
                details = self.get_full_media_details(tmdb_id, media_type)
                if details:
                    # Check Keywords (often contain alternative titles or tags)
                    keywords = details.get("keywords", [])
                    for kw in keywords:
                        kw_name = kw.get("name", "")
                        if not kw_name: continue
                        
                        norm_kw = normalize_title(kw_name)
                        if normalized_query_name in norm_kw:
                            logger.info(f"Found {media_type}: '{media_name}' matches keyword '{kw_name}'")
                            print(f"✅ Found {media_type}: '{media_name}' (Matches Keyword: '{kw_name}')")
                            return imdb_id, jellyseerr_id, tmdb_id, media_type
                            
                    # Fallback Heuristic for Anime:
                    # If we are searching for a TV show, and the result is an Anime (Genre 16 or Original Lang 'ja'),
                    # and it's the TOP result, we should probably trust it because standard Romaji -> English title mapping is inconsistent.
                    is_anime = False
                    if details.get("originalLanguage") == "ja":
                        is_anime = True
                    elif any(g.get("id") == 16 for g in details.get("genres", [])):
                        is_anime = True
                        
                    if is_anime:
                        logger.info(f"Anime Heuristic: Top result is an Anime (Lang: {details.get('originalLanguage')}), trusting result despite title mismatch.")
                        print(f"✅ Found {media_type}: '{media_name}' (Anime Heuristic Match: '{title}')")
                        return imdb_id, jellyseerr_id, tmdb_id, media_type

                    if DEBUG_MODE == 'VERBOSE' or True:
                        logger.info(f"Deep check keys available: {list(details.keys())}")

            if preferred_check and (DEBUG_MODE == 'VERBOSE' or True): # Enforce logging
                 logger.info(f"Preferred check failed for '{media_name}' vs '{title}' (Org: {original_title}) [{media_type}]")
            
            return None

            if preferred_check and (DEBUG_MODE == 'VERBOSE' or True): # Enforce logging
                 logger.info(f"Preferred check failed for '{media_name}' vs '{title}' (Org: {original_title}) [{media_type}]")
            
            return None

        # 1. If preferred type is specified, try to find a match of that type first
        if preferred_media_type:
            for i, result in enumerate(results):
                if result.get("mediaType") == preferred_media_type:
                    # Treat the first preferred result as a "top result" candidate for deep checking
                    is_top = (i == 0) 
                    match = check_result(result, preferred_check=True, is_top_result=is_top)
                    if match:
                        return match
        
        # 2. If no match found yet (or no preference), check all results
        for i, result in enumerate(results):
            # Skip if we already checked it (optimization: check if type matches preferred)
            if preferred_media_type and result.get("mediaType") == preferred_media_type:
                continue
                
            is_top = (i == 0)
            match = check_result(result, is_top_result=is_top)
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
    
    def make_request(self, tmdb_id, media_id=None, media_type="movie"):
        """
        Make a request for media in Jellyseerr.
        
        Args:
            tmdb_id (int): TMDB ID of the media
            media_id (int, optional): Media ID from Jellyseerr (if exists)
            media_type (str): Type of media ("movie" or "tv")
            
        Returns:
            tuple: (success: bool, message: str)
        """
        payload = {
            "mediaType": media_type,
            "tmdbId": tmdb_id,
            "is4k": IS_4K_REQUEST,
            # mediaId must be a number (validation). Use 0 if None to indicate new media.
            # Jellyseerr uses findOne({ where: { tmdbId: requestBody.mediaId } }) for movies (bug in logic? line 122)
            # OR findOne({ where: { tmdbId: requestBody.mediaId ... } }) (line 127)
            # Actually, line 122/123 uses requestBody.mediaId to fetch from TMDB, which is wrong if mediaId is internal ID.
            # But looking at line 125, it queries Media repo by tmdbId: requestBody.mediaId.
            # WAIT: In MediaRequest.ts:
            # tmdbMedia = await tmdb.getMovie({ movieId: requestBody.mediaId }) 
            # This implies requestBody.mediaId is treated as TMDB ID in some places?
            # NO, look at line 127: where: { tmdbId: requestBody.mediaId }
            # It seems the payload 'mediaId' is expected to be the TMDB ID?!
            # BUT earlier logs showed "mediaId" is separate from "tmdbId".
            # Let's check requestInterfaces.ts again.
            # mediaId: number; tmdbId?: number; ??
            # Re-read MediaRequest.ts carefully.
            
            # Line 122: await tmdb.getMovie({ movieId: requestBody.mediaId })
            # This STRONGLY suggests mediaId in the body is actually the TMDB ID.
            # BUT we also have tmdbId in the body?
            # Let's look at requestInterfaces.ts content from previous step.
            # mediaId: number;
            # tvdbId?: number;
            # ...
            # NO tmdbId in MediaRequestBody in the file I read!
            
            # Wait, I read requestInterfaces.ts content in step 20:
            # export type MediaRequestBody = {
            #   mediaType: MediaType;
            #   mediaId: number;  <-- This IS the ID used for TMDB lookup!
            #   tvdbId?: number;
            #   ...
            # };
            
            # THERE IS NO tmdbId in MediaRequestBody!
            # My client code is sending: { mediaType, tmdbId, is4k, mediaId }
            # The 'tmdbId' key is ignored. 'mediaId' IS the TMDB ID.
            
            "mediaId": int(tmdb_id)
        }
        
        if media_type == "tv":
            # For TV shows, we use "all" to request all available seasons.
            # This delegates the season lookup to the Jellyseerr server, which is more reliable
            # than fetching details client-side and constructing the list manually.
            # It ensures that all valid seasons (excluding specials usually) are requested.
            payload["seasons"] = "all"
        
        logger.info(f"Making request for {media_type} (tmdbId: {tmdb_id}, mediaId: {media_id})")
        logger.info(f"API URL: {self.base_url}/api/v1/request")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
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
                elif res.status_code == 202:
                    # 202 Accepted usually means "No seasons available" which implies they are already requested/owned
                    logger.info(f"Request accepted (likely already requested/owned) for {media_type} {tmdb_id}: {res.text}")
                    print(f"✅ Requested {media_type} (Already handled/owned) - Status: 202")
                    return True, res.text
                else:
                    logger.info(f"Request skipped for mediaId {media_id}. Status: {res.status_code}")
                    logger.info(f"Response body: {res.text}")
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
