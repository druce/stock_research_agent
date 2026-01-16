#!/usr/bin/env python3
"""
Report Generation Phase

Generates comprehensive analyst-style report from all research phases.

Usage:
    ./skills/research_report.py SYMBOL [--work-dir DIR]

    If --work-dir is not specified, creates work/SYMBOL_YYYYMMDD automatically.

Examples:
    ./skills/research_report.py TSLA
    ./skills/research_report.py AAPL --work-dir custom/directory

Output:
    - research_report.md - Markdown report
    - research_report.html - HTML report (optional)
"""

import sys
import os
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

# Template engine
from jinja2 import Environment, FileSystemLoader

# Import configuration
from config import (
    TEMPLATES_DIR,
    DEFAULT_REPORT_TEMPLATE,
    DATE_FORMAT_FILE,
)

# Import utilities
from utils import (
    setup_logging,
    validate_symbol,
    ensure_directory,
    format_currency,
    format_number,
    format_percentage,
)

# Set up logging
logger = setup_logging(__name__)


def load_data(work_dir: Path, symbol: str) -> Dict[str, Any]:
    """
    Load all research data from phase outputs.

    Aggregates data from technical analysis, fundamental analysis, research,
    SEC filings, and other phases into a single dictionary for template rendering.

    Args:
        work_dir: Work directory path
        symbol: Stock ticker symbol

    Returns:
        Dictionary containing all research data with standardized keys

    Example:
        >>> from pathlib import Path
        >>> data = load_data(Path('work/TSLA_20260116'), 'TSLA')
        >>> print(data['company_name'])
    """
    data: Dict[str, Any] = {
        'symbol': symbol,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'company_name': 'N/A',
        'sector': 'N/A',
        'industry': 'N/A',
        'latest_price': 'N/A',
        'market_cap': 'N/A',
    }

    # Load metadata (optional - symbol already set from parameter)
    metadata_path = work_dir / '00_metadata.json'
    if metadata_path.exists():
        try:
            with metadata_path.open('r') as f:
                metadata = json.load(f)
                # Metadata can override if present, but not required
                if metadata.get('symbol'):
                    data['symbol'] = metadata.get('symbol')
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load metadata: {e}")

    # Load technical analysis
    tech_path = work_dir / '01_technical' / 'technical_analysis.json'
    if tech_path.exists():
        try:
            with tech_path.open('r') as f:
                data['technical_analysis'] = json.load(f)
                if 'latest_price' in data['technical_analysis']:
                    data['latest_price'] = f"{data['technical_analysis']['latest_price']:.2f}"
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load technical analysis: {e}")

    # Load peers list with enhanced metrics
    peers_path = work_dir / '01_technical' / 'peers_list.json'
    ratios_path = work_dir / '02_fundamental' / 'key_ratios.csv'

    if peers_path.exists():
        try:
            with peers_path.open('r') as f:
                peers_data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load peers data: {e}")
            peers_data = None

        # Load key ratios for peer metrics
        ratios_df = None
        if ratios_path.exists():
            try:
                ratios_df = pd.read_csv(ratios_path)
            except (IOError, pd.errors.ParserError) as e:
                logger.warning(f"Could not load ratios data: {e}")

        # Convert to list of dicts with enhanced metrics
        if peers_data and 'symbol' in peers_data and isinstance(peers_data['symbol'], list):
            peers: List[Dict[str, Any]] = []
            for i, peer_symbol in enumerate(peers_data['symbol']):
                peer_info: Dict[str, Any] = {
                    'symbol': peer_symbol,
                    'name': peers_data.get('name', [])[i] if i < len(peers_data.get('name', [])) else 'N/A',
                    'price': f"{peers_data.get('price', [])[i]:.2f}" if i < len(peers_data.get('price', [])) and peers_data.get('price', [])[i] else 'N/A',
                    'market_cap': f"{peers_data.get('market_cap', [])[i]:,.0f}" if i < len(peers_data.get('market_cap', [])) and peers_data.get('market_cap', [])[i] else 'N/A',
                }

                # Add financial metrics from ratios_df if available
                if ratios_df is not None and peer_symbol in ratios_df.columns:
                    # P/E Ratio
                    pe_row = ratios_df[ratios_df['Metric'] == 'Trailing P/E']
                    if not pe_row.empty and peer_symbol in pe_row.columns:
                        pe_val = pe_row[peer_symbol].values[0]
                        peer_info['pe_ratio'] = f"{pe_val:.2f}" if pd.notna(pe_val) and pe_val != 'N/A' else 'N/A'
                    else:
                        peer_info['pe_ratio'] = 'N/A'

                    # Revenue (TTM)
                    rev_row = ratios_df[ratios_df['Metric'] == 'Revenue (ttm)']
                    if not rev_row.empty and peer_symbol in rev_row.columns:
                        rev_val = rev_row[peer_symbol].values[0]
                        if pd.notna(rev_val) and rev_val != 'N/A':
                            try:
                                peer_info['revenue'] = f"${float(rev_val)/1e9:.1f}B"
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not format revenue for {peer_symbol}: {e}")
                                peer_info['revenue'] = 'N/A'
                        else:
                            peer_info['revenue'] = 'N/A'
                    else:
                        peer_info['revenue'] = 'N/A'

                    # Profit Margin
                    margin_row = ratios_df[ratios_df['Metric'] == 'Profit Margin']
                    if not margin_row.empty and peer_symbol in margin_row.columns:
                        margin_val = margin_row[peer_symbol].values[0]
                        if pd.notna(margin_val) and margin_val != 'N/A':
                            try:
                                peer_info['profit_margin'] = f"{float(margin_val)*100:.1f}%"
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not format profit margin for {peer_symbol}: {e}")
                                peer_info['profit_margin'] = 'N/A'
                        else:
                            peer_info['profit_margin'] = 'N/A'
                    else:
                        peer_info['profit_margin'] = 'N/A'

                    # ROE
                    roe_row = ratios_df[ratios_df['Metric'] == 'Return on Equity']
                    if not roe_row.empty and peer_symbol in roe_row.columns:
                        roe_val = roe_row[peer_symbol].values[0]
                        if pd.notna(roe_val) and roe_val != 'N/A':
                            try:
                                peer_info['roe'] = f"{float(roe_val)*100:.1f}%"
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not format ROE for {peer_symbol}: {e}")
                                peer_info['roe'] = 'N/A'
                        else:
                            peer_info['roe'] = 'N/A'
                    else:
                        peer_info['roe'] = 'N/A'
                else:
                    # No ratios data available
                    peer_info['pe_ratio'] = 'N/A'
                    peer_info['revenue'] = 'N/A'
                    peer_info['profit_margin'] = 'N/A'
                    peer_info['roe'] = 'N/A'

                peers.append(peer_info)

            data['peers'] = peers[:10]  # Limit to top 10

    # Check for chart
    chart_path = work_dir / '01_technical' / 'chart.png'
    if chart_path.exists():
        data['chart_path'] = '01_technical/chart.png'

    # Check for income statement Sankey chart
    sankey_path = work_dir / '02_fundamental' / 'income_statement_sankey.png'
    if sankey_path.exists():
        data['income_statement_sankey_path'] = '02_fundamental/income_statement_sankey.png'

    # Load fundamental data
    overview_path = work_dir / '02_fundamental' / 'company_overview.json'
    if overview_path.exists():
        try:
            with overview_path.open('r') as f:
                overview = json.load(f)
                data['company_name'] = overview.get('company_name', 'N/A')
                data['sector'] = overview.get('sector', 'N/A')
                data['industry'] = overview.get('industry', 'N/A')
                data['business_summary'] = overview.get('business_summary', '')
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load company overview: {e}")

            if overview.get('market_cap') != 'N/A':
                data['market_cap'] = f"{overview['market_cap']:,.0f}"

            # Financial metrics
            data['revenue'] = f"{overview.get('revenue', 0):,.0f}" if overview.get('revenue') != 'N/A' else 'N/A'
            data['revenue_per_share'] = f"{overview.get('revenue_per_share', 0):.2f}" if overview.get('revenue_per_share') != 'N/A' else 'N/A'

            if overview.get('quarterly_revenue_growth') != 'N/A' and overview.get('quarterly_revenue_growth') is not None:
                data['quarterly_revenue_growth'] = f"{overview['quarterly_revenue_growth']*100:.2f}"

            data['gross_profit'] = f"{overview.get('gross_profit', 0):,.0f}" if overview.get('gross_profit') != 'N/A' else 'N/A'
            data['ebitda'] = f"{overview.get('ebitda', 0):,.0f}" if overview.get('ebitda') != 'N/A' else 'N/A'

            # Margins
            if overview.get('profit_margin') != 'N/A' and overview.get('profit_margin') is not None:
                data['profit_margin'] = f"{overview['profit_margin']*100:.2f}"
            if overview.get('operating_margin') != 'N/A' and overview.get('operating_margin') is not None:
                data['operating_margin'] = f"{overview['operating_margin']*100:.2f}"

            # Returns
            if overview.get('roe') != 'N/A' and overview.get('roe') is not None:
                data['roe'] = f"{overview['roe']*100:.2f}"
            if overview.get('roa') != 'N/A' and overview.get('roa') is not None:
                data['roa'] = f"{overview['roa']*100:.2f}"

            # Valuation
            data['trailing_pe'] = f"{overview.get('trailing_pe', 0):.2f}" if overview.get('trailing_pe') != 'N/A' else 'N/A'
            data['forward_pe'] = f"{overview.get('forward_pe', 0):.2f}" if overview.get('forward_pe') != 'N/A' else 'N/A'
            data['peg_ratio'] = f"{overview.get('peg_ratio', 0):.2f}" if overview.get('peg_ratio') != 'N/A' else 'N/A'
            data['price_to_book'] = f"{overview.get('price_to_book', 0):.2f}" if overview.get('price_to_book') != 'N/A' else 'N/A'
            data['price_to_sales'] = f"{overview.get('price_to_sales', 0):.2f}" if overview.get('price_to_sales') != 'N/A' else 'N/A'

    # Load analyst recommendations
    recs_path = work_dir / '02_fundamental' / 'analyst_recommendations.json'
    if recs_path.exists():
        try:
            with recs_path.open('r') as f:
                recs = json.load(f)
                # Convert to DataFrame-like format for template
                data['analyst_recommendations'] = recs
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load analyst recommendations: {e}")

    # Load Perplexity research
    news_path = work_dir / '03_research' / 'news_stories.md'
    if news_path.exists():
        try:
            with news_path.open('r') as f:
                data['news_stories'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load news stories: {e}")

    business_profile_path = work_dir / '03_research' / 'business_profile.md'
    if business_profile_path.exists():
        try:
            with business_profile_path.open('r') as f:
                data['business_profile'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load business profile: {e}")

    exec_profiles_path = work_dir / '03_research' / 'executive_profiles.md'
    if exec_profiles_path.exists():
        try:
            with exec_profiles_path.open('r') as f:
                data['executive_profiles'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load executive profiles: {e}")

    # Load SEC data
    sec_metadata_path = work_dir / '04_sec' / '10k_metadata.json'
    if sec_metadata_path.exists():
        try:
            with sec_metadata_path.open('r') as f:
                sec_data = json.load(f)
                data['sec_filing_url'] = sec_data.get('filing_url', '')
                data['sec_filing_date'] = sec_data.get('filing_date', '')
                data['sec_report_date'] = sec_data.get('report_date', '')
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load SEC metadata: {e}")

    # Load Wikipedia data
    wiki_summary_path = work_dir / '05_wikipedia' / 'wikipedia_summary.txt'
    if wiki_summary_path.exists():
        try:
            with wiki_summary_path.open('r') as f:
                wiki_text = f.read()
                # Extract just the summary part (after the header)
                lines = wiki_text.split('\n')
                summary_start = False
                summary_lines = []
                for line in lines:
                    if '=' * 60 in line:
                        if summary_start:
                            break
                        summary_start = True
                        continue
                    if summary_start and line.strip():
                        summary_lines.append(line)
                data['wikipedia_summary'] = '\n'.join(summary_lines)
        except IOError as e:
            logger.warning(f"Could not load Wikipedia summary: {e}")

    # Load deep analysis data
    analysis_dir = work_dir / '06_analysis'

    # Business model analysis
    business_model_path = analysis_dir / 'business_model_analysis.md'
    if business_model_path.exists():
        try:
            with business_model_path.open('r') as f:
                data['business_model_analysis'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load business model analysis: {e}")

    # Competitive analysis
    competitive_path = analysis_dir / 'competitive_analysis.md'
    if competitive_path.exists():
        try:
            with competitive_path.open('r') as f:
                data['competitive_analysis'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load competitive analysis: {e}")

    # Supply chain analysis
    supply_chain_path = analysis_dir / 'supply_chain_analysis.md'
    if supply_chain_path.exists():
        try:
            with supply_chain_path.open('r') as f:
                data['supply_chain_analysis'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load supply chain analysis: {e}")

    # Risk analysis
    risk_analysis_path = analysis_dir / 'risk_analysis.md'
    if risk_analysis_path.exists():
        try:
            with risk_analysis_path.open('r') as f:
                data['recent_news_analysis'] = f.read()
        except IOError as e:
            logger.warning(f"Could not load risk analysis: {e}")

    # Investment thesis
    thesis_path = analysis_dir / 'investment_thesis.md'
    if thesis_path.exists():
        try:
            with thesis_path.open('r') as f:
                thesis_content = f.read()
                data['investment_thesis'] = thesis_content
        except IOError as e:
            logger.warning(f"Could not load investment thesis: {e}")
            thesis_content = None

            # Try to extract specific sections from investment thesis
            # This is a simple approach - could be enhanced with better parsing
            if thesis_content:
                import re
                if 'Bull Case' in thesis_content or 'bull case' in thesis_content.lower():
                    # Extract bull case section
                    bull_match = re.search(r'(?:Bull Case|BULL CASE)[\s\S]*?(?=(?:Bear Case|BEAR CASE|Base Case|##|$))', thesis_content, re.IGNORECASE)
                    if bull_match:
                        data['bull_case'] = bull_match.group(0).strip()

                if 'Bear Case' in thesis_content or 'bear case' in thesis_content.lower():
                    # Extract bear case section
                    bear_match = re.search(r'(?:Bear Case|BEAR CASE)[\s\S]*?(?=(?:Base Case|BASE CASE|Critical Watch|##|$))', thesis_content, re.IGNORECASE)
                    if bear_match:
                        data['bear_case'] = bear_match.group(0).strip()

                if 'SWOT' in thesis_content:
                    # Extract SWOT sections
                    strengths_match = re.search(r'(?:Strengths|STRENGTHS)[\s\S]*?(?=(?:Weaknesses|WEAKNESSES|##))', thesis_content, re.IGNORECASE)
                    if strengths_match:
                        data['strengths'] = strengths_match.group(0).strip()

                    weaknesses_match = re.search(r'(?:Weaknesses|WEAKNESSES)[\s\S]*?(?=(?:Opportunities|OPPORTUNITIES|##))', thesis_content, re.IGNORECASE)
                    if weaknesses_match:
                        data['weaknesses'] = weaknesses_match.group(0).strip()

                    opportunities_match = re.search(r'(?:Opportunities|OPPORTUNITIES)[\s\S]*?(?=(?:Threats|THREATS|##))', thesis_content, re.IGNORECASE)
                    if opportunities_match:
                        data['opportunities'] = opportunities_match.group(0).strip()

                    threats_match = re.search(r'(?:Threats|THREATS)[\s\S]*?(?=(?:Bull Case|BULL CASE|##|$))', thesis_content, re.IGNORECASE)
                    if threats_match:
                        data['threats'] = threats_match.group(0).strip()

    # Load SEC 10-K Item 1 excerpt
    item1_path = work_dir / '04_sec' / '10k_item1.txt'
    if item1_path.exists():
        try:
            with item1_path.open('r', encoding='utf-8', errors='ignore') as f:
                item1_text = f.read()
                # Extract a reasonable excerpt for business description
                if len(item1_text) > 5000:
                    data['sec_item1_business'] = item1_text[:5000] + "\n\n[...continued in full 10-K filing]"
                else:
                    data['sec_item1_business'] = item1_text
        except IOError as e:
            logger.warning(f"Could not load SEC Item 1: {e}")

    # Reference file paths for detailed analysis
    balance_sheet_path = work_dir / '02_fundamental' / 'balance_sheet.csv'
    if balance_sheet_path.exists():
        data['balance_sheet_file'] = str(balance_sheet_path)

    cash_flow_path = work_dir / '02_fundamental' / 'cash_flow.csv'
    if cash_flow_path.exists():
        data['cash_flow_file'] = str(cash_flow_path)

    return data


def generate_report(
    work_dir: Path,
    symbol: str,
    output_format: str = 'markdown',
    template_name: str = DEFAULT_REPORT_TEMPLATE
) -> bool:
    """
    Generate the research report.

    Loads all research data and renders it using a Jinja2 template to create
    markdown and optionally HTML reports.

    Args:
        work_dir: Work directory path
        symbol: Stock ticker symbol
        output_format: 'markdown' or 'html'
        template_name: Template file to use

    Returns:
        True if report was successfully generated, False otherwise

    Example:
        >>> from pathlib import Path
        >>> success = generate_report(Path('work/TSLA_20260116'), 'TSLA')
    """
    try:
        logger.info(f"Generating {output_format} report...")
        print(f"Generating {output_format} report...")
        print(f"  Using template: {template_name}")

        # Load all data
        data = load_data(work_dir, symbol)

        if not data['symbol']:
            logger.error("Could not determine symbol")
            print("❌ Could not determine symbol")
            return False

        print(f"  Symbol: {data['symbol']}")
        print(f"  Company: {data['company_name']}")

        # Set up Jinja2 environment
        template_dir = Path(__file__).parent.parent / TEMPLATES_DIR
        env = Environment(loader=FileSystemLoader(str(template_dir)))

        # Add custom filters for formatting
        env.filters['format_number'] = lambda value: format_number(value, precision=0)
        env.filters['format_currency'] = format_currency
        env.filters['format_percentage'] = format_percentage

        # Load template
        template = env.get_template(template_name)

        # Render template
        report_content = template.render(**data)

        # Save markdown report
        report_path = work_dir / 'research_report.md'
        with report_path.open('w') as f:
            f.write(report_content)

        logger.info(f"Saved report to: {report_path}")
        print(f"✓ Saved report to: {report_path}")

        # Optionally convert to HTML
        if output_format == 'html':
            try:
                import markdown
                html_content = markdown.markdown(report_content)

                html_path = work_dir / 'research_report.html'
                with html_path.open('w') as f:
                    f.write(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Stock Research Report: {data['symbol']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        img {{ max-width: 100%; height: auto; }}
        hr {{ margin: 30px 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
""")

                logger.info(f"Saved HTML report to: {html_path}")
                print(f"✓ Saved HTML report to: {html_path}")
            except ImportError:
                logger.info("markdown library not installed, skipping HTML generation")
                print("⊘ markdown library not installed, skipping HTML generation")
            except IOError as e:
                logger.error(f"Could not write HTML file: {e}")
                print(f"⚠ Could not save HTML file: {e}")

        return True

    except (IOError, KeyError) as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        print(f"❌ Error generating report: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error generating report: {e}", exc_info=True)
        print(f"❌ Error generating report: {e}")
        return False


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Report generation phase'
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
        '--format',
        default='markdown',
        choices=['markdown', 'html'],
        help='Output format (default: markdown)'
    )
    parser.add_argument(
        '--template',
        default=DEFAULT_REPORT_TEMPLATE,
        help=f'Template file to use (default: {DEFAULT_REPORT_TEMPLATE})'
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
    print("Report Generation Phase")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Work Directory: {work_dir}")
    print(f"Format: {args.format}")
    print(f"Template: {args.template}")
    print("=" * 60)

    success = generate_report(work_dir, symbol, args.format, args.template)

    # Summary
    print("\n" + "=" * 60)
    print("Report Generation Phase Complete")
    print("=" * 60)

    if success:
        print("✓ Report generated successfully")
        return 0
    else:
        print("❌ Report generation failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
