#!/usr/bin/env python3
"""
Perplexity AI Research Phase

Performs deep research using Perplexity AI with strategic queries.

Usage:
    ./skills/research_perplexity.py SYMBOL [--work-dir DIR]

    If --work-dir is not specified, creates work/SYMBOL_YYYYMMDD automatically.

Examples:
    ./skills/research_perplexity.py TSLA
    ./skills/research_perplexity.py AAPL --work-dir custom/directory

Output:
    - Creates 03_research/ directory in work directory
    - news_stories.md - Major news since 2024
    - business_profile.md - 10-section business analysis
    - executive_profiles.md - C-suite executive profiles
"""

import sys
import argparse
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load environment for API keys
from dotenv import load_dotenv
load_dotenv()

# Perplexity API (OpenAI-compatible)
from openai import OpenAI

# Yahoo Finance for company name lookup
import yfinance as yf

# Import configuration
from config import (
    PERPLEXITY_MODEL,
    PERPLEXITY_TEMPERATURE,
    PERPLEXITY_MAX_TOKENS,
    NEWS_STORIES_COUNT,
    NEWS_STORIES_SINCE,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    RETRY_BACKOFF_MULTIPLIER,
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


def get_company_name(symbol: str, work_dir: Path) -> str:
    """
    Get company name for a symbol, trying multiple sources.

    Priority:
    1. Try loading from company_overview.json (if fundamental phase ran first)
    2. Fall back to fetching directly from yfinance

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        Company name or symbol if not found

    Example:
        >>> from pathlib import Path
        >>> name = get_company_name('AAPL', Path('work/AAPL_20260116'))
        >>> print(name)
        Apple Inc.
    """
    # Try loading from fundamentals first
    company_overview_path = work_dir / '02_fundamental' / 'company_overview.json'
    if company_overview_path.exists():
        try:
            with company_overview_path.open('r') as f:
                overview = json.load(f)
                company_name = overview.get('company_name', None)
                if company_name and company_name != 'N/A':
                    return company_name
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load company name from fundamentals: {e}")
            print(f"  ⚠ Could not load company name from fundamentals: {e}")

    # Fall back to yfinance lookup
    try:
        logger.info(f"Looking up company name for {symbol}...")
        print(f"  Looking up company name for {symbol}...")
        ticker = yf.Ticker(symbol)
        info = ticker.info
        company_name = info.get('longName', None)
        if company_name:
            logger.info(f"Found: {company_name}")
            print(f"  ✓ Found: {company_name}")
            return company_name
    except (KeyError, ValueError, AttributeError) as e:
        logger.warning(f"Could not fetch company name from yfinance: {e}")
        print(f"  ⚠ Could not fetch company name from yfinance: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching company name: {e}", exc_info=True)
        print(f"  ⚠ Could not fetch company name from yfinance: {e}")

    # If all else fails, return the symbol
    logger.info("Using symbol as fallback for company name")
    print(f"  ⚠ Using symbol as fallback")
    return symbol


def query_perplexity(
    prompt: str,
    model: str = PERPLEXITY_MODEL,
    temperature: float = PERPLEXITY_TEMPERATURE,
    max_tokens: int = 4000,
    max_retries: int = MAX_RETRIES
) -> Optional[str]:
    """
    Query Perplexity AI with retry logic.

    Implements exponential backoff retry strategy for API calls.

    Args:
        prompt: Query prompt
        model: Perplexity model to use
        temperature: Temperature for response (lower = more factual)
        max_tokens: Maximum tokens in response
        max_retries: Maximum retry attempts

    Returns:
        Response text if successful, None if all retries failed

    Example:
        >>> response = query_perplexity("Tell me about Apple Inc.")
        >>> if response:
        ...     print(f"Got {len(response)} characters")
    """
    import os

    # Get API key
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        logger.error("PERPLEXITY_API_KEY not found in environment")
        print("❌ ERROR: PERPLEXITY_API_KEY not found in environment")
        return None

    # Initialize Perplexity client
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai"
    )

    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            logger.info(f"Querying Perplexity (attempt {attempt + 1}/{max_retries})...")
            print(f"  Querying Perplexity (attempt {attempt + 1}/{max_retries})...")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial research analyst. Use only reputable, up-to-date sources. Provide detailed, well-sourced responses. Always include specific dates and source citations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content
            logger.info(f"Received response ({len(result)} characters)")
            print(f"  ✓ Received response ({len(result)} characters)")
            return result

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            print(f"  ⚠ Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = (RETRY_BACKOFF_MULTIPLIER ** attempt) * RETRY_DELAY_SECONDS
                logger.info(f"Waiting {wait_time}s before retry...")
                print(f"  Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error("All retry attempts failed")
                print(f"  ❌ All retry attempts failed")
                return None

    return None


def save_news_research(
    symbol: str,
    work_dir: Path,
    company_identifier: Optional[str] = None
) -> bool:
    """
    Research major news stories for the company.

    Uses Perplexity AI to gather and summarize significant recent news.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path
        company_identifier: Company name with symbol (e.g., "Tesla, Inc. (TSLA)")

    Returns:
        True if successful, False otherwise

    Example:
        >>> from pathlib import Path
        >>> success = save_news_research('TSLA', Path('work/TSLA_20260116'), 'Tesla, Inc. (TSLA)')
    """
    try:
        identifier = company_identifier or symbol
        logger.info(f"Researching news stories for {identifier}...")
        print(f"Researching news stories for {identifier}...")

        prompt = f"""

Research and summarize the most significant news stories about {identifier} from January 1, {NEWS_STORIES_SINCE} to today.

Requirements:
- Prioritize top-tier financial media (WSJ, Bloomberg, FT, Reuters, CNBC) and official company filings or press releases when available.
- Focus on:
  - Major corporate developments (earnings, guidance, product launches, partnerships, acquisitions, divestitures)
  - Regulatory issues, litigation, or investigations
  - Leadership changes and governance issues
  - Clearly notable market-moving developments for the stock

Output format:
- Chronological order (most recent first)
- For each story, include:
  - Exact calendar date
  - 3–5 sentences focusing on factual reporting, not speculation
  - At least one source citation with publication name
- Provide {NEWS_STORIES_COUNT} of the most significant stories.
"""
        result = query_perplexity(prompt, max_tokens=PERPLEXITY_MAX_TOKENS['news_stories'])

        if result:
            output_dir = work_dir / '03_research'
            ensure_directory(output_dir)

            news_path = output_dir / 'news_stories.md'
            with news_path.open('w') as f:
                f.write(f"# Major News Stories - {symbol}\n\n")
                f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
                f.write(result)

            logger.info(f"Saved news research to: {news_path}")
            print(f"✓ Saved news research to: {news_path}")
            return True
        else:
            logger.error("Failed to get news research")
            print(f"❌ Failed to get news research")
            return False

    except IOError as e:
        logger.error(f"File error in news research: {e}", exc_info=True)
        print(f"❌ Error in news research: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in news research: {e}", exc_info=True)
        print(f"❌ Error in news research: {e}")
        return False


def save_business_profile(
    symbol: str,
    work_dir: Path,
    company_identifier: Optional[str] = None
) -> bool:
    """
    Research comprehensive business profile.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path
        company_identifier: Company name with symbol (e.g., "Tesla, Inc. (TSLA)")

    Returns:
        True if successful, False otherwise
    """
    try:
        identifier = company_identifier or symbol
        print(f"Researching business profile for {identifier}...")

        prompt = f"""
Provide a comprehensive business profile for {identifier} with the following 10 sections:

1. **Company History & Evolution**: Founding, major milestones, transformations

2. **Business Model & Revenue Streams**: How the company makes money, product/service mix, geographic breakdown

3. **Competitive Advantages & Moats**: What sets them apart, barriers to entry, intellectual property

4. **Market Position & Share**: Industry ranking, market share percentages, competitive landscape

5. **Supply Chain Positioning**: Key suppliers, manufacturing approach, distribution channels

6. **Financial Health Overview**: Revenue trends, profitability, debt levels, cash position

7. **Growth Strategy**: Expansion plans, R&D focus, capital allocation priorities

8. **Risk Factors**: Key threats to business model, regulatory risks, competitive pressures

9. **Industry Trends**: Sector dynamics, tailwinds/headwinds, technological disruption

10. **Recent Developments**: Last 6-12 months of major announcements and changes

Each section should be 2-4 paragraphs with specific data points and citations.
"""

        result = query_perplexity(prompt, max_tokens=8000)

        if result:
            output_dir = work_dir / '03_research'
            ensure_directory(output_dir)

            profile_path = output_dir / 'business_profile.md'
            with profile_path.open('w') as f:
                f.write(f"# Business Profile - {symbol}\n\n")
                f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
                f.write(result)

            print(f"✓ Saved business profile to: {profile_path}")
            return True
        else:
            print(f"❌ Failed to get business profile")
            return False

    except Exception as e:
        print(f"❌ Error in business profile research: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_executive_profiles(
    symbol: str,
    work_dir: Path,
    company_identifier: Optional[str] = None
) -> bool:
    """
    Research executive leadership profiles.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path
        company_identifier: Company name with symbol (e.g., "Tesla, Inc. (TSLA)")

    Returns:
        True if successful, False otherwise
    """
    try:
        identifier = company_identifier or symbol
        print(f"Researching executive profiles for {identifier}...")

        prompt = f"""
Provide detailed profiles for the C-suite executives at {identifier}.

For each executive (CEO, CFO, COO, CTO, and other key C-suite):

1. **Name and Title**: Current role
2. **Background**: Education, previous roles, years with company
3. **Compensation**: Latest annual compensation if publicly available
4. **Tenure**: When they joined, length in current role
5. **Notable Achievements**: Key accomplishments at the company
6. **Recent Statements**: Recent public comments about strategy or outlook
7. **Controversies**: Any notable issues or criticisms

Focus on CEO and CFO with most detail, then other key executives.

Include specific citations and dates.
"""

        result = query_perplexity(prompt)

        if result:
            output_dir = work_dir / '03_research'
            ensure_directory(output_dir)

            exec_path = output_dir / 'executive_profiles.md'
            with exec_path.open('w') as f:
                f.write(f"# Executive Profiles - {symbol}\n\n")
                f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
                f.write(result)

            print(f"✓ Saved executive profiles to: {exec_path}")
            return True
        else:
            print(f"❌ Failed to get executive profiles")
            return False

    except Exception as e:
        print(f"❌ Error in executive profiles research: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Perplexity AI research phase'
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

    # Get company name for better queries
    company_name = get_company_name(symbol, work_dir)
    company_identifier = f"{company_name} ({symbol})" if company_name != symbol else symbol

    print("=" * 60)
    print("Perplexity AI Research Phase")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Company: {company_identifier}")
    print(f"Work Directory: {work_dir}")
    print("=" * 60)

    success_count = 0
    total_count = 3

    # Task 1: News stories
    if save_news_research(symbol, work_dir, company_identifier):
        success_count += 1

    # Task 2: Business profile
    if save_business_profile(symbol, work_dir, company_identifier):
        success_count += 1

    # Task 3: Executive profiles
    if save_executive_profiles(symbol, work_dir, company_identifier):
        success_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("Perplexity Research Phase Complete")
    print("=" * 60)
    print(f"Tasks completed: {success_count}/{total_count}")

    if success_count == total_count:
        print("✓ All tasks completed successfully")
        return 0
    elif success_count > 0:
        print(f"⚠ Partial success: {success_count}/{total_count} tasks completed")
        return 0  # Still return success for partial completion
    else:
        print("❌ All tasks failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
