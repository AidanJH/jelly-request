# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Essential Commands

### Local Development (Python 3.11+)
*   **Install Dependencies:** `pip install -r requirements.txt`
*   **Run Application:** `python main.py`
    *   *Note:* Requires setting environment variables (see Configuration below) or relying on defaults.
*   **Test Scraper Only:** (Snippet to run in REPL)
    ```python
    from imdb_scraper import scrape_imdb_top_movies
    print(scrape_imdb_top_movies(limit=5))
    ```

### Docker Workflows
*   **Build:** `docker build -t jelly-request .`
*   **Run (Compose):** `docker-compose up -d --build`
*   **View Logs:** `docker logs -f jelly-request`
*   **Stop:** `docker-compose down`

## Architecture Overview

The application orchestrates a one-way sync from IMDb to Jellyseerr:
1.  **Scheduler (`main.py`):** Runs the sync loop based on `RUN_INTERVAL_DAYS`.
2.  **Input (`imdb_scraper.py`):** Fetches the configured IMDb list. It attempts to parse JSON-LD structured data first, falling back to HTML scraping if necessary.
3.  **Normalization (`utils.py`):** Titles are normalized (special chars removed, lowercase) to maximize match probability.
4.  **Integration (`jellyseerr_client.py`):**
    *   Searches Jellyseerr for the normalized title.
    *   Checks existing requests and library availability to prevent duplicates.
    *   Sends a request (POST `/api/v1/request`) if the movie is missing and unrequested.

## Configuration & Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `JELLYSEERR_URL` | `http://192.168.0.29:5054` | Base URL for Jellyseerr API. |
| `API_KEY` | (Placeholder) | Jellyseerr API Key (`X-Api-Key` header). |
| `IMDB_URL` | `https://www.imdb.com/chart/moviemeter` | Source IMDb list URL (Legacy). |
| `LIST_URLS` | `None` | Comma-separated list or JSON array of IMDb URLs. Overrides `IMDB_URL` if set. |
| `MOVIE_LIMIT` | `50` | Max movies to scrape per run. |
| `RUN_INTERVAL_DAYS` | `7` | Days to sleep between runs. |
| `DEBUG_MODE` | `SIMPLE` | Set to `VERBOSE` for debug logs. |
| `IS_4K_REQUEST` | `true` | Request 4K quality profile (`true`/`false`). |

## Implementation Details

### IMDb Scraping
*   **Anti-Bot:** Uses a standard User-Agent header.
*   **Parsing:** Preferentially targets `<script type="application/ld+json">` for stability. Fallback uses CSS selector `ul.ipc-metadata-list li.ipc-metadata-list-summary-item a h3`.
*   **Resilience:** Errors during scraping return an empty list but do not crash the container; the scheduler will retry after the interval.

### Jellyseerr Integration
*   **Duplicate Prevention:**
    1.  Fetches *all* existing requests first to build an in-memory skip list (keyed by TMDb/IMDb IDs).
    2.  Checks `mediaInfo.status` (5 = Available) via `/api/v1/movie/{tmdb_id}` before requesting.
*   **Idempotency:** Relying solely on the API's 409 Conflict response is insufficient due to race conditions; the client implements aggressive pre-checks.
*   **Auth:** Uses `X-Api-Key` header.

## Repo-Specific Conventions
*   **Logging:** Use `config.logger` instead of `print` for operational logs.
*   **Version Control:** Git revision/branch are baked into the container at build time (ARGS `GIT_REVISION`, `GIT_BRANCH`) and displayed in the startup header.
