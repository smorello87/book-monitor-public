# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Book Monitor v2 is an automated rare books listing tracker that monitors BookFinder.com based on search specifications from a Google Sheets document. It sends daily digest emails when new listings appear. The system uses Playwright for web scraping to handle JavaScript-rendered content and supports flexible search criteria: Author (required), Title (optional), Year (optional), and Keywords (optional).

**Version History**:
- **v1** (archived in `archive/v1-zotero/`): Zotero-based system - automated monitoring of books in a Zotero library
- **v2** (current): Google Sheets-based system - flexible search specifications with multiple parameters

## Key Architecture

### Core Workflow (monitor.py)
The main entry point orchestrates a three-phase workflow:
1. **Sync Phase**: Loads search specifications from Google Sheets (CSV export) → updates `search_specs` table in SQLite
2. **Check Phase**: For each search spec, searches BookFinder.com → identifies new listings → saves to database
3. **Notify Phase**: Groups unnotified listings by author → sends HTML digest email via Brevo

### Component Structure

**src/sheets_loader.py**: Google Sheets CSV integration
- Loads search specifications from public Google Sheets via CSV export
- No authentication required (sheet must be "Anyone with link can view")
- CSV URL format: `https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv`
- Parses columns: Author (required), Title (optional), Year (optional), Keyword (optional)
- Uses pandas for CSV parsing
- Returns list of search spec dictionaries

**src/zotero_client.py**: ARCHIVED (v1 only) - Zotero API integration
- Kept for backward compatibility
- Not used in v2 Google Sheets-based system

**src/bookfinder_scraper.py**: BookFinder.com web scraper with hybrid strategy
- **Strategy 1 (Fast)**: HTTP request → extract `__NEXT_DATA__` JSON from Next.js
- **Strategy 2 (Medium)**: HTTP request → parse HTML with BeautifulSoup
- **Strategy 3 (Fallback)**: Playwright headless browser → wait for JavaScript render → parse HTML
- Always uses `viewAll=true` parameter to get full listings page (not grouped results)
- Parses listings from `data-csa-c-item-type="search-offer"` attributes (BookFinder's 2024+ structure)
- Rate limiting: 10 second delays between requests by default

**src/database.py**: SQLite persistence layer
- **search_specs table**: Stores search specifications from Google Sheets (spec_id, author, title, year, keywords)
- **authors table**: DEPRECATED (v1 only) - kept for backward compatibility
- **books table**: Uses hash-based `book_id` (not ISBN) as primary key to support historical books without ISBNs
- **listings table**: Tracks individual listings with deduplication via listing hash
- Hash generation: SHA256 of `{book_id}|{seller}|{price}|{condition}|{url}`
- Tracks notification status to avoid duplicate emails

**src/digest.py**: Email delivery via Brevo REST API
- Generates HTML emails with grouped listings by book
- Requires REST API key (format: `xkeysib-...`), not SMTP key
- Templates include: book title, author, ISBN, seller, price, condition, direct links

### Search Strategy Details

The system uses two different search strategies based on whether a title is provided in the Google Sheet:

**Strategy 1: Title + Author Search** (when title is provided):
```
/search/?author={full_author_name}&title={title}&keywords={keywords}&publicationMinYear={year}&publicationMaxYear={year}&mode=ADVANCED&viewAll=true
```
- Uses FULL author name (e.g., "Andre Luotto"), not just lastname
- Precise search for a specific book
- Filters results to match the exact author using `data-csa-c-authors` attribute verification

**Strategy 2: Author-Only Search** (when no title is provided):
```
/search/?author={full_author_name}&title=&keywords={keywords}&publicationMinYear={year}&publicationMaxYear={year}&mode=ADVANCED&viewAll=true
```
- Uses FULL author name (e.g., "Bernardino Ciambelli")
- Broad search for ALL books by that author
- **CRITICAL**: Uses full name, NOT just lastname, to avoid false matches with other authors sharing the same surname
- Filters results with strict author verification to prevent matches like "Pietro Ciambelli" when searching for "Bernardino Ciambelli"

**Author Filtering (CRITICAL)**:
- After scraping, each listing is verified against the searched author using the `data-csa-c-authors` attribute
- Listings without author data are REJECTED (prevents false positives)
- Author name variations are checked (e.g., "Andre", "Andrea", "A.", "A" for "Andre Luotto")
- Only listings with verified author matches are saved

**BookFinder Parameters**:
- `publicationMinYear` and `publicationMaxYear`: Year range (NOT just `year=`)
- `keywords`: Additional search keywords
- `mode=ADVANCED`: Uses advanced search mode
- `viewAll=true`: CRITICAL - gets full listings page instead of grouped "bunch" results

### Playwright Integration

**When Playwright is used**: Only as a fallback when HTTP requests return 0 listings
**Browser**: Headless Chromium
**Wait strategy**:
1. Navigate with `wait_until='networkidle'`
2. Wait for selector (15s timeout)
3. Additional 3s timeout for JavaScript rendering
4. Extract HTML and close browser

**Performance**: ~20 seconds per book (vs ~2 seconds with HTTP)

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (REQUIRED)
python -m playwright install chromium

# Set API key
export BREVO_API_KEY="xkeysib-..."  # REST API key, not SMTP key
```

### Running

```bash
# Full monitoring run (sync + check + email)
python monitor.py

# Test connections only
python monitor.py --test

# Sync search specs from Google Sheets only
python monitor.py --sync-only

# Check listings only (skip Google Sheets sync)
python monitor.py --check-only

# Run without sending email
python monitor.py --no-email

# Filter by condition (default: used)
python monitor.py --condition used   # or 'any' or 'new'

# Verbose logging
python monitor.py --verbose
```

### Testing Individual Components

```bash
# Test Google Sheets loader
python -c "from src.sheets_loader import SheetsLoader; loader = SheetsLoader('SHEET_ID'); print(loader.load_search_specs())"

# Test BookFinder scraper (includes Playwright test)
python src/bookfinder_scraper.py

# Test email sending
python -c "from src.digest import DigestEmailer; ..."

# Test database directly
sqlite3 data/books.db "SELECT * FROM search_specs;"
sqlite3 data/books.db "SELECT COUNT(*) FROM listings WHERE notified = 0;"
```

## Database Schema

**search_specs table** (`spec_id` is PRIMARY KEY) - v2 Google Sheets system:
- `spec_id`: Hash of author+title (16 char hex)
- `author`: Full author name (REQUIRED)
- `title`: Book title (OPTIONAL - when NULL, searches all books by author)
- `publication_year`: Publication year (OPTIONAL)
- `keywords`: Search keywords (OPTIONAL)
- `added_date`, `last_checked`, `check_enabled`

**authors table** (`author_id` is PRIMARY KEY) - DEPRECATED v1 only:
- Kept for backward compatibility
- Not used in v2 Google Sheets-based system

**books table** (`book_id` is PRIMARY KEY):
- `book_id`: Hash of title+author (16 char hex)
- `isbn`: Optional, can be NULL
- `title`, `author`, `publication_year`
- `last_checked`, `check_enabled`

**listings table** (`listing_hash` is PRIMARY KEY):
- `listing_hash`: Unique hash of listing details
- `book_id`: Foreign key to books
- `seller`, `price`, `currency`, `condition`, `url`
- `first_seen`, `last_seen`, `is_active`
- `notified`: Boolean flag for email tracking

## Configuration (config.yaml)

**Google Sheets configuration (v2)**:
- `google_sheets.sheet_id`: Google Sheets document ID (from URL)
- Sheet must be "Anyone with link can view" for CSV export access
- Required column: Author
- Optional columns: Title, Year, Keyword

**Search configuration**:
- `search.condition_filter`: Filter condition - "used" (default), "any", or "new"
- `search.sort_order`: "price_desc" (highest price first for rare editions)

**BookFinder configuration**:
- `bookfinder.rate_limit_seconds`: 10+ (be polite to BookFinder)
- `bookfinder.timeout`: 30 seconds for HTTP requests
- `bookfinder.user_agent`: Browser user agent string

**Monitoring configuration**:
- `monitoring.max_specs_per_run`: Limit search specs checked per execution (40 default)

**Email configuration**:
- Sender email must be verified in Brevo dashboard
- Use REST API key (starts with `xkeysib-`), not SMTP key (`xsmtpsib-`)
- Set as environment variable: `BREVO_API_KEY`

**Archived v1 settings** (not used in v2):
- `zotero.library_id`, `zotero.library_type` - for v1 Zotero-based system only

## GitHub Actions Deployment

**Workflow** (`.github/workflows/monitor.yml`):
- Runs daily at 6 AM UTC (configurable via cron)
- Uses `ubuntu-latest` runner
- **Critical step**: `python -m playwright install --with-deps chromium` to install browser
- Automatically syncs latest search specs from Google Sheets each run
- Commits database changes back to repository after each run
- Requires secret: `BREVO_API_KEY`

**Performance**: ~2-5 minutes per run depending on number of search specs

## Common Issues

**No listings found**: Ensure using `viewAll=true` parameter in search URL. BookFinder's default grouped view doesn't include individual listings.

**Playwright timeout**: Increase wait times in `_fetch_with_playwright()` method. Some pages need >3 seconds for JavaScript to render.

**Wrong API key type**: Brevo has two key types - REST API keys (`xkeysib-...`) work, SMTP keys (`xsmtpsib-...`) don't.

**Google Sheets access denied**: Sheet must be set to "Anyone with link can view" for CSV export to work without authentication.

**Wrong author results**:
- If searching by author only (no title), system uses the FULL author name to prevent false matches
- Listings are filtered using `data-csa-c-authors` attribute - those without author data are rejected
- Author variations (nicknames, initials) are checked to ensure proper matching

**Author-only searches returning 0 results**:
- BookFinder requires full author name (e.g., "Bernardino Ciambelli")
- Using only lastname (e.g., "Ciambelli") may match other authors with same surname
- The system's author filtering then rejects all listings as false positives
- Fix: Ensure search_by_author_only() uses full `author` parameter, not `author_lastname`

## Web Scraping Ethics

- Uses 10+ second rate limiting (configurable)
- Only scrapes public data (book listings)
- Respects robots.txt (note: BookFinder's robots.txt disallows `/search/` for automated tools)
- Designed for personal use only (monitoring personal Zotero library)
- BookFinder doesn't offer official API access
