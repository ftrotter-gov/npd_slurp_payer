#!/usr/bin/env python3
"""
Pipeline Runner for NPD Payer Slurp

Executes pipeline steps by number, loading configuration from .env file.

Usage:
    python go.py <step_number>

Example:
    python go.py 10
"""

import sys
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv
import os


class StepRunner:
    """Manages execution of pipeline steps."""
    
    # Map step numbers to their corresponding script files
    STEP_MAP = {
        10: 'step_10_download.py',
        # Future steps can be added here
        # 20: 'step_20_process.py',
        # 30: 'step_30_analyze.py',
    }
    
    @staticmethod
    def run_step(*, step_number: int) -> int:
        """
        Run a pipeline step by number.
        
        Args:
            step_number: The step number to execute
            
        Returns:
            Exit code from the step execution
        """
        # Check if step exists
        if step_number not in StepRunner.STEP_MAP:
            logging.error(f"go.py Error: Step {step_number} is not defined")
            logging.error(f"Available steps: {sorted(StepRunner.STEP_MAP.keys())}")
            return 1
        
        step_file = StepRunner.STEP_MAP[step_number]
        
        # Check if step file exists
        if not Path(step_file).exists():
            logging.error(f"go.py Error: Step file {step_file} not found")
            return 1
        
        # Load configuration from .env
        load_dotenv()
        
        # Get configuration for step 10 (download)
        if step_number == 10:
            csv_path = os.getenv('STARTING_URLS_CSV', 'payer_url_list.csv')
            output_dir = os.getenv('OUTPUT_DIRECTORY', 'payer_raw_data_cache')
            
            logging.info("="*70)
            logging.info(f"NPD Payer Slurp - Running Step {step_number}")
            logging.info(f"Script: {step_file}")
            logging.info(f"Configuration from .env:")
            logging.info(f"  STARTING_URLS_CSV: {csv_path}")
            logging.info(f"  OUTPUT_DIRECTORY: {output_dir}")
            logging.info(f"  DOWNLOAD_FRESHNESS_DAYS: {os.getenv('DOWNLOAD_FRESHNESS_DAYS', '1')}")
            logging.info("="*70)
            
            # Execute the step
            result = subprocess.run(
                [sys.executable, step_file, csv_path, output_dir],
                cwd=Path.cwd()
            )
            
            return result.returncode
        
        # Future steps would be handled here
        else:
            logging.error(f"go.py Error: Step {step_number} execution not yet implemented")
            return 1


def main():
    """Main entry point for the runner."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Check command-line arguments
    if len(sys.argv) != 2:
        logging.error("go.py Error: Usage: python go.py <step_number>")
        logging.error("Example: python go.py 10")
        sys.exit(1)
    
    # Parse step number
    try:
        step_number = int(sys.argv[1])
    except ValueError:
        logging.error(f"go.py Error: Step number must be an integer, got: {sys.argv[1]}")
        sys.exit(1)
    
    # Run the step
    exit_code = StepRunner.run_step(step_number=step_number)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
