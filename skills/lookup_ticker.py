#!/usr/bin/env python3
"""
Ticker Lookup Skill with Multi-Provider Fallback

Searches for stock ticker symbols by company name using:
1. yfinance (primary - free, no API key required)
2. Finnhub (secondary - free tier with API key)
3. OpenBB+FMP (fallback - requires PAT, FMP may need paid subscription)

Usage:
    ./skills/lookup_ticker.py "company name"
    ./skills/lookup_ticker.py "Broadcom"
    ./skills/lookup_ticker.py --query "Apple Inc" --limit 5

Output:
    - Prints matching ticker symbols with company names
    - Optionally saves results to CSV file
    - Shows which provider was used
"""

import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dotenv import load_dotenv

# Import configuration
from config import (
    DEFAULT_TICKER_LIMIT,
    MAX_TICKER_LENGTH,
    DATA_DIR,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)


def search_ticker_yfinance(
    query: str,
    limit: int = DEFAULT_TICKER_LIMIT
) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    """
    Search for ticker symbols using yfinance.

    Note: yfinance doesn't have a native search API, but we can validate
    if a symbol exists by trying to fetch its info.

    Args:
        query: Ticker symbol or company name
        limit: Maximum number of results to return

    Returns:
        A tuple containing:
            - success (bool): True if search succeeded
            - results (list): List of ticker dictionaries
            - error (str or None): Error message if failed

    Example:
        >>> success, results, error = search_ticker_yfinance("AAPL")
        >>> if success:
        ...     print(results[0]['symbol'])
        AAPL
    """
    try:
        import yfinance as yf

        # yfinance doesn't have search, but we can try to validate a symbol
        # If query looks like a symbol (short, uppercase), validate it
        if len(query) <= MAX_TICKER_LENGTH and query.replace('.', '').isalpha():
            ticker = yf.Ticker(query.upper())
            try:
                info = ticker.info

                # Check if we got valid data
                if info and 'symbol' in info:
                    results = [{
                        'symbol': info.get('symbol', query.upper()),
                        'name': info.get('longName', info.get('shortName', 'N/A')),
                        'exchange': info.get('exchange', 'N/A'),
                        'type': info.get('quoteType', 'N/A'),
                        'currency': info.get('currency', 'N/A'),
                        'country': info.get('country', 'N/A')
                    }]
                    return True, results, None
            except (KeyError, AttributeError, ValueError) as e:
                logger.debug(f"Could not validate symbol {query}: {e}")

        # yfinance doesn't support company name search
        return False, [], "yfinance doesn't support company name search, only symbol validation"

    except ImportError:
        return False, [], "yfinance not installed"
    except Exception as e:
        logger.error(f"Unexpected error in yfinance search: {e}", exc_info=True)
        return False, [], f"yfinance error: {str(e)}"


def search_ticker_finnhub(
    query: str,
    limit: int = DEFAULT_TICKER_LIMIT
) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    """
    Search for ticker symbols using Finnhub API.

    Args:
        query: Company name or ticker symbol
        limit: Maximum number of results to return

    Returns:
        A tuple containing:
            - success (bool): True if search succeeded
            - results (list): List of ticker dictionaries
            - error (str or None): Error message if failed

    Raises:
        None - all exceptions are caught and returned as error strings
    """
    import os

    try:
        import finnhub

        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            return False, [], "FINNHUB_API_KEY not set in environment"

        client = finnhub.Client(api_key=api_key)

        # Use symbol lookup endpoint
        search_results = client.symbol_lookup(query)

        if not search_results or 'result' not in search_results:
            return False, [], "No results from Finnhub"

        raw_results = search_results['result']

        if not raw_results:
            return False, [], "Finnhub returned empty results"

        # Format results
        results = []
        for item in raw_results[:limit]:
            results.append({
                'symbol': item.get('symbol', 'N/A'),
                'name': item.get('description', 'N/A'),
                'type': item.get('type', 'N/A'),
                'exchange': item.get('displaySymbol', 'N/A'),
                'mic': item.get('mic', 'N/A')
            })

        return True, results, None

    except ImportError:
        return False, [], "finnhub-python not installed (pip install finnhub-python)"
    except Exception as e:
        error_msg = str(e)
        # Check for rate limit
        if '429' in error_msg or 'rate limit' in error_msg.lower():
            return False, [], f"Finnhub rate limit exceeded: {error_msg}"
        logger.error(f"Finnhub API error: {e}", exc_info=True)
        return False, [], f"Finnhub error: {error_msg}"


def search_ticker_openbb(
    query: str,
    provider: str = 'cboe',
    limit: int = DEFAULT_TICKER_LIMIT
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Search for ticker symbols using OpenBB Platform.

    Args:
        query: Company name or search string
        provider: Data provider (default: 'cboe')
        limit: Maximum number of results to return

    Returns:
        A tuple containing:
            - success (bool): True if search succeeded
            - results (list): List of ticker dictionaries
            - error (str or None): Error message if failed
    """
    import os

    try:
        from openbb import obb

        pat = os.getenv('OPENBB_PAT')
        if not pat:
            return False, [], "OPENBB_PAT not set in environment"

        # Login with PAT
        try:
            obb.user.credentials.openbb_pat = pat
        except Exception as e:
            return False, [], f"Could not login with PAT: {e}"

        # Use OpenBB equity search
        result = obb.equity.search(query=query, provider=provider)

        # Convert result to list of dictionaries
        if hasattr(result, 'to_dataframe'):
            df = result.to_dataframe()
            results = df.to_dict('records')
        elif hasattr(result, 'results'):
            results = result.results
            if not isinstance(results, list):
                try:
                    df = pd.DataFrame([results])
                    results = df.to_dict('records')
                except Exception as e:
                    logger.warning(f"Could not convert results to DataFrame: {e}")
                    results = [results]
        elif isinstance(result, list):
            results = result
        else:
            return False, [], f"Unexpected result format: {type(result)}"

        # Limit results
        if limit and len(results) > limit:
            results = results[:limit]

        if not results:
            return False, [], "OpenBB returned empty results"

        return True, results, None

    except ImportError:
        return False, [], "OpenBB not installed (pip install openbb)"
    except Exception as e:
        logger.error(f"OpenBB API error: {e}", exc_info=True)
        return False, [], f"OpenBB error: {str(e)}"


def search_ticker_with_fallback(
    query: str,
    limit: int = DEFAULT_TICKER_LIMIT,
    provider: str = 'cboe'
) -> Tuple[List[Dict], str, Dict[str, Optional[str]]]:
    """
    Search for ticker symbols with automatic fallback chain:
    yfinance -> Finnhub -> OpenBB+FMP

    Args:
        query: Company name or ticker symbol
        limit: Maximum number of results
        provider: OpenBB provider (only used if we fall back to OpenBB)

    Returns:
        A tuple containing:
            - results (list): List of ticker dictionaries (empty if all failed)
            - provider_used (str): Name of provider that succeeded ('none' if all failed)
            - all_errors (dict): Dictionary mapping provider names to error messages
    """
    all_errors: Dict[str, Optional[str]] = {}

    # Try yfinance first
    logger.info("[1/3] Trying yfinance...")
    success, results, error = search_ticker_yfinance(query, limit)
    all_errors['yfinance'] = error

    if success and results:
        logger.info(f"✓ yfinance succeeded ({len(results)} results)")
        return results, 'yfinance', all_errors
    else:
        logger.info(f"✗ yfinance failed: {error}")

    # Try Finnhub second
    logger.info("[2/3] Trying Finnhub...")
    success, results, error = search_ticker_finnhub(query, limit)
    all_errors['finnhub'] = error

    if success and results:
        logger.info(f"✓ Finnhub succeeded ({len(results)} results)")
        return results, 'Finnhub', all_errors
    else:
        logger.info(f"✗ Finnhub failed: {error}")

    # Try OpenBB+FMP last
    logger.info("[3/3] Trying OpenBB+FMP...")
    success, results, error = search_ticker_openbb(query, provider, limit)
    all_errors['openbb'] = error

    if success and results:
        logger.info(f"✓ OpenBB+FMP succeeded ({len(results)} results)")
        return results, f'OpenBB+FMP (provider={provider})', all_errors
    else:
        logger.info(f"✗ OpenBB+FMP failed: {error}")

    # All providers failed
    return [], 'none', all_errors


def format_results(results: List[Dict]) -> Optional[pd.DataFrame]:
    """
    Format search results for display.

    Args:
        results: List of ticker information dictionaries

    Returns:
        Formatted DataFrame, or None if results are empty
    """
    if not results:
        return None

    # Convert to DataFrame for nice formatting
    df = pd.DataFrame(results)

    # Common fields to display (adjust based on actual API response)
    # Priority order for columns
    priority_cols = ['symbol', 'name', 'exchange', 'type', 'mic',
                     'market_cap', 'country', 'currency', 'dpm_name',
                     'post_station', 'cik']
    display_cols = []

    for col in priority_cols:
        if col in df.columns:
            display_cols.append(col)

    # Add any remaining columns not in priority list
    for col in df.columns:
        if col not in display_cols:
            display_cols.append(col)

    if display_cols:
        df = df[display_cols]

    return df


def save_results(df: pd.DataFrame, output_dir: str = DATA_DIR) -> Optional[Path]:
    """
    Save search results to CSV file.

    Args:
        df: Search results DataFrame
        output_dir: Directory to save file

    Returns:
        Path to saved file, or None if save failed
    """
    if df is None or len(df) == 0:
        return None

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_path / f'ticker_search_{timestamp}.csv'

    df.to_csv(output_file, index=False)
    return output_file


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description='Search for stock ticker symbols with multi-provider fallback'
    )
    parser.add_argument(
        'query',
        nargs='?',
        help='Company name or ticker symbol (e.g., "Broadcom" or "AVGO")'
    )
    parser.add_argument(
        '--query', '-q',
        dest='query_flag',
        help='Company name or ticker symbol (alternative format)'
    )
    parser.add_argument(
        '--provider', '-p',
        default='cboe',
        help='OpenBB data provider (only used as fallback, default: cboe)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=DEFAULT_TICKER_LIMIT,
        help=f'Maximum number of results (default: {DEFAULT_TICKER_LIMIT})'
    )
    parser.add_argument(
        '--save', '-s',
        action='store_true',
        help=f'Save results to CSV file in {DATA_DIR}/ directory'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=DATA_DIR,
        help=f'Directory to save results (default: {DATA_DIR})'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get query from either positional or flag argument
    query = args.query or args.query_flag

    if not query:
        parser.print_help()
        logger.error("Please provide a company name or ticker symbol to search for")
        print("\nExample: ./skills/lookup_ticker.py \"Broadcom\"")
        print("Example: ./skills/lookup_ticker.py \"AVGO\"")
        return 1

    logger.info("=" * 60)
    logger.info("Multi-Provider Ticker Lookup")
    logger.info("=" * 60)
    logger.info(f"Searching for: '{query}'")
    logger.info("Fallback chain: yfinance → Finnhub → OpenBB+FMP")
    logger.info("")

    # Search with fallback
    results, provider_used, all_errors = search_ticker_with_fallback(
        query,
        args.limit,
        args.provider
    )

    if not results:
        logger.error("=" * 60)
        logger.error("No results found from any provider")
        logger.error("=" * 60)
        logger.error("\nProvider errors:")
        for provider, error in all_errors.items():
            if error:
                logger.error(f"  • {provider}: {error}")
        logger.info("\nTroubleshooting:")
        logger.info("  1. Check if ticker symbol is correct")
        logger.info("  2. Set FINNHUB_API_KEY in .env (get free key at https://finnhub.io/register)")
        logger.info("  3. Set OPENBB_PAT in .env")
        logger.info("=" * 60)
        return 1

    # Format and display results
    df = format_results(results)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"SUCCESS: Found {len(results)} result(s) using {provider_used}")
    logger.info("=" * 60)

    if df is not None:
        print("\n" + df.to_string(index=False))
    else:
        # Fallback: print raw results
        for i, result in enumerate(results, 1):
            print(f"{i}. {result}")

    # Save if requested
    if args.save and df is not None:
        saved_file = save_results(df, args.output_dir)
        if saved_file:
            logger.info(f"\n✓ Results saved to: {saved_file}")

    logger.info("\n" + "=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
