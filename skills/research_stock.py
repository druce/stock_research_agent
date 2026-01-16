#!/usr/bin/env python3
"""
Stock Research Orchestrator

Coordinates comprehensive stock research workflow across multiple phases.

Usage:
    ./skills/research_stock.py INTC
    ./skills/research_stock.py INTC --phases technical
    ./skills/research_stock.py INTC --phases technical,fundamental
    ./skills/research_stock.py INTC --skip-cleanup

Output:
    - Creates work/{SYMBOL}_{YYYYMMDD}/ directory with research outputs
    - Deletes older directories for same symbol by default
    - Tracks completed phases in metadata file
"""

import sys
import argparse
import json
import subprocess
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager
from dotenv import load_dotenv

# Import configuration
from config import (
    WORK_DIR,
    PHASE_API_KEYS,
    PHASE_TIMEOUTS,
    MAX_PARALLEL_WORKERS,
    DATE_FORMAT_FILE,
    DATE_FORMAT_DISPLAY,
)

# Import utilities
from utils import (
    setup_logging,
    validate_symbol,
    ensure_directory,
    format_date,
)

# Set up logging
logger = setup_logging(__name__)

# Load environment variables
load_dotenv()

# Import company overview function for early execution
sys.path.insert(0, str(Path(__file__).parent))
from research_fundamental import save_company_overview


def validate_api_keys(phases_to_run: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that required API keys are present for the phases to run.

    Args:
        phases_to_run: List of phase names to execute

    Returns:
        Tuple containing:
            - success: True if all required keys present
            - missing_keys: Sorted list of missing API key names

    Example:
        >>> valid, missing = validate_api_keys(['technical', 'research'])
        >>> if not valid:
        ...     print(f"Missing: {missing}")
    """
    import os

    missing_keys: Set[str] = set()

    for phase in phases_to_run:
        required_keys = PHASE_API_KEYS.get(phase, [])
        for key in required_keys:
            if not os.getenv(key):
                missing_keys.add(key)

    return len(missing_keys) == 0, sorted(missing_keys)


def validate_ticker(symbol: str) -> bool:
    """
    Validate ticker symbol using lookup_ticker skill.

    Uses the lookup_ticker.py skill to verify that the symbol exists
    and is valid. If validation fails due to network issues, continues
    with a warning.

    Args:
        symbol: Stock ticker symbol to validate (e.g., 'TSLA', 'AAPL')

    Returns:
        True if valid ticker, False otherwise

    Example:
        >>> if validate_ticker('AAPL'):
        ...     print("Valid ticker")
    """
    try:
        lookup_script = Path(__file__).parent / 'lookup_ticker.py'
        result = subprocess.run(
            [str(lookup_script), symbol, '--limit', '1'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return True

        logger.warning(
            "Ticker validation failed (exit %s). stdout: %s stderr: %s",
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip()
        )
        return False

    except subprocess.TimeoutExpired:
        logger.warning("Ticker validation timed out after 30 seconds")
        return True
    except FileNotFoundError as e:
        logger.warning(f"Could not find lookup_ticker.py: {e}")
        return True
    except Exception as e:
        logger.warning(f"Could not validate ticker: {e}")
        return True


def cleanup_old_directories(
    symbol: str,
    current_dir: Path,
    skip_cleanup: bool = False
) -> None:
    """
    Delete older work directories for the same symbol.

    Args:
        symbol: Stock ticker symbol
        current_dir: Current work directory to preserve
        skip_cleanup: If True, skip cleanup

    Example:
        >>> cleanup_old_directories('TSLA', Path('work/TSLA_20260116'))
    """
    if skip_cleanup:
        print(f"⊘ Skipping cleanup (--skip-cleanup flag set)")
        return

    work_dir_path = Path(WORK_DIR)
    if not work_dir_path.exists():
        return

    pattern = f"{symbol}_*"
    matching_dirs = list(work_dir_path.glob(pattern))

    deleted_count = 0
    for dir_path in matching_dirs:
        if dir_path != current_dir and dir_path.is_dir():
            try:
                shutil.rmtree(dir_path)
                deleted_count += 1
                print(f"✓ Deleted old directory: {dir_path}")
            except OSError as e:
                logger.warning(f"Could not delete {dir_path}: {e}")

    if deleted_count == 0:
        print(f"✓ No old directories to clean up")
    else:
        print(f"✓ Cleaned up {deleted_count} old director{'y' if deleted_count == 1 else 'ies'}")


def create_metadata(work_dir: Path, symbol: str) -> Dict:
    """
    Create metadata file to track research progress.

    Args:
        work_dir: Work directory path
        symbol: Stock ticker symbol

    Returns:
        Metadata dictionary with tracking information

    Example:
        >>> metadata = create_metadata(Path('work/TSLA_20260116'), 'TSLA')
        >>> print(metadata['symbol'])
        TSLA
    """
    metadata = {
        'symbol': symbol,
        'research_date': datetime.now().strftime('%Y-%m-%d'),
        'research_timestamp': datetime.now().isoformat(),
        'phases_completed': [],
        'phases_failed': [],
        'errors': [],
        'data_sources': {}
    }

    metadata_path = work_dir / '00_metadata.json'
    try:
        with metadata_path.open('w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Created metadata file: {metadata_path}")
    except IOError as e:
        logger.error(f"Failed to create metadata file: {e}")
        raise

    return metadata


def save_metadata(work_dir: Path, metadata: Dict) -> None:
    """
    Save updated metadata to file.

    Args:
        work_dir: Work directory path
        metadata: Metadata dictionary to save

    Example:
        >>> save_metadata(work_dir, metadata)
    """
    metadata_path = work_dir / '00_metadata.json'
    try:
        with metadata_path.open('w') as f:
            json.dump(metadata, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save metadata: {e}")


def run_phase(
    phase_name: str,
    phase_script: Path,
    symbol: str,
    work_dir: Path,
    metadata: Dict,
    metadata_lock: Optional[object] = None,
    extra_args: Optional[List[str]] = None
) -> bool:
    """
    Execute a research phase script.

    Args:
        phase_name: Name of the phase (e.g., 'technical', 'fundamental')
        phase_script: Path to phase script file
        symbol: Stock ticker symbol
        work_dir: Work directory path
        metadata: Metadata dictionary for tracking
        metadata_lock: Threading lock for metadata updates (optional)
        extra_args: List of extra command-line arguments (optional)

    Returns:
        True if phase succeeded, False otherwise

    Example:
        >>> success = run_phase(
        ...     'technical',
        ...     Path('skills/research_technical.py'),
        ...     'TSLA',
        ...     Path('work/TSLA_20260116'),
        ...     metadata
        ... )
    """
    print(f"\n{'='*60}")
    print(f"Phase: {phase_name.upper()}")
    print(f"{'='*60}")

    try:
        cmd = [str(phase_script), symbol, '--work-dir', str(work_dir)]
        if extra_args:
            cmd.extend(extra_args)

        phase_timeout = PHASE_TIMEOUTS.get(phase_name, 300)

        logger.debug(f"Executing command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=phase_timeout
        )

        if result.stdout:
            print(result.stdout)

        def update_metadata_success():
            metadata['phases_completed'].append(phase_name)
            print(f"\n✓ Phase '{phase_name}' completed successfully")
            save_metadata(work_dir, metadata)

        def update_metadata_failure(error_msg: str):
            metadata['phases_failed'].append(phase_name)
            metadata['errors'].append(error_msg)
            print(f"\n❌ {error_msg}")
            save_metadata(work_dir, metadata)

        if result.returncode == 0:
            if metadata_lock:
                with metadata_lock:
                    update_metadata_success()
            else:
                update_metadata_success()
            return True
        else:
            error_msg = f"Phase '{phase_name}' failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"

            if metadata_lock:
                with metadata_lock:
                    update_metadata_failure(error_msg)
            else:
                update_metadata_failure(error_msg)
            return False

    except subprocess.TimeoutExpired:
        timeout_minutes = phase_timeout // 60
        error_msg = f"Phase '{phase_name}' timed out after {timeout_minutes} minutes"
        logger.error(error_msg)

        if metadata_lock:
            with metadata_lock:
                metadata['phases_failed'].append(phase_name)
                metadata['errors'].append(error_msg)
                save_metadata(work_dir, metadata)
        else:
            metadata['phases_failed'].append(phase_name)
            metadata['errors'].append(error_msg)
            save_metadata(work_dir, metadata)
        print(f"\n⏱️  {error_msg}")
        return False

    except FileNotFoundError:
        error_msg = f"Phase script not found: {phase_script}"
        logger.error(error_msg)

        if metadata_lock:
            with metadata_lock:
                metadata['phases_failed'].append(phase_name)
                metadata['errors'].append(error_msg)
                save_metadata(work_dir, metadata)
        else:
            metadata['phases_failed'].append(phase_name)
            metadata['errors'].append(error_msg)
            save_metadata(work_dir, metadata)
        print(f"\n❌ {error_msg}")
        return False

    except Exception as e:
        error_msg = f"Phase '{phase_name}' encountered unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)

        if metadata_lock:
            with metadata_lock:
                metadata['phases_failed'].append(phase_name)
                metadata['errors'].append(error_msg)
                save_metadata(work_dir, metadata)
        else:
            metadata['phases_failed'].append(phase_name)
            metadata['errors'].append(error_msg)
            save_metadata(work_dir, metadata)
        print(f"\n❌ {error_msg}")
        return False


def main() -> int:
    """
    Main execution function.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Comprehensive stock research orchestrator'
    )
    parser.add_argument(
        'symbol',
        help='Stock ticker symbol (e.g., INTC, AAPL, MSFT)'
    )
    parser.add_argument(
        '--phases',
        default='all',
        help='Comma-separated list of phases to run (default: all)\n'
             'Available phases: technical, fundamental, research, sec, wikipedia, report'
    )
    parser.add_argument(
        '--skip-cleanup',
        action='store_true',
        help='Do not delete old work directories for this symbol'
    )
    parser.add_argument(
        '--peers',
        default=None,
        help='Comma-separated list of custom peer tickers (e.g., "GM,F,TM,RIVN")'
    )
    parser.add_argument(
        '--no-filter-peers',
        action='store_true',
        help='Disable automatic peer filtering (filtering is enabled by default)'
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

    print("=" * 60)
    print("Stock Research Orchestrator")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Phases: {args.phases}")
    print(f"Date: {format_date(datetime.now(), DATE_FORMAT_DISPLAY)}")
    print("=" * 60)

    # Step 1: Validate ticker
    print(f"\n{'='*60}")
    print("Step 1: Ticker Validation")
    print(f"{'='*60}")

    if not validate_ticker(symbol):
        print(f"\n❌ ERROR: Invalid ticker symbol '{symbol}'")
        print("Please check the ticker and try again.")
        return 1

    print(f"✓ Ticker '{symbol}' validated")

    # Step 2: Work Directory Setup
    print(f"\n{'='*60}")
    print("Step 2: Work Directory Setup")
    print(f"{'='*60}")

    date_str = datetime.now().strftime(DATE_FORMAT_FILE)
    work_dir = Path(WORK_DIR) / f"{symbol}_{date_str}"

    # Step 3: Cleanup old directories BEFORE creating new one
    cleanup_old_directories(symbol, work_dir, args.skip_cleanup)

    # Create new work directory
    ensure_directory(work_dir)
    print(f"✓ Created work directory: {work_dir}")

    # Step 4: Create metadata
    metadata = create_metadata(work_dir, symbol)

    # Step 5: Determine which phases to run
    skills_dir = Path(__file__).parent
    all_phases: Dict[str, Path] = {
        'technical': skills_dir / 'research_technical.py',
        'fundamental': skills_dir / 'research_fundamental.py',
        'research': skills_dir / 'research_perplexity.py',
        'analysis': skills_dir / 'research_analysis.py',
        'sec': skills_dir / 'research_sec.py',
        'wikipedia': skills_dir / 'research_wikipedia.py',
        'report': skills_dir / 'research_report.py',
        'deep': skills_dir / 'research_deep.py',
        'final': skills_dir / 'research_final.py'
    }

    if args.phases.lower() == 'all':
        phases_to_run = list(all_phases.keys())
    else:
        phases_to_run = [p.strip() for p in args.phases.split(',')]

    # Validate phase names
    invalid_phases = [p for p in phases_to_run if p not in all_phases]
    if invalid_phases:
        print(f"\n❌ ERROR: Invalid phase names: {', '.join(invalid_phases)}")
        print(f"Available phases: {', '.join(all_phases.keys())}")
        return 1

    # Validate API keys for phases to run
    print(f"\n{'='*60}")
    print("Step 3: API Key Validation")
    print(f"{'='*60}")

    valid_keys, missing_keys = validate_api_keys(phases_to_run)
    if not valid_keys:
        print(f"\n❌ ERROR: Required API keys are missing:")
        for key in missing_keys:
            print(f"  - {key}")
        print(f"\nPlease add the missing keys to your .env file and try again.")
        print(f"Example .env entry:")
        for key in missing_keys:
            print(f"  {key}=your_key_here")
        return 1

    print(f"✓ All required API keys are present")

    print(f"\n{'='*60}")
    print("Step 4: Get Company Overview")
    print(f"{'='*60}")
    logger.info(f"Fetching foundational company data for {symbol}...")

    # Run company overview first (quick, foundational data)
    if save_company_overview(symbol, work_dir):
        print(f"✓ Company overview data ready")
    else:
        logger.warning("Could not fetch company overview, continuing with other phases...")

    print(f"\n{'='*60}")
    print("Step 5: Execute Research Phases")
    print(f"{'='*60}")
    print(f"Phases to run: {', '.join(phases_to_run)}")

    success_count = 0
    failed_count = 0

    # Separate phases into groups for sequential execution
    technical_phase = 'technical' in phases_to_run
    other_data_phases = [p for p in phases_to_run if p not in ['technical', 'report', 'deep', 'final']]
    report_phase = 'report' in phases_to_run
    deep_phase = 'deep' in phases_to_run
    final_phase = 'final' in phases_to_run

    # Execute technical phase FIRST (sequential) - generates peers list
    if technical_phase:
        print(f"\n{'='*60}")
        print("Executing technical phase (sequential - generates peer list)...")
        print(f"{'='*60}")

        phase_script = all_phases['technical']
        if phase_script.exists():
            extra_args = []
            if args.peers:
                extra_args.extend(['--peers', args.peers])
            if args.no_filter_peers:
                extra_args.append('--no-filter-peers')

            success = run_phase('technical', phase_script, symbol, work_dir, metadata, metadata_lock=None, extra_args=extra_args)
            if success:
                success_count += 1
            else:
                failed_count += 1
                logger.warning("Technical phase failed - fundamental phase may have incomplete peer data")
        else:
            logger.info("Skipping 'technical' - script not yet implemented")

    # Execute remaining data phases in parallel (if any)
    if other_data_phases:
        print(f"\n{'='*60}")
        print(f"Executing {len(other_data_phases)} remaining data phases in parallel...")
        print(f"(Technical phase already completed - peer list available)")
        print(f"{'='*60}")

        manager = Manager()
        metadata_lock = manager.Lock()

        with ProcessPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
            future_to_phase = {}
            for phase_name in other_data_phases:
                phase_script = all_phases[phase_name]

                if not phase_script.exists():
                    logger.info(f"Skipping '{phase_name}' - script not yet implemented")
                    continue

                future = executor.submit(run_phase, phase_name, phase_script, symbol, work_dir, metadata, metadata_lock, [])
                future_to_phase[future] = phase_name

            for future in as_completed(future_to_phase):
                phase_name = future_to_phase[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Unexpected error in parallel execution for '{phase_name}': {e}", exc_info=True)
                    failed_count += 1

    # Execute report phase sequentially (after all data gathered)
    if report_phase:
        phase_script = all_phases['report']
        if phase_script.exists():
            print(f"\n{'='*60}")
            print("Generating initial research report...")
            print(f"{'='*60}")
            success = run_phase('report', phase_script, symbol, work_dir, metadata)
            if success:
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.info("Skipping 'report' - script not yet implemented")

    # Execute deep research phase sequentially (after report)
    if deep_phase:
        phase_script = all_phases['deep']
        if phase_script.exists():
            print(f"\n{'='*60}")
            print("Running deep research with Claude API...")
            print("This may take a few minutes with extended thinking enabled...")
            print(f"{'='*60}")
            success = run_phase('deep', phase_script, symbol, work_dir, metadata)
            if success:
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.info("Skipping 'deep' - script not yet implemented")

    # Execute final report phase sequentially (after deep)
    if final_phase:
        phase_script = all_phases['final']
        if phase_script.exists():
            print(f"\n{'='*60}")
            print("Assembling final report with multi-format conversion...")
            print(f"{'='*60}")
            success = run_phase('final', phase_script, symbol, work_dir, metadata)
            if success:
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.info("Skipping 'final' - script not yet implemented")

    # Step 6: Final summary
    print(f"\n{'='*60}")
    print("Research Complete")
    print(f"{'='*60}")
    print(f"Symbol: {symbol}")
    print(f"Completed at: {format_date(datetime.now(), DATE_FORMAT_DISPLAY)}")
    print(f"Work directory: {work_dir}")
    print(f"Phases completed: {success_count}")
    print(f"Phases failed: {failed_count}")

    if metadata['phases_completed']:
        print(f"\n✓ Completed phases: {', '.join(metadata['phases_completed'])}")

    if metadata['phases_failed']:
        print(f"\n❌ Failed phases: {', '.join(metadata['phases_failed'])}")
        for error in metadata['errors']:
            print(f"  - {error}")

    print(f"\n{'='*60}")

    if success_count > 0:
        print("✓ Research partially or fully completed")
        print(f"✓ See outputs in: {work_dir}")
        return 0
    else:
        print("❌ No phases completed successfully")
        return 1


if __name__ == '__main__':
    sys.exit(main())
