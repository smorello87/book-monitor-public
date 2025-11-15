# Rare Books Monitor 📚

Automated rare books listing tracker that monitors BookFinder.com based on search criteria defined in a Google Sheets document. Sends daily digest emails when new listings appear.

**Version 2**: Google Sheets-based flexible search system
**Version 1** (archived): Zotero library-based system → see `archive/v1-zotero/`

## What It Does

This system automatically:
1. ✅ Reads search specifications from a **Google Sheets** document
2. ✅ Searches **BookFinder.com** for books matching your criteria
3. ✅ Filters to **USED condition** books only (configurable)
4. ✅ Tracks listings in a **SQLite database** to detect new ones
5. ✅ Sends **daily email digests** with new findings
6. ✅ Runs **automatically via local cron job** (no server needed)

## Features

- 📊 **Google Sheets Integration**: Define searches in a spreadsheet (Author, Title, Year, Keywords)
- 🔍 **Flexible Search**: Search by author only, or combine with title/year/keywords
- 🎯 **Smart Filtering**: Only shows books by the EXACT author (prevents false matches)
- 📧 **Daily Digests**: Beautiful HTML emails grouped by author
- 💾 **Deduplication**: Tracks seen listings to avoid spam
- ⏰ **Automated Scheduling**: Runs daily via local cron job
- 🌐 **Playwright Scraping**: Handles JavaScript-rendered pages reliably
- 🕐 **Rate Limited**: Polite 10-second delays between requests

## Project Structure

```
book-monitor/
├── src/
│   ├── sheets_loader.py         # 📊 Google Sheets CSV reader
│   ├── bookfinder_scraper.py    # 🔍 BookFinder.com scraper (Playwright)
│   ├── database.py              # 💾 SQLite operations
│   └── digest.py                # 📧 Email generation (Brevo API)
├── archive/v1-zotero/           # 📦 Old Zotero-based system
├── data/
│   └── books.db                 # SQLite database (auto-created)
├── logs/                        # Cron job logs (auto-created)
├── config.yaml                  # ⚙️ Configuration
├── monitor.py                   # 🚀 Main script
├── setup_cron.sh                # 🔧 Automated cron setup script
└── requirements.txt             # Python dependencies
```

## Prerequisites

1. **Google Sheets**: A public Google Sheets document with search criteria
2. **Brevo Account**: Free email service (300 emails/day free tier)
3. **Python 3.7+**: For running the monitor script
4. **Cron or Task Scheduler**: For automated daily runs (built into macOS/Linux)

## Quick Start

### 1. Create Your Google Sheets Document

1. **Copy the template**: [Example Google Sheet](https://docs.google.com/spreadsheets/d/1wnGY6o-uRGw1vsxPb6MzN44KxvnK5MeRTA5Mn6DmTXo/edit?usp=sharing)
2. **Make it public**: Share → "Anyone with the link" → Viewer
3. **Add your searches**: Fill in the columns (see format below)

**Required Columns:**
- `Author` - Full author name (e.g., "Bernardino Ciambelli") **REQUIRED**

**Optional Columns:**
- `Title` - Specific book title (leave blank to search all books by author)
- `Year` - Publication year (filters to that year only)
- `Keyword` - Additional search keywords

**Example Sheet:**

| Author | Title | Year | Keyword |
|--------|-------|------|---------|
| Bernardino Ciambelli | | | |
| Andre Luotto | Anima Italiana | | |
| Giovanni Verga | I Malavoglia | 1881 | |

4. **Get the Sheet ID**: From the URL `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`

### 2. Set Up Brevo Email Service

1. Create free account at [Brevo](https://www.brevo.com/)
2. Go to **SMTP & API** → **API Keys** → Create new key
3. **Copy the API key** (starts with `xkeysib-`)
4. **Verify your sender email** in Brevo dashboard

### 3. Clone This Repository

```bash
git clone https://github.com/YOUR_USERNAME/book-monitor.git
cd book-monitor
```

### 4. Configure Your Settings

Edit `config.yaml`:

```yaml
# Google Sheets Configuration
google_sheets:
  sheet_id: "YOUR_SHEET_ID"  # From your Google Sheets URL

# Email Configuration (Brevo)
email:
  sender_email: "your-verified-email@example.com"  # Must be verified in Brevo
  sender_name: "Rare Books Monitor"
  recipient_email: "your-email@example.com"        # Where to receive digests

# Search Configuration
search:
  condition_filter: "used"    # Filter: 'used', 'any', or 'new'
  sort_order: "price_desc"    # Highest price first (rare editions)

# BookFinder Configuration
bookfinder:
  rate_limit_seconds: 10      # Be polite! (10 seconds between requests)
  timeout: 30

# Monitoring Configuration
monitoring:
  max_specs_per_run: 40       # Max searches to check per run
```

### 5. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser (required for web scraping)
python -m playwright install chromium
```

### 6. Test the Setup

```bash
# Set API key
export BREVO_API_KEY="your-brevo-api-key"

# Test Google Sheets connection
python monitor.py --test

# Run full check (won't send email with --no-email)
python monitor.py --verbose --no-email
```

### 7. Set Up Automated Daily Runs

#### Automatic Setup

```bash
# Run the setup script
./setup_cron.sh
```

The script will guide you through:
1. Setting environment variables in crontab
2. Adding the cron job (runs daily at 6 AM)
3. Creating log directory

#### Manual Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

2. **Open crontab editor**:
```bash
crontab -e
```

3. **Add environment variables** (at the top):
```bash
BREVO_API_KEY=xkeysib-your_api_key_here
SENDER_EMAIL=your-verified-email@example.com
RECIPIENT_EMAIL=your-email@example.com
GOOGLE_SHEETS_ID=1wnGY6o-uRGw1vsxPb6MzN44KxvnK5MeRTA5Mn6DmTXo
```

4. **Add cron job** (runs daily at 6 AM):
```bash
0 6 * * * cd /path/to/book-monitor && /usr/local/bin/python3 monitor.py --verbose >> /path/to/book-monitor/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

5. **Save and verify**:
```bash
crontab -l
```

#### Viewing Logs

```bash
# Today's log
tail -f logs/monitor_$(date +%Y%m%d).log

# All logs
ls -lh logs/
```

That's it! The system will now:
- ✅ Run daily at 6 AM from your local machine
- ✅ Check your Google Sheet for searches
- ✅ Search BookFinder for each author/title
- ✅ Email you a digest of new listings
- ✅ Store results in the database

## How It Works

### Search Strategies

The system uses two different approaches based on your Google Sheet entries:

**1. Author + Title Search** (when title is provided):
```
Search: "Andre Luotto" + "Anima Italiana"
→ Finds specific book by that exact author
→ Filters out other Luottos (James, P., etc.)
```

**2. Author-Only Search** (when title is blank):
```
Search: "Bernardino Ciambelli" + (no title)
→ Finds ALL books by Bernardino Ciambelli
→ Filters out Pietro Ciambelli, Lea Ciambelli, etc.
```

**Critical**: The system uses FULL author names and verifies each listing against the actual author to prevent false matches.

### Daily Workflow

1. **6 AM Local**: Cron job triggers
2. **Sync**: Loads latest search specs from your Google Sheet
3. **Search**: For each row, searches BookFinder.com
4. **Filter**: Keeps only USED books by the EXACT author
5. **Deduplicate**: Compares with database to find new listings
6. **Email**: Sends digest grouped by author
7. **Save**: Updates local database with results

## Usage

### Adding New Searches

Just edit your Google Sheet! The system checks it every day.

**Example**: Want to monitor Giovanni Verga?
1. Open your Google Sheet
2. Add new row: `Giovanni Verga | I Malavoglia | 1881 | `
3. Done! Next run will include it.

### Manual Commands (Local)

```bash
# Full run (sync + check + email)
python monitor.py

# Test connections
python monitor.py --test

# Sync Google Sheet only
python monitor.py --sync-only

# Check listings only (skip sync)
python monitor.py --check-only

# Run without email
python monitor.py --no-email

# Search for ANY condition (not just used)
python monitor.py --condition any

# Verbose logging
python monitor.py --verbose
```

## For Collaborators: How to Adapt This System

### Use Case 1: Monitor Different Book Sources

Replace `bookfinder_scraper.py` with scrapers for:
- **AbeBooks**: Similar structure, different selectors
- **Alibris**: Use their search API if available
- **Open Library**: Official API available

**Key files to modify:**
- `src/bookfinder_scraper.py` - Scraping logic
- `src/database.py` - May need additional fields
- `config.yaml` - Add new source configuration

### Use Case 2: Different Notification Methods

Replace `digest.py` with:
- **Slack**: Post to channel via webhook
- **Discord**: Send to Discord server
- **Telegram**: Use Telegram Bot API
- **SMS**: Twilio integration

**Key file to modify:**
- `src/digest.py` - Notification delivery

### Use Case 3: Track Other Items

Adapt for non-book items:
- **Vintage records/vinyl**
- **Rare coins**
- **Collectible stamps**
- **Antique furniture**

**Key changes needed:**
- Google Sheet structure (add relevant fields)
- Search parameters in `bookfinder_scraper.py`
- Email template in `digest.py`

### Use Case 4: Price Alerts

Add price threshold alerts:

```python
# In digest.py, filter listings:
def get_below_threshold_listings(listings, max_price):
    return [l for l in listings if l['price'] <= max_price]
```

## Email Digest Format

HTML email with:
- **Grouped by author** (e.g., "Andre Luotto", "Bernardino Ciambelli")
- Each listing shows: Title, Seller, Price, Condition, Link
- Sorted by price (highest first for rare editions)

## For Developers: Technical Details

### Database Schema

**search_specs** (v2 Google Sheets system):
- `spec_id`, `author`, `title`, `publication_year`, `keywords`

**books**:
- `book_id` (hash of title+author), `title`, `author`, `publication_year`

**listings**:
- `listing_hash`, `book_id`, `seller`, `price`, `currency`, `condition`, `url`, `notified`

### Key Files

- `src/sheets_loader.py` - Google Sheets CSV parser (pandas)
- `src/bookfinder_scraper.py` - Web scraper (Playwright + BeautifulSoup)
- `src/database.py` - SQLite ORM with hash-based deduplication
- `src/digest.py` - Email generation (Brevo REST API)
- `monitor.py` - Main orchestration script

## Customization

### Change Check Frequency

Edit your crontab (`crontab -e`):

```bash
# Run twice daily (6 AM and 6 PM)
0 6,18 * * * cd /path/to/book-monitor && python3 monitor.py --verbose >> /path/to/book-monitor/logs/monitor_$(date +\%Y\%m\%d).log 2>&1

# Run every 12 hours
0 */12 * * * cd /path/to/book-monitor && python3 monitor.py --verbose >> /path/to/book-monitor/logs/monitor_$(date +\%Y\%m\%d).log 2>&1

# Run weekly (Monday 8 AM)
0 8 * * 1 cd /path/to/book-monitor && python3 monitor.py --verbose >> /path/to/book-monitor/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

Cron syntax: `minute hour day month weekday`

### Search for NEW or ANY Condition

In `config.yaml`:

```yaml
search:
  condition_filter: "new"    # Options: used, new, any
```

### Adjust Rate Limiting

Be more polite to BookFinder:

```yaml
bookfinder:
  rate_limit_seconds: 15     # 15 seconds between requests
```

### Limit Searches Per Run

Process fewer specs to avoid timeouts:

```yaml
monitoring:
  max_specs_per_run: 20      # Check only 20 searches per run
```

## Troubleshooting

### Google Sheets Not Loading

- **Check sharing**: Sheet must be "Anyone with link can view"
- **Verify Sheet ID**: From URL `/d/SHEET_ID/edit`
- **Column names**: Must be exactly `Author`, `Title`, `Year`, `Keyword`

### Wrong Author Results

- **Use full name**: "Bernardino Ciambelli" not "Ciambelli"
- **Leave title blank**: To search all books by author
- **Add title**: For specific book searches

### No Listings Found

- BookFinder may have no listings for that author/book
- Try searching BookFinder.com manually first
- Check verbose logs: `python monitor.py --verbose`

### Email Not Received

- Check spam/junk folder
- Verify sender email in Brevo dashboard
- Check cron job logs: `tail -f logs/monitor_$(date +%Y%m%d).log`
- Ensure `BREVO_API_KEY` starts with `xkeysib-` (not `xsmtpsib-`)

### Cron Job Not Running

- Verify cron job is installed: `crontab -l`
- Check environment variables are set in crontab
- Verify Python path is correct: `which python3`
- Check logs for errors: `tail -f logs/monitor_*.log`

## Legal & Ethical Considerations

⚠️ **Important**: Web scraping considerations:

- **Personal use only**: This tool is for monitoring YOUR personal rare book searches
- **Rate limiting**: 10+ second delays between requests (configurable)
- **No commercialization**: Do not sell or redistribute scraped data
- **Robots.txt**: BookFinder's robots.txt discourages automated search access
- **Alternative**: Consider official APIs when available (Open Library, Google Books)

**Best practices:**
- Use generous rate limiting (15+ seconds)
- Limit searches per run (`max_specs_per_run: 20`)
- Monitor during off-peak hours only

## Cost Analysis

**100% Free** for typical usage:

| Service | Free Tier | Typical Usage | Cost |
|---------|-----------|---------------|------|
| Local Cron | Unlimited | Runs on your computer | $0 |
| Brevo Email | 300 emails/day | 1 email/day | $0 |
| Google Sheets | Unlimited | 1 sheet | $0 |
| **Total** | | | **$0/month** |

## Version History

- **v2 (Current)**: Google Sheets-based flexible search system
  - Support for Author, Title, Year, Keywords
  - Smart author filtering to prevent false matches
  - Daily automated monitoring via local cron job

- **v1 (Archived)**: Zotero library-based system → `archive/v1-zotero/`

## Contributing

Contributions welcome! Ideas:
- **Additional sources**: AbeBooks, Alibris, Open Library APIs
- **Price tracking**: Historical price charts
- **Multiple sheets**: Support monitoring multiple Google Sheets
- **Webhooks**: Slack, Discord, Telegram notifications
- **Web dashboard**: Manage searches via web interface

## License

MIT License - Free for personal and educational use

## Acknowledgments

Built with:
- [Playwright](https://playwright.dev/python/) - JavaScript-rendered web scraping
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Pandas](https://pandas.pydata.org/) - CSV data processing
- [Brevo](https://www.brevo.com/) - Email delivery (formerly SendinBlue)

---

**Questions?** Open an issue or check the [CLAUDE.md](CLAUDE.md) for technical details.

**Happy rare book hunting!** 📚✨
