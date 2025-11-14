"""Email digest generation and delivery."""

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime
from typing import List, Dict, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class DigestEmailer:
    """Email digest generator and sender using Brevo (SendinBlue) API."""

    def __init__(self, api_key: str, sender_email: str, sender_name: str,
                 recipient_email: str):
        """Initialize email client.

        Args:
            api_key: Brevo API key
            sender_email: Sender email address
            sender_name: Sender name
            recipient_email: Recipient email address
        """
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.recipient_email = recipient_email

        # Configure Brevo API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        logger.info(f"Initialized email client for {recipient_email}")

    def send_digest(self, listings: List[Dict]) -> bool:
        """Send daily digest email with new listings.

        Args:
            listings: List of listing dictionaries with book info

        Returns:
            True if email sent successfully
        """
        if not listings:
            logger.info("No new listings to send")
            return False

        # Group listings by book
        grouped = self._group_listings_by_book(listings)

        # Generate email content
        subject = self._generate_subject(grouped)
        html_content = self._generate_html(grouped)
        text_content = self._generate_text(grouped)

        # Send email
        return self._send_email(subject, html_content, text_content)

    def _group_listings_by_book(self, listings: List[Dict]) -> Dict:
        """Group listings by author, then by book (for author-based system).

        Args:
            listings: List of listing dictionaries

        Returns:
            Dictionary mapping author to {books: {title: {book_info, listings}}}
        """
        grouped = defaultdict(lambda: defaultdict(lambda: {'listings': []}))

        for listing in listings:
            author = listing.get('author', 'Unknown Author')
            title = listing.get('title', 'Unknown Title')

            # Store book info if not already stored
            if not grouped[author][title].get('book_info'):
                grouped[author][title]['book_info'] = {
                    'title': title,
                    'author': author,
                    'isbn': listing.get('isbn'),
                    'publication_year': listing.get('publication_year', '')
                }

            # Add listing
            grouped[author][title]['listings'].append({
                'seller': listing.get('seller', 'Unknown'),
                'price': listing.get('price'),
                'currency': listing.get('currency', 'USD'),
                'condition': listing.get('condition', 'Unknown'),
                'url': listing.get('url', '#'),
                'first_seen': listing.get('first_seen')
            })

        # Sort listings by price (HIGH to LOW) within each book
        for author in grouped:
            for title in grouped[author]:
                grouped[author][title]['listings'].sort(
                    key=lambda x: x['price'] if x['price'] is not None else 0,
                    reverse=True  # Highest price first
                )

        # Convert nested defaultdict to dict
        return {author: dict(books) for author, books in grouped.items()}

    def _generate_subject(self, grouped: Dict) -> str:
        """Generate email subject line for author-based digest.

        Args:
            grouped: Grouped listings dictionary (author → books)

        Returns:
            Email subject string
        """
        total_authors = len(grouped)
        total_listings = sum(
            len(book_data['listings'])
            for author_books in grouped.values()
            for book_data in author_books.values()
        )

        if total_authors == 1:
            author = list(grouped.keys())[0]
            return f"📚 {total_listings} Books by {author}"
        else:
            return f"📚 {total_listings} Books Found - {total_authors} Authors"

    def _generate_html(self, grouped: Dict) -> str:
        """Generate HTML email content for author-based digest.

        Args:
            grouped: Grouped listings dictionary (author → books)

        Returns:
            HTML string
        """
        today = datetime.now().strftime("%B %d, %Y")
        total_authors = len(grouped)
        total_listings = sum(
            len(book_data['listings'])
            for author_books in grouped.values()
            for book_data in author_books.values()
        )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rare Books Digest</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .summary {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        .author-section {{
            margin-bottom: 40px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            background-color: #fafbfc;
        }}
        .author-name {{
            font-size: 1.5em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 20px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .book {{
            margin-bottom: 25px;
            border-left: 4px solid #95a5a6;
            padding-left: 15px;
        }}
        .book-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #34495e;
            margin-bottom: 10px;
        }}
        .listing {{
            background-color: white;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 10px;
            margin-left: 15px;
        }}
        .listing-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            gap: 40px;
        }}
        .seller {{
            font-weight: 600;
            color: #2c3e50;
            flex: 1;
        }}
        .price {{
            font-size: 1.3em;
            font-weight: bold;
            color: #c0392b;
            white-space: nowrap;
        }}
        .condition {{
            display: inline-block;
            background-color: #fef9e7;
            color: #7d6608;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .button {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 5px;
            margin-top: 10px;
        }}
        .button:hover {{
            background-color: #2980b9;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            text-align: center;
            color: #95a5a6;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Books Digest</h1>

        <div class="summary">
            <strong>Date:</strong> {today}<br>
            <strong>New Listings:</strong> {total_listings} USED books by {total_authors} author{"s" if total_authors > 1 else ""}<br>
            <strong>Sort Order:</strong> Highest price first
        </div>
"""

        # Add each author section
        for author, books in sorted(grouped.items()):
            total_author_listings = sum(len(book_data['listings']) for book_data in books.values())

            html += f"""
        <div class="author-section">
            <div class="author-name">{author} ({total_author_listings} listing{"s" if total_author_listings > 1 else ""})</div>
"""

            # Add books by this author
            for title, book_data in books.items():
                book = book_data['book_info']
                listings = book_data['listings']

                html += f"""
            <div class="book">
                <div class="book-title">{book['title']}</div>
"""

                # Add listings for this book (already sorted by price DESC)
                for listing in listings:
                    price_str = f"${listing['price']:.2f}" if listing['price'] is not None else "Price not available"

                    html += f"""
                <div class="listing">
                    <div class="listing-header">
                        <span class="seller">{listing['seller']}</span>
                        <span class="price">{price_str}</span>
                    </div>
                    <div>
                        <span class="condition">{listing['condition']}</span>
                    </div>
                    <a href="{listing['url']}" class="button">View Listing →</a>
                </div>
"""

                html += """
            </div>
"""

            html += """
        </div>
"""

        html += """
    </div>
</body>
</html>
"""
        return html

    def _generate_text(self, grouped: Dict) -> str:
        """Generate plain text email content for author-based digest.

        Args:
            grouped: Grouped listings dictionary (author → books)

        Returns:
            Plain text string
        """
        today = datetime.now().strftime("%B %d, %Y")
        total_authors = len(grouped)
        total_listings = sum(
            len(book_data['listings'])
            for author_books in grouped.values()
            for book_data in author_books.values()
        )

        text = f"""BOOKS DIGEST
{today}

New Listings: {total_listings} USED books by {total_authors} author{"s" if total_authors > 1 else ""}
Sort Order: Highest price first

{"=" * 60}

"""

        for author, books in sorted(grouped.items()):
            total_author_listings = sum(len(book_data['listings']) for book_data in books.values())

            text += f"""
{'=' * 60}
{author} ({total_author_listings} listing{"s" if total_author_listings > 1 else ""})
{'=' * 60}

"""

            for title, book_data in books.items():
                book = book_data['book_info']
                listings = book_data['listings']

                text += f"""
{book['title']}
{len(listings)} listing{"s" if len(listings) > 1 else ""}:

"""

                for i, listing in enumerate(listings, 1):
                    price_str = f"${listing['price']:.2f}" if listing['price'] is not None else "Price not available"
                    text += f"""  {i}. {listing['seller']} - {price_str}
     Condition: {listing['condition']}
     {listing['url']}

"""

                text += "-" * 60 + "\n"

        return text

    def _send_email(self, subject: str, html_content: str, text_content: str) -> bool:
        """Send email via Brevo API.

        Args:
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body

        Returns:
            True if successful
        """
        try:
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": self.recipient_email}],
                sender={"email": self.sender_email, "name": self.sender_name},
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

            api_response = self.api_instance.send_transac_email(send_smtp_email)
            logger.info(f"Email sent successfully. Message ID: {api_response.message_id}")
            return True

        except ApiException as e:
            logger.error(f"Error sending email via Brevo: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    def test_connection(self) -> bool:
        """Test email service connection.

        Returns:
            True if connection successful
        """
        try:
            # Try to get account info to test API key
            account_api = sib_api_v3_sdk.AccountApi(
                sib_api_v3_sdk.ApiClient(
                    sib_api_v3_sdk.Configuration()
                )
            )
            # This will raise an exception if the API key is invalid
            logger.info("Email service connection test successful")
            return True
        except Exception as e:
            logger.error(f"Email service connection test failed: {e}")
            return False


def main():
    """Test function for development."""
    import os
    import yaml

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Get API key from environment
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        print("Error: BREVO_API_KEY environment variable not set")
        return

    # Initialize emailer
    email_config = config['email']
    emailer = DigestEmailer(
        api_key=api_key,
        sender_email=email_config['sender_email'],
        sender_name=email_config['sender_name'],
        recipient_email=email_config['recipient_email']
    )

    # Create sample listings
    sample_listings = [
        {
            'isbn': '9780743273565',
            'title': 'The Great Gatsby',
            'author': 'F. Scott Fitzgerald',
            'publication_year': '2004',
            'seller': 'Better World Books',
            'price': 8.99,
            'currency': 'USD',
            'condition': 'Good',
            'url': 'https://www.bookfinder.com/example1',
            'first_seen': datetime.now()
        },
        {
            'isbn': '9780743273565',
            'title': 'The Great Gatsby',
            'author': 'F. Scott Fitzgerald',
            'publication_year': '2004',
            'seller': 'ThriftBooks',
            'price': 7.49,
            'currency': 'USD',
            'condition': 'Very Good',
            'url': 'https://www.bookfinder.com/example2',
            'first_seen': datetime.now()
        }
    ]

    # Send test digest
    print("Sending test digest email...")
    success = emailer.send_digest(sample_listings)

    if success:
        print("✓ Test email sent successfully!")
    else:
        print("✗ Failed to send test email")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
