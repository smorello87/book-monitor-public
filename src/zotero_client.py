"""Zotero API client for fetching library items."""

from pyzotero import zotero
from typing import List, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Client for interacting with Zotero API."""

    def __init__(self, library_id: str, library_type: str = 'user',
                 api_key: Optional[str] = None):
        """Initialize Zotero client.

        Args:
            library_id: Zotero library ID
            library_type: 'user' or 'group'
            api_key: API key (optional for public libraries)
        """
        self.library_id = library_id
        self.library_type = library_type
        self.api_key = api_key
        self.client = zotero.Zotero(library_id, library_type, api_key)
        logger.info(f"Initialized Zotero client for {library_type} library: {library_id}")

    def fetch_books(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all books from the Zotero library.

        Args:
            limit: Maximum number of books to fetch (None for all)

        Returns:
            List of book dictionaries with ISBN, title, author, etc.
        """
        logger.info("Fetching books from Zotero library...")

        try:
            # Fetch items, filtering for books
            items = self.client.items(itemType='book', limit=limit)
            logger.info(f"Fetched {len(items)} items from Zotero")

            books = []
            for item in items:
                book = self._extract_book_data(item)
                if book:
                    books.append(book)

            logger.info(f"Extracted {len(books)} books with valid data")
            return books

        except Exception as e:
            logger.error(f"Error fetching books from Zotero: {e}")
            raise

    def fetch_books_with_isbn(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch books that have ISBN numbers.

        Args:
            limit: Maximum number of books to fetch (None for all)

        Returns:
            List of book dictionaries with ISBN
        """
        all_books = self.fetch_books(limit=limit)
        books_with_isbn = [book for book in all_books if book.get('isbn')]

        logger.info(f"Filtered to {len(books_with_isbn)} books with ISBN")
        return books_with_isbn

    def _extract_book_data(self, item: Dict) -> Optional[Dict]:
        """Extract relevant book data from Zotero item.

        Args:
            item: Zotero item dictionary

        Returns:
            Cleaned book dictionary or None if invalid
        """
        try:
            data = item.get('data', {})

            # Extract ISBN (prefer ISBN-13, fall back to ISBN-10)
            isbn = self._clean_isbn(data.get('ISBN', ''))

            # Extract creators (authors)
            creators = data.get('creators', [])
            authors = []
            for creator in creators:
                if creator.get('creatorType') in ['author', 'editor']:
                    name = creator.get('name')
                    if not name:
                        # Construct from firstName and lastName
                        first = creator.get('firstName', '')
                        last = creator.get('lastName', '')
                        name = f"{first} {last}".strip()
                    if name:
                        authors.append(name)

            author_str = '; '.join(authors) if authors else None

            # Extract other fields
            title = data.get('title')
            if not title:
                logger.debug("Skipping item without title")
                return None

            publication_year = data.get('date', '')
            # Extract just the year if full date is provided
            if publication_year:
                # Try to extract 4-digit year
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', publication_year)
                if year_match:
                    publication_year = year_match.group(0)

            book = {
                'isbn': isbn,
                'title': title,
                'author': author_str,
                'publication_year': publication_year,
                'zotero_key': item.get('key'),
                'item_type': data.get('itemType'),
            }

            return book

        except Exception as e:
            logger.warning(f"Error extracting book data: {e}")
            return None

    def _clean_isbn(self, isbn: str) -> Optional[str]:
        """Clean and validate ISBN.

        Args:
            isbn: Raw ISBN string

        Returns:
            Cleaned ISBN or None
        """
        if not isbn:
            return None

        # Remove hyphens, spaces, and other non-alphanumeric characters
        import re
        cleaned = re.sub(r'[^0-9X]', '', isbn.upper())

        # Check if it's a valid length (10 or 13 digits)
        if len(cleaned) in [10, 13]:
            return cleaned

        # If multiple ISBNs are present (separated by commas, semicolons, etc.)
        # Take the first one
        parts = re.split(r'[,;\s]+', isbn)
        for part in parts:
            cleaned = re.sub(r'[^0-9X]', '', part.upper())
            if len(cleaned) in [10, 13]:
                return cleaned

        logger.debug(f"Invalid ISBN format: {isbn}")
        return None

    def test_connection(self) -> bool:
        """Test connection to Zotero API.

        Returns:
            True if connection successful
        """
        try:
            # Try to fetch just 1 item to test connection
            items = self.client.items(limit=1)
            logger.info(f"Connection test successful. Library has items: {len(items) > 0}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_library_info(self) -> Dict:
        """Get information about the library.

        Returns:
            Dictionary with library statistics
        """
        try:
            # Get total count of items
            all_items = self.client.items()
            books = self.client.items(itemType='book')

            return {
                'total_items': len(all_items),
                'total_books': len(books),
                'library_id': self.library_id,
                'library_type': self.library_type
            }
        except Exception as e:
            logger.error(f"Error getting library info: {e}")
            return {}


def main():
    """Test function for development."""
    import yaml

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize client
    zot_config = config['zotero']
    client = ZoteroClient(
        library_id=zot_config['library_id'],
        library_type=zot_config['library_type']
    )

    # Test connection
    if client.test_connection():
        print("✓ Connection successful!")

        # Get library info
        info = client.get_library_info()
        print(f"\nLibrary Info:")
        print(f"  Total items: {info.get('total_items', 0)}")
        print(f"  Total books: {info.get('total_books', 0)}")

        # Fetch books with ISBN
        books = client.fetch_books_with_isbn(limit=5)
        print(f"\nFound {len(books)} books with ISBN:")
        for book in books:
            print(f"  - {book['title']} by {book['author']} (ISBN: {book['isbn']})")
    else:
        print("✗ Connection failed!")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
