"""
Main entry point for Jelly Request application.
Orchestrates the IMDb scraping and Jellyseerr requesting process.
"""

import time
from config import RUN_INTERVAL_DAYS, IMDB_URLS, logger
from imdb_scraper import scrape_imdb_top_movies
from mal_scraper import scrape_mal_season
from jellyseerr_client import JellyseerrClient
from header import display_header

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
            # Use a dictionary to store movies with their preferred type
            # Key: Title, Value: {title: str, type: str}
            all_media = {}
            
            print(f"\nStarting scrape cycle for {len(IMDB_URLS)} list(s)...")
            
            for idx, url in enumerate(IMDB_URLS, 1):
                try:
                    print(f"\n[{idx}/{len(IMDB_URLS)}] Scraping URL: {url}")
                    
                    # Determine preferred type based on URL
                    preferred_type = None
                    if "myanimelist.net" in url:
                        movies = scrape_mal_season(url)
                        preferred_type = "tv" # MAL is mostly anime series
                    else:
                        movies = scrape_imdb_top_movies(url)
                        preferred_type = "movie" # IMDb lists are usually movies
                    
                    if not movies:
                        logger.warning(f"No movies found for URL: {url}")
                        print(f"⚠️ No movies found for list {idx}.")
                    else:
                        logger.info(f"Scraped {len(movies)} items from list {idx} (Type hint: {preferred_type})")
                        print(f"✅ Found {len(movies)} items.")
                        
                        for movie in movies:
                            # Store in dictionary to dedup by title, but keep the preferred type
                            # If it already exists, we keep the existing one (first come first served)
                            # or maybe we should prefer 'tv' if both exist? For now, simple dedup.
                            if movie not in all_media:
                                all_media[movie] = {
                                    "title": movie,
                                    "type": preferred_type
                                }
                        
                except Exception as e:
                    logger.error(f"Failed to scrape list {url}: {e}")
                    print(f"❌ Failed to scrape list {url}: {e}")
                    continue

            unique_media_list = sorted(all_media.values(), key=lambda x: x["title"])
            
            if not unique_media_list:
                logger.error("No movies found from any configured lists")
                print("❌ No movies found from any lists.")
            else:
                logger.info(f"Total unique items to process: {len(unique_media_list)}")
                print(f"✅ Total Unique Items (Total: {len(unique_media_list)}):")
                for i, item in enumerate(unique_media_list, 1):
                    type_str = f" [{item['type'].upper()}]" if item['type'] else ""
                    print(f"{i}. {item['title']}{type_str}")
                
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
            # Search for the media in Jellyseerr
            json_data = jellyseerr_client.search_media(title)
            if not json_data:
                stats["not_found"] += 1
                print(f"❌ SKIPPED: Not found in Jellyseerr search results")
                continue
                
            # Extract details from search results with preferred type
            imdb_id, media_id, tmdb_id, media_type = jellyseerr_client.get_media_details(title, json_data, preferred_type)
            
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
