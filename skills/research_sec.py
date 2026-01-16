#!/usr/bin/env python3
"""
SEC Filings Research Phase

Fetches and parses SEC 10-K filings, specifically Item 1 (Business Description).

Usage:
    ./skills/research_sec.py SYMBOL [--work-dir DIR]

    If --work-dir is not specified, creates work/SYMBOL_YYYYMMDD automatically.

Examples:
    ./skills/research_sec.py TSLA
    ./skills/research_sec.py AAPL --work-dir custom/directory

Output:
    - Creates 05_sec/ directory in work directory
    - 10k_item1.txt - Business description from latest 10-K
    - 10k_metadata.json - Filing metadata
"""

import sys
import argparse
import json
import re
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Load environment
from dotenv import load_dotenv
load_dotenv()

# SEC EDGAR downloader
from sec_edgar_downloader import Downloader

# For parsing HTML
from bs4 import BeautifulSoup

# Import configuration
from config import (
    SEC_FILING_TYPE,
    SEC_ITEM1_MAX_LENGTH,
    DATE_FORMAT_FILE,
)

# Import utilities
from utils import (
    setup_logging,
    validate_symbol,
    ensure_directory,
)

# Set up logging
logger = setup_logging(__name__)


def fetch_10k_item1(symbol: str, work_dir: Path) -> bool:
    """
    Fetch Item 1 (Business) from the latest 10-K filing.

    Downloads the latest 10-K filing from SEC EDGAR and extracts Item 1
    (Business Description section).

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        True if successful, False otherwise

    Example:
        >>> from pathlib import Path
        >>> success = fetch_10k_item1('AAPL', Path('work/AAPL_20260116'))
    """
    import os

    try:
        logger.info(f"Downloading 10-K filing for {symbol}...")
        print(f"Downloading 10-K filing for {symbol}...")

        # Get SEC credentials from environment
        sec_firm = os.getenv('SEC_FIRM')
        sec_user = os.getenv('SEC_USER')

        if not sec_firm or not sec_user:
            logger.error("SEC_FIRM and SEC_USER must be set in .env file")
            print(f"❌ ERROR: SEC_FIRM and SEC_USER must be set in .env file")
            print(f"   SEC requires User-Agent with company name and email")
            return False

        output_dir = work_dir / '05_sec'
        ensure_directory(output_dir)

        # Create temporary download directory
        temp_dir = output_dir / 'temp_download'
        ensure_directory(temp_dir)

        # Initialize downloader with company name and email from environment
        # SEC requires User-Agent with contact info
        dl = Downloader(sec_firm, sec_user, str(temp_dir))

        # Download the latest 10-K
        logger.info("Fetching latest 10-K from SEC EDGAR...")
        print(f"  Fetching latest 10-K from SEC EDGAR...")
        dl.get(SEC_FILING_TYPE, symbol, limit=1)

        # Find the downloaded file
        logger.info("Parsing 10-K filing...")
        print(f"  Parsing 10-K filing...")
        filing_path = None
        for path in temp_dir.rglob('*.txt'):
            filing_path = path
            break

        if not filing_path:
            logger.error("Could not find downloaded 10-K filing")
            print(f"❌ Could not find downloaded 10-K filing")
            return False

        # Read the filing
        with filing_path.open('r', encoding='utf-8', errors='ignore') as f:
            filing_text = f.read()

        # Extract Item 1
        item1_text = extract_item1(filing_text)

        if not item1_text:
            logger.warning("Could not automatically extract Item 1, saving truncated filing")
            print(f"⚠ Could not automatically extract Item 1, saving full filing")
            item1_text = filing_text[:SEC_ITEM1_MAX_LENGTH]

        # Save Item 1
        item1_path = output_dir / '10k_item1.txt'
        with item1_path.open('w', encoding='utf-8') as f:
            f.write(f"SEC 10-K Filing - Item 1 (Business)\n")
            f.write(f"Symbol: {symbol}\n")
            f.write(f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"=" * 60 + "\n\n")
            f.write(item1_text)

        logger.info(f"Saved Item 1 to: {item1_path} ({len(item1_text):,} characters)")
        print(f"✓ Saved Item 1 to: {item1_path}")
        print(f"  Length: {len(item1_text):,} characters")

        # Save metadata
        metadata = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'filing_type': SEC_FILING_TYPE,
            'filing_path': str(filing_path),
            'item1_length': len(item1_text),
        }

        metadata_path = output_dir / '10k_metadata.json'
        with metadata_path.open('w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved metadata to: {metadata_path}")
        print(f"✓ Saved metadata to: {metadata_path}")

        # Clean up temp directory
        shutil.rmtree(temp_dir)

        return True

    except (IOError, OSError) as e:
        logger.error(f"File error downloading 10-K: {e}", exc_info=True)
        print(f"❌ Error downloading 10-K: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error downloading 10-K: {e}", exc_info=True)
        print(f"❌ Error downloading 10-K: {e}")
        return False


def extract_item1(filing_text: str) -> Optional[str]:
    """
    Extract Item 1 (Business) section from 10-K filing text.

    Uses regex patterns to identify and extract the Business section from
    the HTML/text content of a 10-K filing.

    Args:
        filing_text: Full text of the 10-K filing

    Returns:
        Item 1 text if found, None otherwise

    Example:
        >>> text = extract_item1(filing_content)
        >>> if text:
        ...     print(f"Found {len(text)} characters")
    """
    try:
        # First, parse HTML and extract clean text
        soup = BeautifulSoup(filing_text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        # Get text
        clean_text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in clean_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)

        # Common patterns for Item 1 headers
        patterns = [
            r'(?i)ITEM\s+1[\.\:\s]+BUSINESS',
            r'(?i)ITEM\s+1[\.\:\-\—]+BUSINESS',
            r'(?i)Item 1\.\s+Business',
            r'(?i)Item 1\s+Business',
            r'(?i)ITEM\s+1\.',
            r'(?i)Item 1\s*\n',
        ]

        # Try to find Item 1 start
        start_pos = None
        for pattern in patterns:
            match = re.search(pattern, clean_text)
            if match:
                start_pos = match.start()
                logger.info(f"Found Item 1 at position {start_pos}")
                print(f"  Found Item 1 at position {start_pos}")
                break

        if not start_pos:
            logger.warning("Could not find Item 1 header")
            print(f"  Warning: Could not find Item 1 header")
            return None

        # Find Item 1A or Item 2 to determine end
        item2_patterns = [
            r'(?i)ITEM\s+1A[\.\:\s]+RISK\s+FACTORS',
            r'(?i)ITEM\s+1A[\.\:\-\—]+RISK',
            r'(?i)Item 1A\.\s+Risk',
            r'(?i)Item 1A\s+Risk',
            r'(?i)ITEM\s+1A\.',
            r'(?i)ITEM\s+2[\.\:\s]',
            r'(?i)Item 2\.',
        ]

        end_pos = None
        for pattern in item2_patterns:
            match = re.search(pattern, clean_text[start_pos+100:])  # Skip first 100 chars to avoid false matches
            if match:
                end_pos = start_pos + 100 + match.start()
                print(f"  Found end marker at position {end_pos}")
                break

        # If we can't find the end, take a reasonable chunk
        if not end_pos:
            end_pos = min(start_pos + 100000, len(clean_text))  # ~100K characters or end of text
            print(f"  No end marker found, using {end_pos - start_pos:,} characters")

        item1_text = clean_text[start_pos:end_pos]

        # Additional cleanup
        # Remove excessive whitespace
        item1_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', item1_text)

        # Remove page numbers and other artifacts
        item1_text = re.sub(r'^\d+\s*$', '', item1_text, flags=re.MULTILINE)

        # Remove table of contents entries (lines with dots and page numbers)
        item1_text = re.sub(r'^.*\.{3,}\s*\d+\s*$', '', item1_text, flags=re.MULTILINE)

        # Final whitespace cleanup
        item1_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', item1_text)

        logger.info(f"Extracted {len(item1_text):,} characters")
        print(f"  Extracted {len(item1_text):,} characters")
        return item1_text.strip()

    except (AttributeError, ValueError) as e:
        logger.warning(f"Error extracting Item 1: {e}")
        print(f"  Warning: Error extracting Item 1: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error extracting Item 1: {e}", exc_info=True)
        print(f"  Warning: Error extracting Item 1: {e}")
        return None


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='SEC filings research phase'
    )
    parser.add_argument(
        'symbol',
        help='Stock ticker symbol (e.g., TSLA, AAPL, MSFT)'
    )
    parser.add_argument(
        '--work-dir',
        default=None,
        help='Work directory path (default: work/SYMBOL_YYYYMMDD)'
    )

    args = parser.parse_args()

    # Normalize symbol
    symbol = validate_symbol(args.symbol)

    # Generate work directory if not specified
    if not args.work_dir:
        date_str = datetime.now().strftime(DATE_FORMAT_FILE)
        work_dir = Path('work') / f'{symbol}_{date_str}'
    else:
        work_dir = Path(args.work_dir)

    # Create work directory if it doesn't exist
    ensure_directory(work_dir)

    print("=" * 60)
    print("SEC Filings Research Phase")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Work Directory: {work_dir}")
    print("=" * 60)

    success_count = 0
    total_count = 1

    # Task 1: Fetch 10-K Item 1
    if fetch_10k_item1(symbol, work_dir):
        success_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("SEC Research Phase Complete")
    print("=" * 60)
    print(f"Tasks completed: {success_count}/{total_count}")

    if success_count == total_count:
        print("✓ All tasks completed successfully")
        return 0
    elif success_count > 0:
        print(f"⚠ Partial success: {success_count}/{total_count} tasks completed")
        return 0
    else:
        print("❌ All tasks failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
