"""Database operations for tracking books and listings."""

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for book and listing tracking."""

    def __init__(self, db_path: str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.connect()
        self.init_schema()

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        logger.info(f"Connected to database: {self.db_path}")

    def init_schema(self):
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # Authors table - DEPRECATED (kept for backward compatibility)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authors (
                author_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL UNIQUE,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                check_enabled BOOLEAN DEFAULT 1
            )
        """)

        # Search Specifications table - for Google Sheets based monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_specs (
                spec_id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                title TEXT,
                publication_year INTEGER,
                keywords TEXT,
                accept_new BOOLEAN DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                check_enabled BOOLEAN DEFAULT 1
            )
        """)

        # Books table - book_id is primary key (hash of title+author)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                book_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                isbn TEXT,
                publication_year TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                check_enabled BOOLEAN DEFAULT 1
            )
        """)

        # Listings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                listing_hash TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                seller TEXT,
                price REAL,
                currency TEXT DEFAULT 'USD',
                condition TEXT,
                url TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                notified BOOLEAN DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(book_id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_isbn
            ON books(isbn)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_book_id
            ON listings(book_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_active
            ON listings(is_active)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_listings_notified
            ON listings(notified)
        """)

        # Migration: Add accept_new column if it doesn't exist
        try:
            cursor.execute("SELECT accept_new FROM search_specs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding accept_new column to search_specs table")
            cursor.execute("ALTER TABLE search_specs ADD COLUMN accept_new BOOLEAN DEFAULT 0")

        self.conn.commit()
        logger.info("Database schema initialized")

    def generate_book_id(self, title: str, author: Optional[str] = None) -> str:
        """Generate unique book ID from title and author.

        Args:
            title: Book title
            author: Book author (optional)

        Returns:
            SHA256 hash string
        """
        # Normalize title and author for consistent hashing
        normalized_title = title.lower().strip() if title else ''
        normalized_author = author.lower().strip() if author else ''

        # Combine title and author
        content = f"{normalized_title}|{normalized_author}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]  # Use first 16 chars for shorter IDs

    def generate_listing_hash(self, listing: Dict) -> str:
        """Generate unique hash for a listing.

        Args:
            listing: Dictionary with listing details

        Returns:
            SHA256 hash string
        """
        # Combine key fields to create unique identifier
        content = (
            f"{listing.get('book_id', '')}|"
            f"{listing.get('seller', '')}|"
            f"{listing.get('price', '')}|"
            f"{listing.get('condition', '')}|"
            f"{listing.get('url', '')}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def upsert_book(self, title: str, author: Optional[str] = None,
                    isbn: Optional[str] = None,
                    publication_year: Optional[str] = None):
        """Insert or update a book record.

        Args:
            title: Book title
            author: Book author(s)
            isbn: Book ISBN (optional)
            publication_year: Year of publication
        """
        book_id = self.generate_book_id(title, author)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO books (book_id, title, author, isbn, publication_year)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET
                title = excluded.title,
                author = excluded.author,
                isbn = excluded.isbn,
                publication_year = excluded.publication_year
        """, (book_id, title, author, isbn, publication_year))
        self.conn.commit()
        logger.debug(f"Upserted book: {book_id} - {title}")
        return book_id

    def update_book_checked(self, book_id: str):
        """Update last_checked timestamp for a book.

        Args:
            book_id: Book ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE books
            SET last_checked = CURRENT_TIMESTAMP
            WHERE book_id = ?
        """, (book_id,))
        self.conn.commit()

    def generate_author_id(self, full_name: str) -> str:
        """Generate unique author ID from full name.

        Args:
            full_name: Author's full name

        Returns:
            SHA256 hash string
        """
        normalized_name = full_name.lower().strip()
        return hashlib.sha256(normalized_name.encode()).hexdigest()[:16]

    def upsert_author(self, full_name: str) -> str:
        """Insert or update an author record.

        Args:
            full_name: Author's full name

        Returns:
            Author ID
        """
        author_id = self.generate_author_id(full_name)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO authors (author_id, full_name)
            VALUES (?, ?)
            ON CONFLICT(author_id) DO UPDATE SET
                full_name = excluded.full_name
        """, (author_id, full_name))
        self.conn.commit()
        logger.debug(f"Upserted author: {author_id} - {full_name}")
        return author_id

    def get_enabled_authors(self) -> List[Dict]:
        """Get all enabled authors for checking.

        Returns:
            List of author dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT author_id, full_name, last_checked
            FROM authors
            WHERE check_enabled = 1
            ORDER BY full_name
        """)
        return [dict(row) for row in cursor.fetchall()]

    def update_author_checked(self, author_id: str):
        """Update last_checked timestamp for an author.

        Args:
            author_id: Author ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE authors
            SET last_checked = CURRENT_TIMESTAMP
            WHERE author_id = ?
        """, (author_id,))
        self.conn.commit()

    # Search Specification Methods (Google Sheets based)
    # ===================================================

    def generate_search_spec_id(self, author: str, title: Optional[str] = None) -> str:
        """Generate unique search spec ID from author and optional title.

        Args:
            author: Author name
            title: Book title (optional)

        Returns:
            SHA256 hash string
        """
        key = f"{author}|{title or ''}".lower().strip()
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def upsert_search_spec(self, author: str, title: Optional[str] = None,
                           year: Optional[int] = None, keywords: Optional[str] = None,
                           accept_new: bool = False) -> str:
        """Insert or update a search specification record.

        Args:
            author: Author name
            title: Book title (optional)
            year: Publication year (optional)
            keywords: Search keywords (optional)
            accept_new: Accept NEW condition books (default: False)

        Returns:
            Search spec ID
        """
        spec_id = self.generate_search_spec_id(author, title)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO search_specs (spec_id, author, title, publication_year, keywords, accept_new)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(spec_id) DO UPDATE SET
                author = excluded.author,
                title = excluded.title,
                publication_year = excluded.publication_year,
                keywords = excluded.keywords,
                accept_new = excluded.accept_new
        """, (spec_id, author, title, year, keywords, accept_new))
        self.conn.commit()
        logger.debug(f"Upserted search spec: {spec_id} - {author}" +
                    (f" - {title}" if title else "") +
                    (f" [accept_new={accept_new}]" if accept_new else ""))
        return spec_id

    def get_enabled_search_specs(self) -> List[Dict]:
        """Get all enabled search specifications for checking.

        Returns:
            List of search spec dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT spec_id, author, title, publication_year, keywords, accept_new, last_checked
            FROM search_specs
            WHERE check_enabled = 1
            ORDER BY author, title
        """)
        return [dict(row) for row in cursor.fetchall()]

    def update_search_spec_checked(self, spec_id: str):
        """Update last_checked timestamp for a search specification.

        Args:
            spec_id: Search spec ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE search_specs
            SET last_checked = CURRENT_TIMESTAMP
            WHERE spec_id = ?
        """, (spec_id,))
        self.conn.commit()

    def get_unnotified_listings_by_author(self) -> Dict[str, List[Dict]]:
        """Get unnotified listings grouped by author.

        Returns:
            Dictionary mapping author names to lists of listings
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                b.author,
                b.title,
                b.isbn,
                b.publication_year,
                l.listing_hash,
                l.book_id,
                l.seller,
                l.price,
                l.currency,
                l.condition,
                l.url
            FROM listings l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.notified = 0 AND l.is_active = 1
            ORDER BY b.author, l.price DESC
        """)

        # Group by author
        grouped = {}
        for row in cursor.fetchall():
            author = row['author'] or 'Unknown Author'
            if author not in grouped:
                grouped[author] = []

            listing = {
                'listing_hash': row['listing_hash'],
                'book_id': row['book_id'],
                'title': row['title'],
                'author': author,
                'isbn': row['isbn'],
                'publication_year': row['publication_year'],
                'seller': row['seller'],
                'price': row['price'],
                'currency': row['currency'],
                'condition': row['condition'],
                'url': row['url']
            }
            grouped[author].append(listing)

        return grouped

    def get_stored_listing_hashes(self, book_id: str) -> set:
        """Get all stored listing hashes for a book.

        Args:
            book_id: Book ID

        Returns:
            Set of listing hashes
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT listing_hash
            FROM listings
            WHERE book_id = ? AND is_active = 1
        """, (book_id,))
        return {row['listing_hash'] for row in cursor.fetchall()}

    def save_listings(self, listings: List[Dict]) -> int:
        """Save new listings to database.

        Args:
            listings: List of listing dictionaries

        Returns:
            Number of new listings saved
        """
        if not listings:
            return 0

        cursor = self.conn.cursor()
        saved_count = 0

        for listing in listings:
            listing_hash = self.generate_listing_hash(listing)

            try:
                cursor.execute("""
                    INSERT INTO listings
                    (listing_hash, book_id, seller, price, currency, condition, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    listing_hash,
                    listing.get('book_id'),
                    listing.get('seller'),
                    listing.get('price'),
                    listing.get('currency', 'USD'),
                    listing.get('condition'),
                    listing.get('url')
                ))
                saved_count += 1
                logger.debug(f"Saved new listing: {listing_hash[:8]}...")
            except sqlite3.IntegrityError:
                # Listing already exists, update last_seen
                cursor.execute("""
                    UPDATE listings
                    SET last_seen = CURRENT_TIMESTAMP
                    WHERE listing_hash = ?
                """, (listing_hash,))
                logger.debug(f"Updated existing listing: {listing_hash[:8]}...")

        self.conn.commit()
        logger.info(f"Saved {saved_count} new listings")
        return saved_count

    def get_unnotified_listings(self) -> List[Dict]:
        """Get all new listings that haven't been notified yet.

        Returns:
            List of listing dictionaries with book info
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                l.listing_hash,
                l.book_id,
                l.seller,
                l.price,
                l.currency,
                l.condition,
                l.url,
                l.first_seen,
                b.title,
                b.author,
                b.isbn,
                b.publication_year
            FROM listings l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.notified = 0 AND l.is_active = 1
            ORDER BY b.title, l.price
        """)

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        logger.info(f"Found {len(results)} unnotified listings")
        return results

    def mark_listings_notified(self, listing_hashes: List[str]):
        """Mark listings as notified.

        Args:
            listing_hashes: List of listing hash IDs
        """
        if not listing_hashes:
            return

        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(listing_hashes))
        cursor.execute(f"""
            UPDATE listings
            SET notified = 1
            WHERE listing_hash IN ({placeholders})
        """, listing_hashes)
        self.conn.commit()
        logger.info(f"Marked {len(listing_hashes)} listings as notified")

    def get_books_for_checking(self, limit: Optional[int] = None) -> List[Dict]:
        """Get books that should be checked.

        Args:
            limit: Maximum number of books to return

        Returns:
            List of book dictionaries
        """
        cursor = self.conn.cursor()
        query = """
            SELECT book_id, title, author, isbn, publication_year
            FROM books
            WHERE check_enabled = 1
            ORDER BY last_checked ASC NULLS FIRST
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        return results

    def get_statistics(self) -> Dict:
        """Get database statistics.

        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM books")
        total_books = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM listings WHERE is_active = 1")
        active_listings = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM listings WHERE notified = 0")
        unnotified_listings = cursor.fetchone()['count']

        return {
            'total_books': total_books,
            'active_listings': active_listings,
            'unnotified_listings': unnotified_listings
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
