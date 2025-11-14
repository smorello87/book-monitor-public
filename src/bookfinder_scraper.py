"""BookFinder.com scraper for book listings."""

import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, quote_plus

logger = logging.getLogger(__name__)


class BookFinderScraper:
    """Scraper for BookFinder.com book listings."""

    def __init__(self, base_url: str = "https://www.bookfinder.com",
                 rate_limit: int = 10, user_agent: Optional[str] = None,
                 timeout: int = 30):
        """Initialize BookFinder scraper.

        Args:
            base_url: Base URL for BookFinder
            rate_limit: Seconds to wait between requests
            user_agent: Custom user agent string
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.last_request_time = 0

        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        logger.info(f"Initialized BookFinder scraper (rate limit: {rate_limit}s)")

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            wait_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def _extract_next_data(self, html: str) -> Optional[Dict]:
        """Extract structured data from Next.js __NEXT_DATA__ script tag.

        Args:
            html: HTML content

        Returns:
            Dictionary with Next.js page props, or None if not found
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            script = soup.find('script', {'id': '__NEXT_DATA__'})

            if script and script.string:
                import json
                data = json.loads(script.string)
                page_props = data.get('props', {}).get('pageProps', {})

                if page_props:
                    logger.debug("Successfully extracted __NEXT_DATA__")
                    return page_props
        except Exception as e:
            logger.debug(f"Could not extract __NEXT_DATA__: {e}")

        return None

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch page content using Playwright for JavaScript rendering.

        Args:
            url: URL to fetch

        Returns:
            Rendered HTML content or None if failed
        """
        try:
            from playwright.sync_api import sync_playwright

            logger.info("Using Playwright (headless browser) for JavaScript rendering")

            with sync_playwright() as p:
                # Launch headless browser
                browser = p.chromium.launch(headless=True)

                # Create new page with custom user agent
                context = browser.new_context(
                    user_agent=self.user_agent,
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()

                # Navigate to URL with timeout
                logger.debug(f"Playwright navigating to: {url}")
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)

                # Wait for listings to load (try multiple selectors)
                try:
                    # Wait for any of these selectors that might contain listings
                    page.wait_for_selector(
                        'div.result-item, div.bf-book, tr.result-row, [data-isbn], [data-csa-c-item-type="search-offer"], button[role="tab"]',
                        timeout=15000
                    )
                    logger.debug("Page content loaded successfully")
                except Exception as e:
                    logger.debug(f"No expected selectors found, but continuing: {e}")

                # Additional wait for JavaScript to fully render
                page.wait_for_timeout(3000)

                # Get rendered HTML
                html = page.content()

                # Close browser
                browser.close()

                logger.info("Playwright fetch successful")
                return html

        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && python -m playwright install chromium")
            return None
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return None

    def _parse_listings_from_json(self, listings_data: List[Dict], book_identifier: str) -> List[Dict]:
        """Parse listings from JSON data structure.

        Args:
            listings_data: List of listing dictionaries from JSON
            book_identifier: ISBN or book_id

        Returns:
            List of normalized listing dictionaries
        """
        results = []

        for item in listings_data:
            try:
                listing = {
                    'book_id': book_identifier,
                    'seller': item.get('seller', {}).get('name') if isinstance(item.get('seller'), dict) else item.get('seller'),
                    'price': float(item.get('price', {}).get('amount', 0)) if isinstance(item.get('price'), dict) else item.get('price'),
                    'currency': item.get('price', {}).get('currency', 'USD') if isinstance(item.get('price'), dict) else item.get('currency', 'USD'),
                    'condition': item.get('condition'),
                    'url': item.get('url') or item.get('link') or item.get('href')
                }

                # Only add if we have minimum required fields
                if listing.get('seller') or listing.get('price'):
                    results.append(listing)

            except Exception as e:
                logger.warning(f"Error parsing listing from JSON: {e}")
                continue

        return results

    def search_by_isbn(self, isbn: str, max_price: Optional[float] = None) -> List[Dict]:
        """Search for book listings by ISBN using direct ISBN endpoint.

        Args:
            isbn: Book ISBN (10 or 13 digits)
            max_price: Maximum price filter (optional)

        Returns:
            List of listing dictionaries
        """
        # Clean ISBN
        clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())

        if not clean_isbn:
            logger.warning(f"Invalid ISBN: {isbn}")
            return []

        logger.info(f"Searching BookFinder for ISBN: {clean_isbn}" +
                   (f" (max price: ${max_price})" if max_price else ""))

        try:
            # Use direct ISBN endpoint: /isbn/{isbn}/
            search_url = f"{self.base_url}/isbn/{clean_isbn}/"
            params = {
                'viewAll': 'true',  # Get full listings page instead of grouped results
                'currency': 'USD',
                'destination': 'US'
            }

            # Add max price filter if specified
            if max_price is not None:
                params['maxPrice'] = str(max_price)

            # Build full URL
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
            full_url = f"{search_url}?{param_str}"

            # Rate limit
            self._rate_limit()

            # Make request
            logger.debug(f"Fetching: {full_url}")
            response = self.session.get(full_url, timeout=self.timeout)
            response.raise_for_status()

            # Strategy 1: Try to extract structured data from __NEXT_DATA__ (fast)
            next_data = self._extract_next_data(response.text)
            if next_data and 'listings' in next_data:
                logger.info("Using __NEXT_DATA__ extraction (fast path)")
                listings = self._parse_listings_from_json(next_data['listings'], clean_isbn)
                if listings:
                    logger.info(f"Found {len(listings)} listings for ISBN {clean_isbn}")
                    return listings

            # Strategy 2: Fall back to HTML parsing
            logger.debug("__NEXT_DATA__ not available, using HTML parsing")
            listings = self._parse_search_results(response.text, clean_isbn)
            if listings:
                logger.info(f"Found {len(listings)} listings for ISBN {clean_isbn}")
                return listings

            # Strategy 3: Fall back to Playwright (slow but handles JavaScript)
            logger.info("No listings found with fast methods, trying Playwright...")
            rendered_html = self._fetch_with_playwright(full_url)
            if rendered_html:
                # Try __NEXT_DATA__ first on rendered page
                next_data = self._extract_next_data(rendered_html)
                if next_data and 'listings' in next_data:
                    listings = self._parse_listings_from_json(next_data['listings'], clean_isbn)
                    if listings:
                        logger.info(f"Found {len(listings)} listings for ISBN {clean_isbn} (via Playwright)")
                        return listings

                # Fall back to HTML parsing on rendered page
                listings = self._parse_search_results(rendered_html, clean_isbn)
                logger.info(f"Found {len(listings)} listings for ISBN {clean_isbn} (via Playwright)")
                return listings

            logger.info(f"No listings found for ISBN {clean_isbn}")
            return []

        except requests.RequestException as e:
            logger.error(f"Error fetching BookFinder page: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing BookFinder results: {e}")
            return []

    def search_by_title_author(self, title: str, author: Optional[str] = None,
                                book_id: Optional[str] = None, year: Optional[int] = None,
                                keywords: Optional[str] = None,
                                filter_condition: str = 'used',
                                max_price: Optional[float] = None) -> List[Dict]:
        """Search for book listings by title and author.

        Args:
            title: Book title
            author: Book author (optional)
            book_id: Unique book identifier for tracking
            year: Publication year (optional)
            keywords: Search keywords (optional)
            filter_condition: Condition filter ('used', 'any', 'new')
            max_price: Maximum price filter (optional)

        Returns:
            List of listing dictionaries
        """
        if not title:
            logger.warning("No title provided for search")
            return []

        # Extract author's last name if provided
        author_lastname = None
        if author:
            # Split by common delimiters and get last part
            parts = re.split(r'[;,]', author)
            if parts:
                # Get first author's last name
                first_author = parts[0].strip()
                # Split by space and get last word
                name_parts = first_author.split()
                if name_parts:
                    author_lastname = name_parts[-1]

        logger.info(f"Searching BookFinder for: {title} by {author_lastname or 'unknown author'}" +
                   (f" (max price: ${max_price})" if max_price else ""))

        try:
            # Construct search URL with ADVANCED mode and separate fields
            # This prevents matching random authors with the same last name
            search_url = f"{self.base_url}/search/"
            params = {
                'author': author_lastname or '',
                'title': title or '',
                'keywords': keywords or '',
                'isbn': '',
                'binding': 'ANY',
                'condition': 'ANY',
                'currency': 'USD',
                'destination': 'US',
                'language': 'ANY',
                'mode': 'ADVANCED',
                'viewAll': 'true'  # Get full listings page instead of grouped results
            }

            # Add publication year range if provided (BookFinder uses min/max year params)
            if year:
                params['publicationMinYear'] = str(year)
                params['publicationMaxYear'] = str(year)

            # Add max price filter if specified
            if max_price is not None:
                params['maxPrice'] = str(max_price)

            # Build full URL
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
            full_url = f"{search_url}?{param_str}"

            # Rate limit
            self._rate_limit()

            # Make request
            logger.debug(f"Fetching: {full_url}")
            response = self.session.get(full_url, timeout=self.timeout)
            response.raise_for_status()

            # Strategy 1: Try to extract structured data from __NEXT_DATA__ (fast)
            next_data = self._extract_next_data(response.text)
            if next_data and 'listings' in next_data:
                logger.info("Using __NEXT_DATA__ extraction (fast path)")
                listings = self._parse_listings_from_json(next_data['listings'], book_id or title)
                if listings:
                    listings = self._filter_by_condition(listings, filter_condition)
                    logger.info(f"Found {len(listings)} listings for: {title} by {author_lastname or 'unknown author'}")
                    return listings

            # Strategy 2: Fall back to HTML parsing
            logger.debug("__NEXT_DATA__ not available, using HTML parsing")
            listings = self._parse_search_results(response.text, book_id or title)
            if listings:
                listings = self._filter_by_condition(listings, filter_condition)
                logger.info(f"Found {len(listings)} listings for: {title} by {author_lastname or 'unknown author'}")
                return listings

            # Strategy 3: Fall back to Playwright (slow but handles JavaScript)
            logger.info("No listings found with fast methods, trying Playwright...")
            rendered_html = self._fetch_with_playwright(full_url)
            if rendered_html:
                # Try __NEXT_DATA__ first on rendered page
                next_data = self._extract_next_data(rendered_html)
                if next_data and 'listings' in next_data:
                    listings = self._parse_listings_from_json(next_data['listings'], book_id or title)
                    if listings:
                        listings = self._filter_by_condition(listings, filter_condition)
                        logger.info(f"Found {len(listings)} listings for: {title} by {author_lastname or 'unknown author'} (via Playwright)")
                        return listings

                # Fall back to HTML parsing on rendered page
                listings = self._parse_search_results(rendered_html, book_id or title)
                listings = self._filter_by_condition(listings, filter_condition)
                logger.info(f"Found {len(listings)} listings for: {title} by {author_lastname or 'unknown author'} (via Playwright)")
                return listings

            logger.info(f"No listings found for: {title} by {author_lastname or 'unknown author'}")
            return []

        except requests.RequestException as e:
            logger.error(f"Error fetching BookFinder page: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing BookFinder results: {e}")
            return []

    def search_by_author_only(self, author: str, author_id: Optional[str] = None,
                               filter_condition: str = 'used', year: Optional[int] = None,
                               keywords: Optional[str] = None,
                               max_price: Optional[float] = None) -> List[Dict]:
        """Search for ALL books by an author (no title specified).

        Args:
            author: Full author name (e.g., "Bernardino Ciambelli")
            author_id: Unique author identifier for tracking (optional)
            filter_condition: Condition filter ('used', 'any', 'new')
                            'used' = exclude New condition listings
                            'any' = all conditions
                            'new' = only New condition
            year: Publication year (optional)
            keywords: Search keywords (optional)
            max_price: Maximum price filter (optional)

        Returns:
            List of listing dictionaries with enhanced book info

        Note:
            This searches by author last name only, which may return books
            by different authors with the same surname. Results include
            book titles extracted from listings for disambiguation.
        """
        if not author:
            logger.warning("No author provided for search")
            return []

        # Extract author's last name
        author_lastname = None
        if author:
            # Split by common delimiters and get last part
            parts = re.split(r'[;,]', author)
            if parts:
                # Get first author's last name
                first_author = parts[0].strip()
                # Split by space and get last word
                name_parts = first_author.split()
                if name_parts:
                    author_lastname = name_parts[-1]

        logger.info(f"Searching BookFinder for all books by: {author} (lastname: {author_lastname})" +
                   (f" (max price: ${max_price})" if max_price else ""))

        try:
            # Construct search URL with ADVANCED mode, author only (NO title)
            search_url = f"{self.base_url}/search/"
            params = {
                'author': author,  # Use FULL author name, not just lastname
                'title': '',  # Empty - we want ALL books by this author
                'keywords': keywords or '',
                'isbn': '',
                'binding': 'ANY',
                'condition': 'ANY',
                'currency': 'USD',
                'destination': 'US',
                'language': 'ANY',
                'mode': 'ADVANCED',
                'viewAll': 'true'  # Get full listings page instead of grouped results
            }

            # Add publication year range if provided (BookFinder uses min/max year params)
            if year:
                params['publicationMinYear'] = str(year)
                params['publicationMaxYear'] = str(year)

            # Add max price filter if specified
            if max_price is not None:
                params['maxPrice'] = str(max_price)

            # Build full URL
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
            full_url = f"{search_url}?{param_str}"

            # Rate limit
            self._rate_limit()

            # Make request
            logger.debug(f"Fetching: {full_url}")
            response = self.session.get(full_url, timeout=self.timeout)
            response.raise_for_status()

            # Strategy 1: Try to extract structured data from __NEXT_DATA__ (fast)
            next_data = self._extract_next_data(response.text)
            if next_data and 'listings' in next_data:
                logger.info("Using __NEXT_DATA__ extraction (fast path)")
                listings = self._parse_listings_from_json(next_data['listings'], author_id or author)
                if listings:
                    listings = self._enhance_and_filter_listings(listings, author, filter_condition)
                    logger.info(f"Found {len(listings)} listings for author: {author}")
                    return listings

            # Strategy 2: Fall back to HTML parsing
            logger.debug("__NEXT_DATA__ not available, using HTML parsing")
            listings = self._parse_author_search_results(response.text, author)
            if listings:
                listings = self._enhance_and_filter_listings(listings, author, filter_condition)
                logger.info(f"Found {len(listings)} listings for author: {author}")
                return listings

            # Strategy 3: Fall back to Playwright (slow but handles JavaScript)
            logger.info("No listings found with fast methods, trying Playwright...")
            rendered_html = self._fetch_with_playwright(full_url)
            if rendered_html:
                # Try __NEXT_DATA__ first on rendered page
                next_data = self._extract_next_data(rendered_html)
                if next_data and 'listings' in next_data:
                    listings = self._parse_listings_from_json(next_data['listings'], author_id or author)
                    if listings:
                        listings = self._enhance_and_filter_listings(listings, author, filter_condition)
                        logger.info(f"Found {len(listings)} listings for author: {author} (via Playwright)")
                        return listings

                # Fall back to HTML parsing on rendered page
                listings = self._parse_author_search_results(rendered_html, author)
                listings = self._enhance_and_filter_listings(listings, author, filter_condition)
                logger.info(f"Found {len(listings)} listings for author: {author} (via Playwright)")
                return listings

            logger.info(f"No listings found for author: {author}")
            return []

        except requests.RequestException as e:
            logger.error(f"Error fetching BookFinder page: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing BookFinder results for author {author}: {e}")
            return []

    def _parse_author_search_results(self, html: str, author: str) -> List[Dict]:
        """Parse search results for author-only search (extracts book titles).

        Args:
            html: HTML content
            author: Author name being searched

        Returns:
            List of listing dictionaries with book titles
        """
        soup = BeautifulSoup(html, 'lxml')
        listings = []

        # Check if no results
        no_results = soup.find('div', class_='no-results')
        if no_results:
            logger.info(f"No results found for author: {author}")
            return []

        # Find all book listings using data-csa-c-item-type="search-offer"
        listing_containers = soup.find_all(attrs={'data-csa-c-item-type': 'search-offer'})

        if not listing_containers:
            # Fallback to old structure if needed
            listing_containers = (
                soup.find_all('div', class_='result-item') or
                soup.find_all('div', class_='bf-book') or
                soup.find_all('tr', class_='result-row')
            )

        logger.debug(f"Found {len(listing_containers)} potential listing containers for author: {author}")

        for container in listing_containers:
            listing = self._parse_author_listing(container, author)
            if listing:
                listings.append(listing)

        return listings

    def _parse_author_listing(self, element, author: str) -> Optional[Dict]:
        """Parse a single listing element for author search (includes book title).

        Args:
            element: BeautifulSoup element
            author: Author name being searched

        Returns:
            Listing dictionary with book title, or None
        """
        try:
            listing = {}

            # Try new BookFinder structure first (data-csa-c-* attributes)
            if element.get('data-csa-c-item-type') == 'search-offer':
                # Extract title from data attribute
                title = element.get('data-csa-c-title', '')
                if title:
                    listing['title'] = title.strip()

                # Extract actual authors from BookFinder data
                listing_authors = element.get('data-csa-c-authors', '')
                if listing_authors:
                    listing['listing_authors'] = listing_authors  # Store for filtering

                # Store searched author
                listing['author'] = author

                # Extract from data attributes
                seller = element.get('data-csa-c-affiliate', '')
                if seller:
                    listing['seller'] = seller.replace('_', ' ').title()

                # Extract price
                price_str = element.get('data-csa-c-usdprice', '')
                if price_str:
                    try:
                        listing['price'] = float(price_str)
                        listing['currency'] = 'USD'
                    except ValueError:
                        pass

                # Extract condition
                condition = element.get('data-csa-c-condition', '')
                if condition:
                    listing['condition'] = condition.title()

                # Extract URL from clickout link
                link_elem = element.find('a', attrs={'data-csa-c-action': 'clickout'})
                if link_elem and link_elem.get('href'):
                    listing['url'] = link_elem['href']

                # Only return if we have minimum required fields (title + price or seller)
                if listing.get('title') and (listing.get('seller') or listing.get('price')):
                    logger.debug(f"Parsed listing: {listing.get('title', 'Unknown')} - {listing.get('seller', 'Unknown')} - ${listing.get('price', 'N/A')}")
                    return listing

            return None

        except Exception as e:
            logger.warning(f"Error parsing author listing element: {e}")
            return None

    def _filter_by_condition(self, listings: List[Dict], filter_condition: str) -> List[Dict]:
        """Filter listings by condition only (no author filtering).

        Args:
            listings: List of listing dictionaries
            filter_condition: Condition filter ('used', 'any', 'new')

        Returns:
            Filtered list of listings
        """
        if filter_condition == 'any':
            return listings

        filtered = []
        for listing in listings:
            condition = listing.get('condition', '').lower()

            if filter_condition == 'used':
                # Skip "New" condition listings
                if condition == 'new':
                    logger.debug(f"Skipping NEW listing: ${listing.get('price', 'N/A')} - {condition}")
                    continue
            elif filter_condition == 'new':
                # Only include "New" condition listings
                if condition != 'new':
                    continue

            filtered.append(listing)

        logger.debug(f"Condition filter: {len(listings)} → {len(filtered)} listings (filter={filter_condition})")
        return filtered

    def _enhance_and_filter_listings(self, listings: List[Dict], author: str, filter_condition: str) -> List[Dict]:
        """Enhance listings with author info and filter by condition and author name.

        Args:
            listings: List of listing dictionaries
            author: Full author name to filter by (e.g., "Andre Luotto")
            filter_condition: Condition filter ('used', 'any', 'new')

        Returns:
            Filtered list of listings with author info
        """
        filtered = []

        # Extract author's first and last name for filtering
        author_parts = author.strip().split()
        author_firstname = author_parts[0].lower() if author_parts else ''
        author_lastname = author_parts[-1].lower() if author_parts else ''

        for listing in listings:
            # Filter by author using listing_authors data from BookFinder
            listing_authors = listing.get('listing_authors', '').lower()

            # CRITICAL: Reject listings without author data - we cannot verify them
            if not listing_authors:
                logger.debug(f"Skipping - no author data to verify for '{listing.get('title', 'Unknown')}'")
                continue

            # Verify the listing author matches our searched author
            if author_firstname and author_lastname:
                # Check if the author's first name (or initial) appears with their last name
                # Examples: "Andre Luotto", "A. Luotto", "Andy Luotto"

                # Build variations to check
                variations = [author_firstname, author_firstname[0]]  # "andre", "a"

                # Add common nickname variations
                if author_firstname == 'andre':
                    variations.extend(['andrea', 'andy', 'andrew'])
                elif author_firstname == 'bernardino':
                    variations.extend(['bernardo', 'bernard'])
                elif author_firstname == 'giuseppe':
                    variations.extend(['joseph', 'joe'])
                elif author_firstname == 'antonio':
                    variations.extend(['anthony', 'tony'])
                elif author_firstname == 'salvatore':
                    variations.extend(['sal', 'salvator'])

                # Check if any variation + lastname appears in listing authors
                found_match = False
                for var in variations:
                    # Look for patterns like "Andre Luotto" or "A. Luotto" or "Luotto, Andre"
                    if (f"{var} {author_lastname}" in listing_authors or
                        f"{var}. {author_lastname}" in listing_authors or
                        f"{author_lastname}, {var}" in listing_authors or
                        f"{author_lastname}; {var}" in listing_authors):
                        found_match = True
                        break

                if not found_match:
                    logger.debug(f"Skipping - wrong author: '{listing_authors}' (wanted: {author})")
                    continue
            elif author_lastname:
                # If we only have lastname, at least verify it appears in listing_authors
                if author_lastname not in listing_authors:
                    logger.debug(f"Skipping - lastname mismatch: '{listing_authors}' (wanted: {author_lastname})")
                    continue

            # Add author if not present
            if 'author' not in listing:
                listing['author'] = author

            # Generate book_id from title+author if not present
            if 'book_id' not in listing and listing.get('title'):
                import hashlib
                book_key = f"{listing['title']}|{author}".lower()
                listing['book_id'] = hashlib.sha256(book_key.encode()).hexdigest()[:16]

            # Filter by condition (normalize to lowercase for comparison)
            condition = listing.get('condition', '').lower()

            if filter_condition == 'used':
                # Skip "New" condition listings
                if condition == 'new':
                    logger.debug(f"Skipping NEW listing: {listing.get('title', 'Unknown')} - ${listing.get('price', 'N/A')}")
                    continue
            elif filter_condition == 'new':
                # Only include "New" condition listings
                if condition != 'new':
                    continue
            # 'any' includes all conditions

            filtered.append(listing)

        logger.debug(f"Filtered {len(listings)} → {len(filtered)} listings (condition={filter_condition}, author={author})")
        return filtered

    def _parse_search_results(self, html: str, book_identifier: str) -> List[Dict]:
        """Parse search results page.

        Args:
            html: HTML content
            book_identifier: ISBN or book_id being searched

        Returns:
            List of listing dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        listings = []

        # Check if no results
        no_results = soup.find('div', class_='no-results')
        if no_results:
            logger.info(f"No results found for: {book_identifier}")
            return []

        # Find all book listings using data-csa-c-item-type="search-offer" (new BookFinder structure)
        listing_containers = soup.find_all(attrs={'data-csa-c-item-type': 'search-offer'})

        if not listing_containers:
            # Fallback to old structure if needed
            listing_containers = (
                soup.find_all('div', class_='result-item') or
                soup.find_all('div', class_='bf-book') or
                soup.find_all('tr', class_='result-row')
            )

        logger.debug(f"Found {len(listing_containers)} potential listing containers")

        for container in listing_containers:
            listing = self._parse_listing(container, book_identifier)
            if listing:
                listings.append(listing)

        return listings

    def _parse_listing(self, element, book_identifier: str) -> Optional[Dict]:
        """Parse a single listing element.

        Args:
            element: BeautifulSoup element
            book_identifier: ISBN or book_id being searched

        Returns:
            Listing dictionary or None
        """
        try:
            # Only store book_id if it's a proper hash (16 hex chars) or ISBN
            # Don't store if it's just a title string - let caller generate proper hash
            listing = {}
            if book_identifier and (len(book_identifier) == 16 or book_identifier.isdigit()):
                listing['book_id'] = book_identifier

            # Try new BookFinder structure first (data-csa-c-* attributes)
            if element.get('data-csa-c-item-type') == 'search-offer':
                # Extract from data attributes
                seller = element.get('data-csa-c-affiliate', '')
                if seller:
                    listing['seller'] = seller.replace('_', ' ').title()

                # Extract price
                price_str = element.get('data-csa-c-usdprice', '')
                if price_str:
                    try:
                        listing['price'] = float(price_str)
                        listing['currency'] = 'USD'
                    except ValueError:
                        pass

                # Extract condition
                condition = element.get('data-csa-c-condition', '')
                if condition:
                    listing['condition'] = condition.title()

                # Extract URL from clickout link
                link_elem = element.find('a', attrs={'data-csa-c-action': 'clickout'})
                if link_elem and link_elem.get('href'):
                    listing['url'] = link_elem['href']

                # Only return if we have minimum required fields
                if listing.get('seller') or listing.get('price'):
                    logger.debug(f"Parsed listing: {listing.get('seller', 'Unknown')} - ${listing.get('price', 'N/A')}")
                    return listing
                return None

            # Fallback to old parsing method for legacy HTML structure
            # Extract seller
            seller_elem = (
                element.find('span', class_='seller-name') or
                element.find('a', class_='seller') or
                element.find('div', class_='seller')
            )
            if seller_elem:
                listing['seller'] = seller_elem.get_text(strip=True)

            # Extract price
            price_elem = (
                element.find('span', class_='price') or
                element.find('div', class_='price') or
                element.find(string=re.compile(r'\$[\d,]+\.?\d*'))
            )
            if price_elem:
                price_text = price_elem if isinstance(price_elem, str) else price_elem.get_text(strip=True)
                listing['price'] = self._parse_price(price_text)
                listing['currency'] = 'USD'

            # Extract condition
            condition_elem = (
                element.find('span', class_='condition') or
                element.find('div', class_='condition') or
                element.find(string=re.compile(r'\b(New|Used|Fine|Good|Fair|Poor|Very Good)\b', re.I))
            )
            if condition_elem:
                condition_text = condition_elem if isinstance(condition_elem, str) else condition_elem.get_text(strip=True)
                listing['condition'] = condition_text.strip()

            # Extract URL
            link_elem = element.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                listing['url'] = urljoin(self.base_url, href)

            # Only return if we have minimum required fields
            if 'seller' in listing or 'price' in listing:
                logger.debug(f"Parsed listing: {listing.get('seller', 'Unknown')} - ${listing.get('price', 'N/A')}")
                return listing

            return None

        except Exception as e:
            logger.warning(f"Error parsing listing element: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text.

        Args:
            price_text: Price string (e.g., "$12.99", "12.99 USD")

        Returns:
            Price as float or None
        """
        try:
            # Remove currency symbols and extract number
            clean_text = re.sub(r'[^\d.,]', '', price_text)
            # Remove thousands separators
            clean_text = clean_text.replace(',', '')
            # Convert to float
            return float(clean_text)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse price: {price_text}")
            return None

    def test_connection(self) -> bool:
        """Test connection to BookFinder.

        Returns:
            True if connection successful
        """
        try:
            self._rate_limit()
            response = self.session.get(self.base_url, timeout=self.timeout)
            response.raise_for_status()
            logger.info("BookFinder connection test successful")
            return True
        except Exception as e:
            logger.error(f"BookFinder connection test failed: {e}")
            return False


def main():
    """Test function for development."""
    import yaml

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize scraper
    bf_config = config['bookfinder']
    scraper = BookFinderScraper(
        base_url=bf_config['base_url'],
        rate_limit=bf_config['rate_limit_seconds'],
        user_agent=bf_config['user_agent'],
        timeout=bf_config['timeout']
    )

    # Test connection
    if scraper.test_connection():
        print("✓ Connection successful!")

        # Test search with a known ISBN (The Great Gatsby)
        test_isbn = "9780743273565"
        print(f"\nSearching for ISBN: {test_isbn}")
        listings = scraper.search_by_isbn(test_isbn)

        if listings:
            print(f"\nFound {len(listings)} listings:")
            for i, listing in enumerate(listings[:5], 1):
                print(f"\n{i}. {listing.get('seller', 'Unknown')}")
                print(f"   Price: ${listing.get('price', 'N/A')}")
                print(f"   Condition: {listing.get('condition', 'N/A')}")
                print(f"   URL: {listing.get('url', 'N/A')}")
        else:
            print("No listings found")
    else:
        print("✗ Connection failed!")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
