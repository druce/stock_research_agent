#!/usr/bin/env python3
"""
Fundamental Analysis Research Phase

Performs fundamental analysis using financial data from yfinance.

Usage:
    ./skills/research_fundamental.py SYMBOL [--work-dir DIR]

    If --work-dir is not specified, creates work/SYMBOL_YYYYMMDD automatically.

Examples:
    ./skills/research_fundamental.py TSLA
    ./skills/research_fundamental.py AAPL --work-dir custom/directory

Output:
    - Creates 02_fundamental/ directory in work directory
    - company_overview.json - Company information and metrics
    - income_statement.csv - Income statement data
    - income_statement_sankey.html - Sankey flow of income statement
    - income_statement_sankey.png - Sankey flow image
    - balance_sheet.csv - Balance sheet data
    - cash_flow.csv - Cash flow statement
    - key_ratios.json - Financial ratios
    - analyst_recommendations.json - Analyst ratings
    - news.json - Recent news articles
"""

import sys
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from dotenv import load_dotenv

# Import configuration
from config import (
    WORK_DIR,
    DATE_FORMAT_FILE,
    MAX_ANALYST_RECOMMENDATIONS,
    MAX_NEWS_ARTICLES,
    CHART_SCALE,
)

# Import utilities
from utils import (
    setup_logging,
    create_work_directory,
    validate_symbol,
    ensure_directory,
    get_phase_directory,
)

# Set up logging
logger = setup_logging(__name__)

# Load environment variables
load_dotenv()


def save_company_overview(symbol: str, work_dir: Union[str, Path]) -> bool:
    """
    Get and save company overview information.

    Fetches comprehensive company information from yfinance including
    valuation metrics, financial highlights, and corporate details.

    Args:
        symbol: Stock ticker symbol (e.g., 'TSLA', 'AAPL')
        work_dir: Work directory path for output

    Returns:
        True if successful, False otherwise

    Example:
        >>> if save_company_overview('TSLA', Path('work/TSLA_20260116')):
        ...     print("Overview saved")
    """
    try:
        output_dir = get_phase_directory(work_dir, 'fundamental')
        ensure_directory(output_dir)
        overview_path = output_dir / 'company_overview.json'

        if overview_path.exists():
            print(f"⊘ Company overview already exists, skipping: {overview_path}")
            return True

        logger.info(f"Getting company overview for {symbol}...")

        ticker = yf.Ticker(symbol)
        info = ticker.info

        overview = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'company_name': info.get('longName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'country': info.get('country', 'N/A'),
            'website': info.get('website', 'N/A'),
            'business_summary': info.get('longBusinessSummary', 'N/A'),
            'employees': info.get('fullTimeEmployees', 'N/A'),
            'market_cap': info.get('marketCap', 'N/A'),
            'enterprise_value': info.get('enterpriseValue', 'N/A'),
            'trailing_pe': info.get('trailingPE', 'N/A'),
            'forward_pe': info.get('forwardPE', 'N/A'),
            'peg_ratio': info.get('pegRatio', 'N/A'),
            'price_to_book': info.get('priceToBook', 'N/A'),
            'price_to_sales': info.get('priceToSalesTrailing12Months', 'N/A'),
            'profit_margin': info.get('profitMargins', 'N/A'),
            'operating_margin': info.get('operatingMargins', 'N/A'),
            'roe': info.get('returnOnEquity', 'N/A'),
            'roa': info.get('returnOnAssets', 'N/A'),
            'revenue': info.get('totalRevenue', 'N/A'),
            'revenue_per_share': info.get('revenuePerShare', 'N/A'),
            'quarterly_revenue_growth': info.get('revenueGrowth', 'N/A'),
            'gross_profit': info.get('grossProfits', 'N/A'),
            'ebitda': info.get('ebitda', 'N/A'),
            'net_income': info.get('netIncomeToCommon', 'N/A'),
            'eps': info.get('trailingEps', 'N/A'),
            'forward_eps': info.get('forwardEps', 'N/A'),
            'dividend_rate': info.get('dividendRate', 'N/A'),
            'dividend_yield': info.get('dividendYield', 'N/A'),
            'payout_ratio': info.get('payoutRatio', 'N/A'),
            'beta': info.get('beta', 'N/A'),
            '52_week_high': info.get('fiftyTwoWeekHigh', 'N/A'),
            '52_week_low': info.get('fiftyTwoWeekLow', 'N/A'),
            'shares_outstanding': info.get('sharesOutstanding', 'N/A'),
            'float_shares': info.get('floatShares', 'N/A'),
            'shares_short': info.get('sharesShort', 'N/A'),
            'short_ratio': info.get('shortRatio', 'N/A'),
            'short_percent_of_float': info.get('shortPercentOfFloat', 'N/A'),
            'held_percent_insiders': info.get('heldPercentInsiders', 'N/A'),
            'held_percent_institutions': info.get('heldPercentInstitutions', 'N/A'),
        }

        with overview_path.open('w') as f:
            json.dump(overview, f, indent=2)

        print(f"✓ Saved company overview to: {overview_path}")
        print(f"  Company: {overview['company_name']}")
        print(f"  Sector: {overview['sector']}")
        print(f"  Industry: {overview['industry']}")

        return True

    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing company overview data: {e}")
        return False
    except IOError as e:
        logger.error(f"Error writing company overview file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error getting company overview: {e}", exc_info=True)
        return False


def save_financial_statements(symbol: str, work_dir: Union[str, Path]) -> bool:
    """
    Get and save financial statements.

    Fetches income statement, balance sheet, and cash flow statement
    from yfinance and saves them as CSV files.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        True if successful, False otherwise

    Example:
        >>> save_financial_statements('TSLA', Path('work/TSLA_20260116'))
    """
    try:
        logger.info(f"Getting financial statements for {symbol}...")

        output_dir = get_phase_directory(work_dir, 'fundamental')
        ensure_directory(output_dir)

        income_stmt = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        cash_flow = pd.DataFrame()

        try:
            ticker = yf.Ticker(symbol)
            income_stmt = ticker.income_stmt
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow
        except Exception as e:
            logger.warning(f"Failed to fetch statements from yfinance: {e}")

        # Income statement
        income_path = output_dir / 'income_statement.csv'
        if not income_stmt.empty:
            income_stmt.to_csv(income_path)
            print(f"✓ Saved income statement to: {income_path}")
        elif income_path.exists():
            logger.info(f"Using existing income statement: {income_path}")
            try:
                income_stmt = pd.read_csv(income_path, index_col=0)
            except Exception as e:
                logger.warning(f"Could not read existing income statement: {e}")

        if not income_stmt.empty:
            save_income_statement_sankey(income_stmt, output_dir, symbol)
        else:
            logger.info("No income statement available; skipping Sankey chart")

        # Balance sheet
        if not balance_sheet.empty:
            balance_path = output_dir / 'balance_sheet.csv'
            balance_sheet.to_csv(balance_path)
            print(f"✓ Saved balance sheet to: {balance_path}")

        # Cash flow
        if not cash_flow.empty:
            cashflow_path = output_dir / 'cash_flow.csv'
            cash_flow.to_csv(cashflow_path)
            print(f"✓ Saved cash flow to: {cashflow_path}")

        return True

    except IOError as e:
        logger.error(f"Error writing financial statements: {e}")
        return False
    except Exception as e:
        logger.error(f"Error getting financial statements: {e}", exc_info=True)
        return False


def save_income_statement_sankey(
    income_stmt: pd.DataFrame,
    output_dir: Path,
    symbol: str
) -> bool:
    """
    Create a Sankey chart showing revenue flowing to net income.

    Visualizes how revenue flows through various expense categories
    to arrive at net income.

    Args:
        income_stmt: DataFrame containing income statement data
        output_dir: Directory to save Sankey chart
        symbol: Stock ticker symbol for chart title

    Returns:
        True if successful, False otherwise

    Example:
        >>> income_df = pd.read_csv('income_statement.csv')
        >>> save_income_statement_sankey(income_df, Path('output'), 'TSLA')
    """
    def get_value(series: pd.Series, keys: List[str]) -> Optional[float]:
        """Extract value from series trying multiple key names."""
        for key in keys:
            if key in series.index:
                value = series.loc[key]
                if pd.notna(value):
                    return float(value)
        return None

    try:
        if income_stmt.empty:
            return False

        logger.info("Creating income statement Sankey chart...")

        latest_period = income_stmt.columns[0]
        period_label = (
            latest_period.date().isoformat()
            if hasattr(latest_period, "date")
            else str(latest_period)
        )
        series = income_stmt[latest_period]

        revenue = get_value(series, ["Total Revenue", "TotalRevenue"])
        if revenue is None:
            logger.warning("Income statement missing total revenue; skipping Sankey chart")
            return False

        cost_of_revenue = get_value(series, ["Cost Of Revenue", "CostOfRevenue", "Cost Of Goods Sold"])
        gross_profit = get_value(series, ["Gross Profit", "GrossProfit"])
        if gross_profit is None:
            gross_profit = revenue - (cost_of_revenue or 0.0)
        if cost_of_revenue is None:
            cost_of_revenue = max(revenue - gross_profit, 0.0)

        operating_income = get_value(series, ["Operating Income", "OperatingIncome"])
        operating_expenses = get_value(series, ["Total Operating Expenses", "TotalOperatingExpenses"])
        if operating_expenses is None:
            expense_keys = [
                "Research Development",
                "Selling General Administrative",
                "SellingGeneralAdministrative",
                "Selling And Marketing Expense",
                "General and Administrative Expense",
                "Other Operating Expenses",
            ]
            expenses = [get_value(series, [key]) for key in expense_keys]
            expenses = [val for val in expenses if val is not None]
            if expenses:
                operating_expenses = float(sum(expenses))

        if operating_income is None and operating_expenses is not None:
            operating_income = gross_profit - operating_expenses
        elif operating_expenses is None and operating_income is not None:
            operating_expenses = max(gross_profit - operating_income, 0.0)
        elif operating_expenses is None and operating_income is None:
            operating_expenses = 0.0
            operating_income = gross_profit

        pre_tax_income = get_value(series, ["Pretax Income", "Income Before Tax", "IncomeBeforeTax"])
        if pre_tax_income is None:
            pre_tax_income = operating_income

        other_income_expense = operating_income - pre_tax_income
        tax_expense = get_value(series, ["Tax Provision", "Income Tax Expense", "IncomeTaxExpense"])
        if tax_expense is None:
            net_income_candidate = get_value(series, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
            if net_income_candidate is not None:
                tax_expense = max(pre_tax_income - net_income_candidate, 0.0)

        net_income = get_value(series, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
        if net_income is None:
            net_income = max(pre_tax_income - (tax_expense or 0.0), 0.0)

        nodes = [
            "Total Revenue",
            "Cost of Revenue",
            "Gross Profit",
            "Operating Expenses",
            "Operating Income",
            "Other Income/(Expense)",
            "Pre-Tax Income",
            "Taxes",
            "Net Income",
        ]
        node_index = {name: idx for idx, name in enumerate(nodes)}

        sources: List[int] = []
        targets: List[int] = []
        values: List[float] = []

        def add_link(source: str, target: str, value: Optional[float]) -> None:
            if value is None or value <= 0:
                return
            sources.append(node_index[source])
            targets.append(node_index[target])
            values.append(float(value))

        add_link("Total Revenue", "Cost of Revenue", cost_of_revenue)
        add_link("Total Revenue", "Gross Profit", gross_profit)

        add_link("Gross Profit", "Operating Expenses", operating_expenses)
        add_link("Gross Profit", "Operating Income", operating_income)

        if other_income_expense >= 0:
            add_link("Operating Income", "Other Income/(Expense)", other_income_expense)
            add_link("Operating Income", "Pre-Tax Income", pre_tax_income)
        else:
            add_link("Other Income/(Expense)", "Pre-Tax Income", abs(other_income_expense))
            add_link("Operating Income", "Pre-Tax Income", operating_income)

        if tax_expense is not None and tax_expense < 0:
            add_link("Taxes", "Net Income", abs(tax_expense))
            add_link("Pre-Tax Income", "Net Income", pre_tax_income)
        else:
            add_link("Pre-Tax Income", "Taxes", tax_expense)
            add_link("Pre-Tax Income", "Net Income", net_income)

        fig = go.Figure(
            data=[
                go.Sankey(
                    node=dict(label=nodes, pad=18, thickness=16),
                    link=dict(source=sources, target=targets, value=values),
                )
            ]
        )
        fig.update_layout(
            title=f"{symbol} Income Statement Flow ({period_label})",
            font=dict(size=12),
        )

        sankey_path = output_dir / 'income_statement_sankey.html'
        pio.write_html(fig, str(sankey_path), include_plotlyjs='cdn')
        print(f"✓ Saved income statement Sankey to: {sankey_path}")

        image_path = output_dir / 'income_statement_sankey.png'
        try:
            logger.debug("Saving income statement Sankey image...")
            fig.write_image(str(image_path), scale=CHART_SCALE)
            print(f"✓ Saved income statement Sankey image to: {image_path}")
        except Exception as e:
            logger.warning(f"Could not save Sankey image: {e}")
            try:
                import kaleido
                logger.info("Attempting to install a compatible Chrome for Kaleido...")
                kaleido.get_chrome_sync()
                fig.write_image(str(image_path), scale=CHART_SCALE)
                print(f"✓ Saved income statement Sankey image to: {image_path}")
            except ImportError:
                logger.warning("Kaleido not available, skipping image export")
            except Exception as retry_error:
                logger.warning(f"Sankey image retry failed: {retry_error}")

        return True

    except Exception as e:
        logger.warning(f"Failed to create income statement Sankey: {e}")
        return False


def get_financial_ratios(symbol: str) -> pd.DataFrame:
    """
    Retrieve comprehensive financial ratios for a given symbol using yfinance.

    Args:
        symbol: Stock ticker symbol

    Returns:
        DataFrame with columns: Category, Metric, {symbol}

    Raises:
        ValueError: If no data available for symbol

    Example:
        >>> df = get_financial_ratios('TSLA')
        >>> print(df[['Category', 'Metric', 'TSLA']].head())
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info:
        raise ValueError(f"No data available for symbol: {symbol}")

    valuation_ratios = {
        'Trailing P/E': info.get('trailingPE'),
        'Forward P/E': info.get('forwardPE'),
        'PEG Ratio': info.get('pegRatio'),
        'Price/Sales (ttm)': info.get('priceToSalesTrailing12Months'),
        'Price/Book': info.get('priceToBook'),
        'Enterprise Value/Revenue': info.get('enterpriseToRevenue'),
        'Enterprise Value/EBITDA': info.get('enterpriseToEbitda'),
    }

    financial_highlights = {
        'Market Cap': info.get('marketCap'),
        'Enterprise Value': info.get('enterpriseValue'),
        'Revenue (ttm)': info.get('totalRevenue'),
        'Gross Profit (ttm)': info.get('grossProfits'),
        'EBITDA': info.get('ebitda'),
        'Net Income (ttm)': info.get('netIncomeToCommon'),
    }

    profitability_ratios = {
        'Profit Margin': info.get('profitMargins'),
        'Operating Margin': info.get('operatingMargins'),
        'Gross Margin': info.get('grossMargins'),
        'EBITDA Margin': info.get('ebitdaMargins'),
        'Return on Assets': info.get('returnOnAssets'),
        'Return on Equity': info.get('returnOnEquity'),
    }

    liquidity_ratios = {
        'Current Ratio': info.get('currentRatio'),
        'Quick Ratio': info.get('quickRatio'),
        'Total Cash': info.get('totalCash'),
        'Total Debt': info.get('totalDebt'),
        'Debt/Equity': info.get('debtToEquity'),
    }

    per_share_data = {
        'Earnings Per Share (ttm)': info.get('trailingEps'),
        'Book Value Per Share': info.get('bookValue'),
        'Revenue Per Share': info.get('revenuePerShare'),
        'Operating Cash Flow Per Share': (
            info.get('operatingCashflow', 0) / info['sharesOutstanding']
            if info.get('sharesOutstanding') and info['sharesOutstanding'] > 0
            else None
        ),
    }

    all_ratios = {
        **valuation_ratios,
        **financial_highlights,
        **profitability_ratios,
        **liquidity_ratios,
        **per_share_data
    }

    df = pd.DataFrame(list(all_ratios.items()), columns=['Metric', symbol])
    df['Category'] = (
        ['Valuation'] * len(valuation_ratios) +
        ['Financial Highlights'] * len(financial_highlights) +
        ['Profitability'] * len(profitability_ratios) +
        ['Liquidity'] * len(liquidity_ratios) +
        ['Per Share'] * len(per_share_data)
    )
    return df[["Category", "Metric", symbol]]


def save_key_ratios(symbol: str, work_dir: Union[str, Path]) -> bool:
    """
    Calculate and save key financial ratios.

    Fetches financial ratios for the primary symbol and all peer companies
    (if available) and saves to CSV.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        True if successful, False otherwise

    Example:
        >>> save_key_ratios('TSLA', Path('work/TSLA_20260116'))
    """
    try:
        logger.info(f"Calculating key ratios for {symbol}...")

        symbol_df = get_financial_ratios(symbol)

        # Try to load peers list from technical phase
        peers_list: List[str] = []
        technical_dir = Path(work_dir) / '01_technical'
        peers_path = technical_dir / 'peers_list.json'

        logger.debug(f"Looking for peers at: {peers_path}")

        if peers_path.exists():
            try:
                with peers_path.open('r') as f:
                    peers_data = json.load(f)

                logger.debug(f"Loaded peers JSON with keys: {list(peers_data.keys())}")

                # Extract peer symbols from different JSON structures
                if 'symbol' in peers_data and isinstance(peers_data['symbol'], list):
                    peers_list = [s for s in peers_data['symbol'] if s]
                    logger.debug(f"Extracted {len(peers_list)} peers from 'symbol' field")
                elif 'results' in peers_data and isinstance(peers_data['results'], list):
                    peers_list = [p.get('symbol') for p in peers_data['results'] if p.get('symbol')]
                    logger.debug(f"Extracted {len(peers_list)} peers from 'results' field")
                elif 'peers_list' in peers_data and isinstance(peers_data['peers_list'], list):
                    peers_list = peers_data['peers_list']
                    logger.debug(f"Extracted {len(peers_list)} peers from 'peers_list' field")

                if peers_list:
                    print(f"✓ Found {len(peers_list)} peers: {', '.join(peers_list[:5])}{'...' if len(peers_list) > 5 else ''}")
                else:
                    logger.warning("No peers extracted from JSON")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load peers list: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading peers: {e}", exc_info=True)
        else:
            logger.warning("No peers list found - technical phase must run first")
            print(f"\n⚠️  WARNING: No peers list found")
            print(f"  The technical phase must run BEFORE fundamental to generate the peer list.")
            print(f"  Expected file: {peers_path}")
            print(f"")
            print(f"  To fix this:")
            print(f"  1. Run technical phase first: ./skills/research_technical.py {symbol} --work-dir {work_dir}")
            print(f"  2. Then run fundamental phase: ./skills/research_fundamental.py {symbol} --work-dir {work_dir}")
            print(f"  OR use the orchestrator: ./skills/research_stock.py {symbol}")
            print(f"")
            print(f"  Continuing with just {symbol} (no peer comparison available)...")
            print()

        # Get ratios for each peer
        peers_dflist: List[pd.Series] = []
        for peer in peers_list:
            try:
                peer_df = get_financial_ratios(peer)
                peers_dflist.append(peer_df.iloc[:, 2])
                logger.debug(f"Got ratios for {peer}")
            except ValueError as e:
                logger.warning(f"Could not get ratios for {peer}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error getting ratios for {peer}: {e}")

        # Concatenate original table with peer data
        if peers_dflist:
            df = pd.concat([symbol_df] + peers_dflist, axis=1)
        else:
            df = symbol_df

        output_dir = get_phase_directory(work_dir, 'fundamental')
        ensure_directory(output_dir)

        ratios_path = output_dir / 'key_ratios.csv'
        df.to_csv(ratios_path, index=False)

        print(f"✓ Saved key ratios to: {ratios_path}")
        print(f"  Columns: {', '.join(df.columns.tolist())}")
        print(f"  Rows: {len(df)} ratios")

        return True

    except ValueError as e:
        logger.error(f"Invalid data for key ratios: {e}")
        return False
    except IOError as e:
        logger.error(f"Error writing key ratios file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error calculating key ratios: {e}", exc_info=True)
        return False


def save_analyst_recommendations(symbol: str, work_dir: Union[str, Path]) -> bool:
    """
    Get and save analyst recommendations.

    Fetches recent analyst recommendations from yfinance and saves to JSON.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        True if successful, False otherwise

    Example:
        >>> save_analyst_recommendations('TSLA', Path('work/TSLA_20260116'))
    """
    try:
        logger.info(f"Getting analyst recommendations for {symbol}...")

        ticker = yf.Ticker(symbol)
        recommendations = ticker.recommendations

        if recommendations is not None and not recommendations.empty:
            output_dir = get_phase_directory(work_dir, 'fundamental')
            ensure_directory(output_dir)

            recs_dict = recommendations.tail(MAX_ANALYST_RECOMMENDATIONS).to_dict(orient='records')

            # Convert timestamps to strings
            for rec in recs_dict:
                for key, value in rec.items():
                    if pd.isna(value):
                        rec[key] = None
                    elif hasattr(value, 'isoformat'):
                        rec[key] = value.isoformat()

            recs_path = output_dir / 'analyst_recommendations.json'
            with recs_path.open('w') as f:
                json.dump(recs_dict, f, indent=2)

            print(f"✓ Saved analyst recommendations to: {recs_path}")
            print(f"  Total recommendations: {len(recs_dict)}")
        else:
            logger.info("No analyst recommendations available")

        return True

    except IOError as e:
        logger.error(f"Error writing analyst recommendations: {e}")
        return False
    except Exception as e:
        logger.error(f"Error getting analyst recommendations: {e}", exc_info=True)
        return False


def save_news(symbol: str, work_dir: Union[str, Path]) -> bool:
    """
    Get and save recent news articles.

    Fetches recent news articles from yfinance and saves to JSON.

    Args:
        symbol: Stock ticker symbol
        work_dir: Work directory path

    Returns:
        True if successful, False otherwise

    Example:
        >>> save_news('TSLA', Path('work/TSLA_20260116'))
    """
    try:
        logger.info(f"Getting recent news for {symbol}...")

        ticker = yf.Ticker(symbol)
        news = ticker.news

        if news:
            output_dir = get_phase_directory(work_dir, 'fundamental')
            ensure_directory(output_dir)

            # Limit to MAX_NEWS_ARTICLES
            news_limited = news[:MAX_NEWS_ARTICLES]

            news_path = output_dir / 'news.json'
            with news_path.open('w') as f:
                json.dump(news_limited, f, indent=2)

            print(f"✓ Saved news to: {news_path}")
            print(f"  Total articles: {len(news_limited)}")
        else:
            logger.info("No news available")

        return True

    except IOError as e:
        logger.error(f"Error writing news file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error getting news: {e}", exc_info=True)
        return False


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Fundamental analysis research phase'
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
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    symbol = validate_symbol(args.symbol)

    if args.work_dir:
        work_dir = Path(args.work_dir)
    else:
        work_dir = create_work_directory(symbol)

    ensure_directory(work_dir)

    print("=" * 60)
    print("Fundamental Analysis Phase")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Work Directory: {work_dir}")
    print("=" * 60)

    success_count = 0
    total_count = 5

    # Task 1: Company overview
    if save_company_overview(symbol, work_dir):
        success_count += 1

    # Task 2: Financial statements
    if save_financial_statements(symbol, work_dir):
        success_count += 1

    # Task 3: Key ratios
    if save_key_ratios(symbol, work_dir):
        success_count += 1

    # Task 4: Analyst recommendations
    if save_analyst_recommendations(symbol, work_dir):
        success_count += 1

    # Task 5: News
    if save_news(symbol, work_dir):
        success_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("Fundamental Analysis Phase Complete")
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
