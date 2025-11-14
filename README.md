# 📚 Rare Books Monitor v2

Automated monitoring system for rare and historical book listings on BookFinder.com. Get daily email digests when new listings appear for books you're tracking.

## Features

- **📊 Google Sheets Integration** - Manage your book searches from a simple spreadsheet
- **🔍 Flexible Search** - Search by author, title, year, keywords, or combinations
- **📧 Email Digests** - Daily notifications when new listings appear
- **🤖 GitHub Actions** - Runs automatically, no server needed
- **💾 Persistent Tracking** - Remembers what you've seen, no duplicate notifications
- **🎯 Smart Filtering** - Choose NEW, USED, or both for each search

## Quick Start

See [SETUP.md](SETUP.md) for complete setup instructions.

## Example Searches

| Configuration | Result |
|--------------|--------|
| Author: "Jack Kerouac"<br>Title: blank | All books by Jack Kerouac |
| Author: "Jack Kerouac"<br>Title: "On the Road" | Only "On the Road" |
| Accept New: Y | Include NEW condition books |
| Accept New: blank | USED books only (default) |

## License

MIT License - See [LICENSE](LICENSE)
