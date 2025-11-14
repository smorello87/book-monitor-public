#!/usr/bin/env python3
"""Google Sheets loader for search specifications."""

import logging
import pandas as pd
from typing import List, Dict, Optional


logger = logging.getLogger(__name__)


class SheetsLoader:
    """Load search specifications from Google Sheets via CSV export."""

    def __init__(self, sheet_id: str):
        """Initialize sheets loader.

        Args:
            sheet_id: Google Sheets document ID (from URL)
        """
        self.sheet_id = sheet_id
        self.csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        logger.info(f"Initialized sheets loader for sheet: {sheet_id}")

    def load_search_specs(self) -> List[Dict[str, Optional[str]]]:
        """Load search specifications from Google Sheet.

        Returns:
            List of search spec dictionaries with keys:
            - author (str): Full author name (required)
            - title (str|None): Book title (optional)
            - year (int|None): Publication year (optional)
            - keywords (str|None): Search keywords (optional)
            - accept_new (bool): Accept NEW condition books (default: False)

        Raises:
            Exception: If sheet cannot be read or has invalid format
        """
        try:
            logger.info(f"Loading search specs from: {self.csv_url}")

            # Read CSV from Google Sheets
            df = pd.read_csv(self.csv_url)

            # Expected columns: Author, Title, Year, Keyword, Accept New
            expected_cols = ['Author', 'Title', 'Year', 'Keyword', 'Accept New']

            # Check if required column exists
            if 'Author' not in df.columns:
                raise ValueError(f"Sheet must have 'Author' column. Found: {df.columns.tolist()}")

            # Log available columns
            logger.debug(f"Sheet columns: {df.columns.tolist()}")

            # Process each row
            search_specs = []
            for idx, row in df.iterrows():
                # Skip rows without author (empty rows)
                author = str(row.get('Author', '')).strip()
                if not author or author.lower() == 'nan':
                    logger.debug(f"Skipping row {idx+2}: No author specified")
                    continue

                # Get optional fields (handle NaN values from pandas)
                title = str(row.get('Title', '')).strip() if pd.notna(row.get('Title')) else None
                if title and title.lower() == 'nan':
                    title = None

                year_raw = row.get('Year')
                year = None
                if pd.notna(year_raw):
                    try:
                        year = int(float(year_raw))  # Handle "1905.0" format
                    except (ValueError, TypeError):
                        logger.warning(f"Row {idx+2}: Invalid year value '{year_raw}', ignoring")

                keywords = str(row.get('Keyword', '')).strip() if pd.notna(row.get('Keyword')) else None
                if keywords and keywords.lower() == 'nan':
                    keywords = None

                # Parse Accept New column (Y/Yes = True, anything else = False)
                accept_new_raw = str(row.get('Accept New', '')).strip().upper() if pd.notna(row.get('Accept New')) else ''
                accept_new = accept_new_raw in ['Y', 'YES', 'TRUE', '1']

                # Create search spec
                spec = {
                    'author': author,
                    'title': title,
                    'year': year,
                    'keywords': keywords,
                    'accept_new': accept_new
                }

                search_specs.append(spec)
                logger.debug(f"Loaded spec: {author}" +
                           (f" - {title}" if title else "") +
                           (f" ({year})" if year else "") +
                           (f" [{keywords}]" if keywords else ""))

            logger.info(f"Loaded {len(search_specs)} search specifications from Google Sheet")
            return search_specs

        except pd.errors.EmptyDataError:
            logger.error("Sheet is empty or has no data")
            return []

        except Exception as e:
            logger.error(f"Error loading search specs from Google Sheet: {e}")
            raise


if __name__ == '__main__':
    # Test with the actual sheet
    import sys
    logging.basicConfig(level=logging.DEBUG)

    sheet_id = "1wnGY6o-uRGw1vsxPb6MzN44KxvnK5MeRTA5Mn6DmTXo"
    loader = SheetsLoader(sheet_id)

    try:
        specs = loader.load_search_specs()
        print(f"\nLoaded {len(specs)} search specifications:")
        for i, spec in enumerate(specs, 1):
            print(f"\n{i}. {spec['author']}")
            if spec['title']:
                print(f"   Title: {spec['title']}")
            if spec['year']:
                print(f"   Year: {spec['year']}")
            if spec['keywords']:
                print(f"   Keywords: {spec['keywords']}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
