"""
Main entry point for Jelly Request application.
Orchestrates the IMDb scraping and Jellyseerr requesting process.
"""

import time
from config import RUN_INTERVAL_DAYS, IMDB_URLS, MOVIE_LISTS, TV_LISTS, ANIME_LISTS, REQUEST_DELAY_SECONDS, logger
from imdb_scraper import scrape_imdb_top_movies
from mal_scraper import scrape_mal_season
from jellyseerr_client import JellyseerrClient
from header import display_header
from utils import generate_search_candidates

def aggregate_media(movie_lists, tv_lists, anime_lists, imdb_urls):
    """
    Aggregates media from various lists.
    
    Args:
        movie_lists (list): URLs for movie lists
        tv_lists (list): URLs for TV lists
        anime_lists (list): URLs for anime lists
        imdb_urls (list): Legacy/Mixed URLs
        
    Returns:
        list: Sorted list of unique media items with types
    """
    # Use a dictionary to store movies with their preferred type
    # Key: Title, Value: {title: str, type: str}
    all_media = {}
    
    # Define list groups to process: (urls, forced_type, label)
    list_groups = [
        (movie_lists, "movie", "Movies"),
        (tv_lists, "tv", "TV Shows"),
        (anime_lists, "tv", "Anime"),
        (imdb_urls, None, "Legacy/Mixed")
    ]
    
    total_lists = sum(len(group[0]) for group in list_groups)
    print(f"\\nStarting scrape cycle for {total_lists} configured list(s)...")
    
    list_count = 0
    for urls, forced_type, label in list_groups:
        if not urls:
            continue
            
        print(f"\\n--- Processing {label} Lists ---")
        
        for url in urls:
            list_count += 1
            try:
                print(f"\\n[{list_count}/{total_lists}] Scraping URL: {url}")
                
                # Determine scraper and default type based on URL
                scraper_items = []
                detected_type = None
                
                if "myanimelist.net" in url:
                    scraper_items = scrape_mal_season(url)
                    detected_type = "tv" # MAL is mostly anime series
                else:
                    scraper_items = scrape_imdb_top_movies(url)
                    detected_type = "movie" # IMDb lists are usually movies
                
                # Use forced_type if specified (from config), otherwise use detected_type
                final_type = forced_type if forced_type else detected_type
                
                if not scraper_items:
                    logger.warning(f"No media found for URL: {url}")
                    print(f"⚠️ No items found for list.")
                else:
                    logger.info(f"Scraped {len(scraper_items)} items from {label} list (Type: {final_type})")
                    print(f"✅ Found {len(scraper_items)} items.")
                    
                    for item_title in scraper_items:
                        # Store in dictionary to dedup by title
                        # If we have a forced type, it overwrites any previous entry's type
                        # or if it's new.
                        if item_title not in all_media or forced_type:
                            all_media[item_title] = {
                                "title": item_title,
                                "type": final_type
                            }
                    
            except Exception as e:
                logger.error(f"Failed to scrape list {url}: {e}")
                print(f"❌ Failed to scrape list {url}: {e}")
                continue

    unique_media_list = sorted(all_media.values(), key=lambda x: x["title"])
    
    if not unique_media_list:
        logger.error("No media found from any configured lists")
        print("❌ No media found from any lists.")
    else:
        logger.info(f"Total unique items to process: {len(unique_media_list)}")
        print(f"✅ Total Unique Items (Total: {len(unique_media_list)}):")
        for i, item in enumerate(unique_media_list, 1):
            type_str = f" [{item['type'].upper()}]" if item['type'] else ""
            print(f"{i}. {item['title']}{type_str}")
            
    return unique_media_list

def main():
    """Main application loop."""
    # Display application header
    display_header()
    
    logger.info(f"Starting IMDb to Jellyseerr sync, configured to run every {RUN_INTERVAL_DAYS} day(s)")
    print(f"Configured to run every {RUN_INTERVAL_DAYS} day(s)")
    
    # Initialize Jellyseerr client
    jellyseerr = JellyseerrClient()
    
    while True:
        try:
            unique_media_list = aggregate_media(MOVIE_LISTS, TV_LISTS, ANIME_LISTS, IMDB_URLS)
            
            if unique_media_list:
                process_movies(jellyseerr, unique_media_list)
                
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            print(f"❌ Unexpected error: {e}")
        finally:
            logger.info(f"Completed run, sleeping for {RUN_INTERVAL_DAYS} day(s)")
            print(f"ℹ️ Completed run, sleeping for {RUN_INTERVAL_DAYS} day(s)")
            time.sleep(RUN_INTERVAL_DAYS * 24 * 60 * 60)  # Sleep for specified days

def process_movies(jellyseerr_client, media_items):
    """
    Process a list of media items through Jellyseerr with enhanced duplicate prevention.
    
    Args:
        jellyseerr_client (JellyseerrClient): Initialized Jellyseerr client
        media_items (list): List of dicts {"title": str, "type": str}
    """
    # Initialize counters for summary
    stats = {
        "total": len(media_items),
        "new_requests": 0,
        "skipped_requested": 0,
        "skipped_available": 0,
        "skipped_processing": 0,
        "skipped_pending": 0,
        "skipped_declined": 0,
        "not_found": 0,
        "errors": 0
    }
    
    # Fetch existing requests for duplicate prevention
    jellyseerr_client.get_existing_requests()
    
    print("\nRequesting media in Jellyseerr...")
    
    for i, item in enumerate(media_items, 1):
        title = item["title"]
        preferred_type = item["type"]
        
        print(f"\nProcessing '{title}' ({i}/{len(media_items)})...")
        try:
            # Search for the media in Jellyseerr. Try the original title first, then fall
            # back to sequel/season-stripped variants (e.g. "Grand Blue Season 3" -> "Grand Blue"),
            # since TMDB/Seerr index the base series rather than the suffixed seasonal title.
            imdb_id = media_id = tmdb_id = media_type = None
            for candidate in generate_search_candidates(title):
                json_data = jellyseerr_client.search_media(candidate)
                if not json_data:
                    continue
                imdb_id, media_id, tmdb_id, media_type = jellyseerr_client.get_media_details(
                    candidate, json_data, preferred_type
                )
                if tmdb_id:
                    if candidate != title:
                        logger.info(f"Matched '{title}' via fallback query '{candidate}'")
                        print(f"   ↪ Matched via fallback search: '{candidate}'")
                    break
            
            # Check if we have at least a TMDB ID. 'media_id' here is the internal Jellyseerr ID (nullable).
            if not tmdb_id:
                stats["not_found"] += 1
                print(f"❌ SKIPPED: Not found in Jellyseerr search results")
                continue
            
            # Check if already requested or available
            # Note: We pass media_id if it exists, otherwise logic inside relies on TMDB ID checks
            should_skip, skip_reason, skip_details = jellyseerr_client.is_already_requested_or_available(
                tmdb_id, media_type, imdb_id, title
            )
            
            if should_skip:
                # Categorize skip reason for stats
                status = str(skip_details.get("status", "")).upper()
                if status == "AVAILABLE":
                    stats["skipped_available"] += 1
                elif status == "APPROVED":
                    stats["skipped_requested"] += 1
                elif status == "PROCESSING":
                    stats["skipped_processing"] += 1
                elif status == "PENDING":
                    stats["skipped_pending"] += 1
                elif status == "DECLINED":
                    stats["skipped_declined"] += 1
                else:
                    stats["skipped_requested"] += 1  # Default to requested
                
                # Enhanced logging with detailed skip reason
                _log_skip_reason(title, skip_reason, skip_details)
                continue
            
            # Media is new - make the request
            print(f"🎬 REQUESTING: New {media_type} not in system")
            # Pass media_id (can be None) and tmdb_id
            success, msg = jellyseerr_client.make_request(tmdb_id, media_id, media_type)
            
            if success:
                stats["new_requests"] += 1
                print(f"✅ SUCCESS: {media_type.capitalize()} requested - Status: PENDING")
                # Throttle between new requests so Seerr doesn't fire auto-approval
                # notifications faster than downstream services (e.g. Discord) allow.
                if REQUEST_DELAY_SECONDS > 0:
                    logger.debug(f"Waiting {REQUEST_DELAY_SECONDS}s before next request to avoid rate limits")
                    time.sleep(REQUEST_DELAY_SECONDS)
            else:
                stats["errors"] += 1
                if "Request for this media already exists" not in msg:
                    logger.error(f"Failed to request '{title}': {msg}")
                    print(f"❌ FAILED: Could not request {media_type} - {msg}")
                else:
                    # This is a race condition where media was requested between our check and request
                    stats["skipped_requested"] += 1
                    print(f"⏭️ SKIPPED: Request already exists (race condition)")
                
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error processing '{title}': {e}")
            print(f"❌ ERROR: Processing failed - {e}")
            continue
    
    # Print summary
    _print_summary(stats)

def _log_skip_reason(movie, skip_reason, skip_details):
    """
    Log detailed skip reason with enhanced formatting.
    
    Args:
        movie (str): Movie title
        skip_reason (str): Reason for skipping
        skip_details (dict): Additional details about the skip
    """
    status = str(skip_details.get("status", "")).upper()
    
    if status == "AVAILABLE":
        added_date = skip_details.get("added_date", "")
        date_str = f" - Added: {added_date[:10]}" if added_date else ""
        print(f"⏭️ SKIPPED: Already available in library (Status: AVAILABLE){date_str}")
        
    elif status == "APPROVED":
        request_id = skip_details.get("request_id", "")
        created = skip_details.get("created", "")
        date_str = f" - Requested: {created[:10]}" if created else ""
        id_str = f" - Request ID: {request_id}" if request_id else ""
        print(f"⏭️ SKIPPED: Already requested (Status: APPROVED){id_str}{date_str}")
        
    elif status == "PROCESSING":
        request_id = skip_details.get("request_id", "")
        id_str = f" - Request ID: {request_id}" if request_id else ""
        print(f"⏭️ SKIPPED: Currently downloading (Status: PROCESSING){id_str}")
        
    elif status == "PENDING":
        request_id = skip_details.get("request_id", "")
        created = skip_details.get("created", "")
        date_str = f" - Requested: {created[:10]}" if created else ""
        id_str = f" - Request ID: {request_id}" if request_id else ""
        print(f"⏭️ SKIPPED: Pending approval (Status: PENDING){id_str}{date_str}")
        
    elif status == "DECLINED":
        request_id = skip_details.get("request_id", "")
        id_str = f" - Request ID: {request_id}" if request_id else ""
        print(f"⏭️ SKIPPED: Failed previous request (Status: DECLINED){id_str}")
        
    else:
        print(f"⏭️ SKIPPED: {skip_reason}")

def _print_summary(stats):
    """
    Print detailed summary of processing results.
    
    Args:
        stats (dict): Statistics from processing
    """
    total = stats["total"]
    new_requests = stats["new_requests"]
    total_skipped = (stats["skipped_requested"] + stats["skipped_available"] + 
                    stats["skipped_processing"] + stats["skipped_pending"] + 
                    stats["skipped_declined"])
    
    print(f"\n{'='*40}")
    print("SUMMARY")
    print(f"{'='*40}")
    print(f"📊 Total movies processed: {total}")
    print(f"✅ New requests made: {new_requests}")
    
    if stats["skipped_requested"] > 0:
        print(f"⏭️ Skipped (already requested): {stats['skipped_requested']}")
    if stats["skipped_available"] > 0:
        print(f"📚 Skipped (already available): {stats['skipped_available']}")
    if stats["skipped_processing"] > 0:
        print(f"⚠️ Skipped (currently downloading): {stats['skipped_processing']}")
    if stats["skipped_pending"] > 0:
        print(f"⏸️ Skipped (pending approval): {stats['skipped_pending']}")
    if stats["skipped_declined"] > 0:
        print(f"❌ Skipped (previously declined): {stats['skipped_declined']}")
    if stats["not_found"] > 0:
        print(f"🔍 Not found in search: {stats['not_found']}")
    if stats["errors"] > 0:
        print(f"💥 Errors encountered: {stats['errors']}")
    
    success_rate = (new_requests / total * 100) if total > 0 else 0
    prevention_rate = (total_skipped / total * 100) if total > 0 else 0
    
    print(f"\n🎯 Success rate: {success_rate:.0f}% new requests ({new_requests}/{total} movies were genuinely new)")
    print(f"⚡ Duplicate prevention: {prevention_rate:.0f}% efficiency ({total_skipped}/{total} duplicates avoided)")

if __name__ == "__main__":
    main()
