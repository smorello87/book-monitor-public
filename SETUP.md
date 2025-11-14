# Setup Guide - Book Monitor v2

Complete step-by-step instructions for deploying the Book Monitor on GitHub Actions.

## Prerequisites

- GitHub account
- Google account (for Google Sheets)
- Brevo account (free tier: 300 emails/day)

## Part 1: Create Your Google Sheet

1. **Create a new Google Sheet**
   - Go to [Google Sheets](https://sheets.google.com)
   - Create a new spreadsheet
   - Name it something like "Rare Books Monitor"

2. **Set up the columns** (in this exact order):
   - **Column A**: `Author` (required) - Full author name
   - **Column B**: `Title` (optional) - Leave blank to search ALL books by author
   - **Column C**: `Year` (optional) - Publication year
   - **Column D**: `Keyword` (optional) - Additional search keywords
   - **Column E**: `Accept New` (optional) - Put "Y" to include NEW condition books

3. **Add your books**:
   ```
   Author              | Title           | Year | Keyword | Accept New
   Jack Kerouac        | On the Road     |      |         | Y
   Bernardino Ciambelli|                 |      |         |
   ```

4. **Make the sheet public**:
   - Click "Share" button (top right)
   - Click "Change to anyone with the link"
   - Set to "Viewer"
   - Click "Done"

5. **Get the Sheet ID**:
   - Look at the URL: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit`
   - Copy the `YOUR_SHEET_ID` part

## Part 2: Set Up Brevo Email

1. **Create Brevo account**:
   - Go to [Brevo](https://www.brevo.com/) (formerly Sendinblue)
   - Sign up for free account (300 emails/day)

2. **Verify your email**:
   - Settings → Senders → Add a new sender
   - Use the email address you want to send/receive notifications

3. **Get API key**:
   - Settings → SMTP & API → API Keys
   - Create new API key (name it "Book Monitor")
   - Copy the key (starts with `xkeysib-`)
   - **IMPORTANT**: This is REST API key, NOT SMTP key!

## Part 3: Fork and Configure Repository

1. **Fork this repository**:
   - Click "Fork" button on GitHub
   - This creates your own copy

2. **Create config.yaml**:
   ```bash
   cp config.example.yaml config.yaml
   ```

3. **Edit config.yaml**:
   - Replace `YOUR_GOOGLE_SHEETS_ID_HERE` with your Sheet ID from Part 1
   - Save and commit:
   ```bash
   git add config.yaml
   git commit -m "Add configuration"
   git push
   ```

4. **Set up GitHub Secrets**:
   - Go to your forked repo on GitHub
   - Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Add these three secrets:

   | Name | Value |
   |------|-------|
   | `BREVO_API_KEY` | Your Brevo API key (from Part 2) |
   | `SENDER_EMAIL` | Your verified email from Brevo |
   | `RECIPIENT_EMAIL` | Email where you want notifications |

## Part 4: Test the Workflow

1. **Manual test run**:
   - Go to Actions tab in your repo
   - Click "Rare Books Monitor (Author-Based)"
   - Click "Run workflow" → "Run workflow"
   - Watch it run (takes 2-5 minutes)

2. **Check for success**:
   - Workflow should show green checkmark ✓
   - Check for new commit: "Update rare books listings database [automated]"
   - Check your email for digest (if new listings found)

3. **If it fails**:
   - Click on the failed run → click on "monitor" job
   - Look at the error message
   - Common issues:
     - Wrong Google Sheet ID
     - Wrong Brevo API key format (should start with `xkeysib-`)
     - Email not verified in Brevo
     - Secrets not set correctly

## Part 5: Automatic Daily Runs

Once working, the workflow runs automatically:
- **Schedule**: Every day at 6 AM UTC
- **What it does**:
  1. Syncs search specs from your Google Sheet
  2. Searches BookFinder.com for new listings
  3. Sends email digest if new books found
  4. Commits database updates

**To modify schedule**:
Edit `.github/workflows/monitor.yml` line 6:
```yaml
- cron: '0 6 * * *'   # 6 AM UTC daily
```

## Local Development (Optional)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

2. **Create .env file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit .env**:
   ```
   BREVO_API_KEY=xkeysib-your-key-here
   SENDER_EMAIL=your-email@example.com
   RECIPIENT_EMAIL=your-email@example.com
   ```

4. **Run locally**:
   ```bash
   # Test connections
   python monitor.py --test

   # Sync from Google Sheets
   python monitor.py --sync-only

   # Check for new listings (no email)
   python monitor.py --check-only --no-email

   # Full run with email
   python monitor.py
   ```

## Understanding the "Accept New" Feature

By default, the system only finds USED books (rare books are typically used).

To include NEW books for specific searches:
- Add "Y" in the "Accept New" column for that row
- Leave blank for USED-only (default behavior)

Example:
```
Author       | Title      | Accept New | Result
Jack Kerouac | On the Road| Y          | Finds NEW + USED
Jack Kerouac | Big Sur    |            | Finds USED only
```

## Troubleshooting

### No email received
- Check spam folder
- Verify sender email in Brevo dashboard
- Check workflow logs for errors
- Ensure listings were actually found

### Wrong API key error
- Brevo has two key types:
  - ✅ REST API key: `xkeysib-...` (correct)
  - ❌ SMTP key: `xsmtpsib-...` (won't work)

### Google Sheets access denied
- Sheet must be "Anyone with link can view"
- Sheet ID must be exact (no extra characters)

### No listings found
- Check your search terms in BookFinder.com manually
- Try broader searches (remove Year, Keywords)
- Some books may not have any listings

## Support

For issues or questions:
- Check [CLAUDE.md](CLAUDE.md) for technical details
- Open an issue on GitHub
- Review workflow logs in Actions tab
