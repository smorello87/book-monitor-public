"""Author list loader for Book Monitor."""

import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)


class AuthorLoader:
    """Loads and manages author lists from text files."""

    def __init__(self, file_path: str = "authors.txt"):
        """Initialize author loader.

        Args:
            file_path: Path to authors text file
        """
        self.file_path = Path(file_path)
        logger.info(f"Initialized author loader: {self.file_path}")

    def load_authors(self) -> List[str]:
        """Load authors from text file.

        Returns:
            List of author names (full names)

        Raises:
            FileNotFoundError: If authors file doesn't exist
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Authors file not found: {self.file_path}")

        authors = []

        with open(self.file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Strip whitespace
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Skip comments
                if line.startswith('#'):
                    continue

                # Validate author name
                if not self._is_valid_author_name(line):
                    logger.warning(
                        f"Line {line_num}: Invalid author name skipped: {line}"
                    )
                    continue

                authors.append(line)

        logger.info(f"Loaded {len(authors)} authors from {self.file_path}")
        return authors

    def _is_valid_author_name(self, name: str) -> bool:
        """Validate author name format.

        Args:
            name: Author name to validate

        Returns:
            True if valid, False otherwise
        """
        # Check minimum length
        if len(name) < 2:
            return False

        # Check maximum length (reasonable limit)
        if len(name) > 100:
            return False

        # Check for at least one letter
        if not any(c.isalpha() for c in name):
            return False

        return True


def main():
    """Test function for development."""
    import sys

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Load authors
    try:
        loader = AuthorLoader('authors.txt')
        authors = loader.load_authors()

        print(f"\n{'=' * 80}")
        print(f"LOADED {len(authors)} AUTHORS")
        print('=' * 80)
        print()

        for i, author in enumerate(authors, 1):
            print(f"{i}. {author}")

        print()
        print('=' * 80)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
