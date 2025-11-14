#!/usr/bin/env python3
"""Author-based book monitoring script for rare/historical books."""

import os
import sys
import yaml
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sheets_loader import SheetsLoader
from bookfinder_scraper import BookFinderScraper
from database import Database
from digest import DigestEmailer


def setup_logging(verbose: bool = False):
    """Configure logging.

    Args:
        verbose: Enable verbose/debug logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def sync_search_specs(sheet_id: str, db: Database) -> int:
    """Load search specifications from Google Sheets and sync to database.

    Args:
        sheet_id: Google Sheets document ID
        db: Database instance

    Returns:
        Number of search specs synced
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Loading search specifications from Google Sheets...")

    # Load search specs from Google Sheets
    loader = SheetsLoader(sheet_id)
    search_specs = loader.load_search_specs()

    # Upsert search specs to database
    synced_count = 0
    for spec in search_specs:
        db.upsert_search_spec(
            author=spec['author'],
            title=spec['title'],
            year=spec['year'],
            keywords=spec['keywords'],
            isbn=spec.get('isbn'),
            max_price=spec.get('max_price'),
            accept_new=spec.get('accept_new', False)
        )
        synced_count += 1

    logger.info(f"Synced {synced_count} search specifications to database")
    return synced_count


def check_search_spec(spec: dict, spec_id: str, scraper: BookFinderScraper,
                       db: Database, filter_condition: str = 'used') -> int:
    """Search BookFinder using search specification and save listings.

    Args:
        spec: Search specification with keys: author, title, year, keywords, isbn, max_price, accept_new
        spec_id: Search spec ID for tracking
        scraper: BookFinder scraper instance
        db: Database instance
        filter_condition: Default condition filter ('used', 'any', 'new') - overridden by spec's accept_new

    Returns:
        Number of new listings found
    """
    logger = logging.getLogger(__name__)

    author = spec.get('author')
    title = spec.get('title')
    year = spec.get('year')
    keywords = spec.get('keywords')
    isbn = spec.get('isbn')
    max_price = spec.get('max_price')
    accept_new = spec.get('accept_new', False)

    # Determine filter_condition based on accept_new field
    # If accept_new=True, use 'any' to include both NEW and USED
    # If accept_new=False, use 'used' to exclude NEW
    if accept_new:
        filter_condition = 'any'
    else:
        filter_condition = 'used'

    search_desc = f"{author}"
    if title:
        search_desc += f" - {title}"
    if year:
        search_desc += f" ({year})"
    if keywords:
        search_desc += f" [{keywords}]"
    if isbn:
        search_desc += f" [ISBN: {isbn}]"
    if max_price:
        search_desc += f" [max: ${max_price}]"

    logger.info(f"Checking listings for: {search_desc} (condition: {filter_condition})")

    # Search priority: ISBN → Title+Author → Author-only
    if isbn:
        # ISBN provided → direct ISBN search (highest priority)
        logger.debug(f"Using ISBN search for: {isbn}")
        listings = scraper.search_by_isbn(
            isbn=isbn,
            max_price=max_price
        )
    elif title:
        # Title provided → precise search by title + author
        logger.debug(f"Using title+author search for: {title}")
        listings = scraper.search_by_title_author(
            title=title,
            author=author,
            book_id=None,
            year=year,
            keywords=keywords,
            filter_condition=filter_condition,
            max_price=max_price
        )
    else:
        # No title or ISBN → broad search by author only
        logger.debug(f"Using author-only search for: {author}")
        listings = scraper.search_by_author_only(
            author=author,
            author_id=spec_id,
            filter_condition=filter_condition,
            year=year,
            keywords=keywords,
            max_price=max_price
        )

    if not listings:
        logger.info(f"No {filter_condition} listings found for {search_desc}")
        db.update_search_spec_checked(spec_id)
        return 0

    # Filter by max_price if specified (BookFinder doesn't always respect maxPrice parameter)
    if max_price is not None:
        original_count = len(listings)
        listings = [l for l in listings if l.get('price', float('inf')) <= max_price]
        if len(listings) < original_count:
            logger.info(f"Filtered {original_count - len(listings)} listings above max price ${max_price}")

    if not listings:
        logger.info(f"No listings found under max price ${max_price} for {search_desc}")
        db.update_search_spec_checked(spec_id)
        return 0

    # Group listings by book (by book_id)
    books_found = {}
    for listing in listings:
        book_id = listing.get('book_id')
        if not book_id:
            # Generate book_id if not present
            import hashlib
            book_title = listing.get('title') or title or 'Unknown'
            book_key = f"{book_title}|{author}".lower()
            book_id = hashlib.sha256(book_key.encode()).hexdigest()[:16]
            listing['book_id'] = book_id

        if book_id not in books_found:
            books_found[book_id] = {
                'title': listing.get('title') or title or 'Unknown',
                'author': listing.get('author') or author,  # Use author from listing if available
                'isbn': isbn if isbn else None,  # Include ISBN if we searched by ISBN
                'year': year,
                'keywords': keywords,
                'listings': []
            }
        books_found[book_id]['listings'].append(listing)

    # Save books and listings to database
    total_new_listings = 0
    for book_id, book_data in books_found.items():
        # Upsert book with metadata
        # For ISBN searches, book_id IS the ISBN, so we need to generate proper book_id
        actual_book_id = db.upsert_book(
            title=book_data['title'],
            author=book_data['author'],
            isbn=book_data.get('isbn'),
            publication_year=year
        )

        # Update book_id in all listings if it changed (ISBN → title+author hash)
        if actual_book_id != book_id:
            for listing in book_data['listings']:
                listing['book_id'] = actual_book_id

        # Save listings for this book
        new_count = db.save_listings(book_data['listings'])
        total_new_listings += new_count

    # Update search spec checked timestamp
    db.update_search_spec_checked(spec_id)

    logger.info(f"Found {len(books_found)} books, {total_new_listings} new listings for: {search_desc}")
    return total_new_listings


def send_author_digest(db: Database, emailer: DigestEmailer) -> bool:
    """Send digest email grouped by author.

    Args:
        db: Database instance
        emailer: Email client

    Returns:
        True if email sent successfully
    """
    logger = logging.getLogger(__name__)

    # Get unnotified listings grouped by author
    author_listings = db.get_unnotified_listings_by_author()

    if not author_listings:
        logger.info("No new listings to notify")
        return False

    # Count total listings
    total_listings = sum(len(listings) for listings in author_listings.values())

    logger.info(f"Preparing digest: {len(author_listings)} authors, {total_listings} listings")

    # Flatten listings for emailer (it will handle grouping)
    all_listings = []
    for author, listings in author_listings.items():
        all_listings.extend(listings)

    # Send email
    success = emailer.send_digest(listings=all_listings)

    if success:
        # Mark all listings as notified
        listing_hashes = [l['listing_hash'] for l in all_listings]
        db.mark_listings_notified(listing_hashes)
        logger.info(f"Email sent successfully, marked {len(listing_hashes)} listings as notified")
    else:
        logger.warning("Failed to send email")

    return success


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Monitor search specs for rare/historical books')

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--test', action='store_true',
                        help='Test connections only (no actual monitoring)')
    parser.add_argument('--sync-only', action='store_true',
                        help='Only sync search specs from Google Sheets to database')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check search specs (skip sync)')
    parser.add_argument('--no-email', action='store_true',
                        help='Skip sending email digest')
    parser.add_argument('--condition', default='used',
                        choices=['used', 'any', 'new'],
                        help='Condition filter for books (default: used)')
    parser.add_argument('--config', default='config.yaml',
                        help='Path to config file')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("BOOK MONITOR - AUTHOR-BASED RARE BOOKS TRACKER")
    logger.info("=" * 80)

    try:
        # Load configuration
        config = load_config(args.config)

        # Initialize database
        db_path = config.get('database', {}).get('path', 'data/books.db')
        db = Database(db_path)

        if args.test:
            logger.info("Test mode: Checking connections...")

            # Test Google Sheets
            try:
                sheet_id = config.get('google_sheets', {}).get('sheet_id')
                if not sheet_id:
                    raise ValueError("google_sheets.sheet_id not configured in config.yaml")

                loader = SheetsLoader(sheet_id)
                search_specs = loader.load_search_specs()
                logger.info(f"✓ Google Sheets loaded: {len(search_specs)} search specifications")
            except Exception as e:
                logger.error(f"✗ Google Sheets error: {e}")
                return 1

            # Test BookFinder connection
            bf_config = config['bookfinder']
            scraper = BookFinderScraper(
                base_url=bf_config['base_url'],
                rate_limit=bf_config['rate_limit_seconds'],
                user_agent=bf_config['user_agent'],
                timeout=bf_config['timeout']
            )
            if scraper.test_connection():
                logger.info("✓ BookFinder connection successful")
            else:
                logger.error("✗ BookFinder connection failed")
                return 1

            logger.info("✓ All connections successful!")
            return 0

        # Initialize scraper
        bf_config = config['bookfinder']
        scraper = BookFinderScraper(
            base_url=bf_config['base_url'],
            rate_limit=bf_config['rate_limit_seconds'],
            user_agent=bf_config['user_agent'],
            timeout=bf_config['timeout']
        )

        # Phase 1: Sync search specs from Google Sheets
        if not args.check_only:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 1: SYNC SEARCH SPECIFICATIONS")
            logger.info("=" * 80)

            sheet_id = config.get('google_sheets', {}).get('sheet_id')
            if not sheet_id:
                logger.error("google_sheets.sheet_id not configured in config.yaml")
                return 1

            synced_count = sync_search_specs(sheet_id, db)
            logger.info(f"Synced {synced_count} search specifications")

            if args.sync_only:
                logger.info("Sync-only mode: Exiting")
                db.close()
                return 0

        # Phase 2: Check search specifications
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: CHECK SEARCH SPECIFICATIONS")
        logger.info("=" * 80)

        # Get enabled search specs
        search_specs = db.get_enabled_search_specs()
        max_specs = config.get('monitoring', {}).get('max_specs_per_run', 40)

        # Limit to max_specs
        specs_to_check = search_specs[:max_specs]

        logger.info(f"Checking {len(specs_to_check)} search specifications...")

        total_new_listings = 0
        for i, spec_row in enumerate(specs_to_check, 1):
            # Convert database row to spec dict
            spec = {
                'author': spec_row['author'],
                'title': spec_row.get('title'),
                'year': spec_row.get('publication_year'),
                'keywords': spec_row.get('keywords'),
                'isbn': spec_row.get('isbn'),
                'max_price': spec_row.get('max_price'),
                'accept_new': spec_row.get('accept_new', False)
            }

            search_desc = spec['author']
            if spec['title']:
                search_desc += f" - {spec['title']}"

            logger.info(f"\n[{i}/{len(specs_to_check)}] {search_desc}")

            new_listings = check_search_spec(
                spec=spec,
                spec_id=spec_row['spec_id'],
                scraper=scraper,
                db=db,
                filter_condition=args.condition
            )

            total_new_listings += new_listings

        logger.info(f"\nTotal new listings found: {total_new_listings}")

        # Phase 3: Send digest email
        if not args.no_email and total_new_listings > 0:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 3: SEND DIGEST EMAIL")
            logger.info("=" * 80)

            # Initialize email client
            email_config = config['email']
            emailer = DigestEmailer(
                api_key=os.environ.get('BREVO_API_KEY'),
                sender_email=email_config['sender_email'],
                sender_name=email_config['sender_name'],
                recipient_email=email_config['recipient_email']
            )

            send_author_digest(db, emailer)

        elif args.no_email:
            logger.info("\nSkipping email (--no-email flag)")
        else:
            logger.info("\nNo new listings to email")

        # Close database
        db.close()

        logger.info("\n" + "=" * 80)
        logger.info("MONITORING COMPLETE")
        logger.info("=" * 80)

        return 0

    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
