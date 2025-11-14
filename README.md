# 📚 Book Monitor

Automated monitoring system for book listings on BookFinder.com. Get daily email digests when new listings appear for books you're tracking.

## Features

- **📊 Google Sheets Integration** - Manage your book searches from a simple spreadsheet
- **🔍 Flexible Search** - Search by author, title, year, keywords, ISBN, or price range
- **📧 Email Digests** - Daily notifications when new listings appear
- **🤖 GitHub Actions** - Runs automatically, no server needed
- **💾 Persistent Tracking** - Remembers what you've seen, no duplicate notifications
- **🎯 Smart Filtering** - Choose NEW, USED, or both; filter by price

## Quick Setup

### 1. Fork This Repository

Click the "Fork" button at the top right of this page.

### 2. Create Your Google Sheet

1. Create a new Google Sheet with these columns (only **Author** is required):

| Author | Title | Year | Keyword | Accept New | Price Below | ISBN |
|--------|-------|------|---------|------------|-------------|------|
| Jack Kerouac | On the Road | | | Y | 20 | |
| Jack Kerouac | | | | | 15 | |
| Eric Lott | | | | | | 9780195320558 |

**Column Guide:**
- **Author** (required): Full author name
- **Title** (optional): Specific book title, or leave blank for all books by author
- **Year** (optional): Publication year filter
- **Keyword** (optional): Additional search keywords
- **Accept New** (optional): Y to include NEW books, blank for USED only
- **Price Below** (optional): Only show listings under this price
- **ISBN** (optional): Search by ISBN (takes priority over all other fields)

2. Make your sheet public:
   - Click **Share** → **Anyone with the link** → **Viewer**

3. Copy your Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit
   ```

### 3. Set Up Email (Brevo)

1. Sign up for a free [Brevo account](https://www.brevo.com/)
2. Verify your sender email address in Brevo dashboard
3. Generate an API key:
   - Go to **Settings** → **API Keys** → **Create a new API key**
   - Copy the key (starts with `xkeysib-...`)

### 4. Configure GitHub Secrets

In your forked repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add these secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `BREVO_API_KEY` | Your Brevo API key | `xkeysib-abc123...` |
| `SENDER_EMAIL` | Your verified email | `you@gmail.com` |
| `RECIPIENT_EMAIL` | Where to send digest | `you@gmail.com` |
| `GOOGLE_SHEETS_ID` | Your Sheet ID | `1wnGY6o-uRGw1...` |

### 5. Enable GitHub Actions

1. Go to **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"

### 6. Test Your Setup

#### Option A: Manual Test Run
1. Go to **Actions** → **Book Monitor** workflow
2. Click **Run workflow** → **Run workflow**
3. Check for email within 5 minutes

#### Option B: Wait for Scheduled Run
The workflow runs automatically every day at 6 AM UTC.

## How It Works

### Search Priority

When you add a row to your Google Sheet, the system searches in this order:

1. **ISBN** (if provided) → Uses `/isbn/{isbn}/` endpoint
2. **Title + Author** (if title provided) → Precise search
3. **Author only** (if no title) → All books by that author

### Example Searches

| Configuration | What It Does |
|--------------|--------------|
| Author: "Jack Kerouac"<br>Title: blank | Find all books by Jack Kerouac (USED only) |
| Author: "Jack Kerouac"<br>Title: "On the Road" | Find only "On the Road" by Kerouac |
| Author: "Jack Kerouac"<br>Accept New: Y | Include NEW condition books |
| Author: "Jack Kerouac"<br>Price Below: 15 | Only show books under $15 |
| Author: "Eric Lott"<br>ISBN: 9780195320558 | Search by ISBN (ignores title) |

### Email Digest

You'll receive a daily email with:
- New listings grouped by author
- Book title, seller, price, condition
- Direct links to each listing
- Sorted by price (highest first)

## Customization

### Change Schedule

Edit `.github/workflows/monitor.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'  # Daily at 6 AM UTC
  # Change to '0 18 * * *' for 6 PM UTC
  # Change to '0 */6 * * *' for every 6 hours
```

### Change Rate Limiting

Edit `config.example.yaml` then copy to `config.yaml`:

```yaml
bookfinder:
  rate_limit_seconds: 10  # Wait time between requests
  # Increase to 15-20 to be more polite to BookFinder
```

### Limit Books Checked Per Run

```yaml
monitoring:
  max_specs_per_run: 40  # Check only first 40 rows
```

## Troubleshooting

### Not Receiving Emails?

1. Check GitHub Actions logs: **Actions** → Latest workflow run
2. Verify Brevo API key is correct (starts with `xkeysib-`)
3. Verify sender email is verified in Brevo dashboard
4. Check spam folder

### No Listings Found?

- BookFinder may not have listings for that book/author
- Try broader search (remove title, search by author only)
- Check Google Sheet has correct author name spelling

### GitHub Actions Not Running?

1. Ensure Actions are enabled: **Settings** → **Actions** → **Allow all actions**
2. Check workflow file exists: `.github/workflows/monitor.yml`
3. Verify secrets are set correctly

### Database Not Updating?

The `data/books.db` file is automatically updated and committed after each run. Check:
1. GitHub Actions has write permissions
2. Workflow completes successfully (green checkmark)

## Local Development

Want to run it on your computer?

```bash
# 1. Clone your fork
git clone https://github.com/YOUR_USERNAME/book-monitor-public.git
cd book-monitor-public

# 2. Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 3. Copy config template
cp config.example.yaml config.yaml

# 4. Edit config.yaml with your settings

# 5. Set environment variables
export BREVO_API_KEY="xkeysib-..."
export SENDER_EMAIL="you@gmail.com"
export RECIPIENT_EMAIL="you@gmail.com"

# 6. Run
python monitor.py --verbose
```

## Advanced Features

### Test Mode

```bash
# Test connections without searching
python monitor.py --test
```

### Sync Only

```bash
# Update database from Google Sheets without searching
python monitor.py --sync-only
```

### No Email

```bash
# Search but don't send email
python monitor.py --no-email
```

## Architecture

- **monitor.py**: Main script (sync → search → email)
- **src/sheets_loader.py**: Reads Google Sheets CSV
- **src/bookfinder_scraper.py**: Web scraper with Playwright fallback
- **src/database.py**: SQLite persistence
- **src/digest.py**: Email generation via Brevo

See [CLAUDE.md](CLAUDE.md) for detailed technical documentation.

## License

MIT License - See [LICENSE](LICENSE)

## Support

- **Issues**: [GitHub Issues](https://github.com/smorello87/book-monitor-public/issues)
- **Documentation**: See [SETUP.md](SETUP.md) and [CLAUDE.md](CLAUDE.md)
