#!/usr/bin/env python3
"""
FHIR Dataset Downloader - Step 10

Downloads and maintains a local mirror of FHIR-related resources from starting URLs.
Operates in two phases:
1. Download index files from CSV
2. Parse index files and download referenced resources

Uses a modular design with static methods for maintainability and testability.
"""

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Tuple, Optional, Any
from urllib.parse import urlparse, urljoin, urlunparse

import requests
from dotenv import load_dotenv
import os


class ConfigLoader:
    """Loads and manages configuration from .env file."""
    
    @staticmethod
    def load_config():
        """Load configuration from .env file."""
        load_dotenv()
    
    @staticmethod
    def get_csv_path() -> str:
        """Get the path to the CSV file containing starting URLs."""
        return os.getenv('STARTING_URLS_CSV', 'payer_url_list.csv')
    
    @staticmethod
    def get_output_dir() -> str:
        """Get the output directory for downloaded files."""
        return os.getenv('OUTPUT_DIRECTORY', 'payer_raw_data_cache')
    
    @staticmethod
    def get_freshness_days() -> int:
        """Get the freshness threshold in days (whole integers only)."""
        try:
            return int(os.getenv('DOWNLOAD_FRESHNESS_DAYS', '1'))
        except ValueError:
            logging.warning("step_10_download.py Warning: DOWNLOAD_FRESHNESS_DAYS must be an integer, using default of 1")
            return 1


class ExcludedDomains:
    """Manages list of domains that should not be crawled."""
    
    _excluded_domains: Set[str] = set()
    _loaded: bool = False
    
    @staticmethod
    def load_excluded_domains(*, csv_path: str = 'excluded_domain_list.csv') -> None:
        """
        Load excluded domains from CSV file.
        
        Args:
            csv_path: Path to CSV file with excluded domains
        """
        if ExcludedDomains._loaded:
            return
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    domain = row.get('domain', '').strip().lower()
                    if domain:
                        ExcludedDomains._excluded_domains.add(domain)
            
            ExcludedDomains._loaded = True
            if ExcludedDomains._excluded_domains:
                logging.info(f"Loaded {len(ExcludedDomains._excluded_domains)} excluded domain(s)")
        except FileNotFoundError:
            logging.warning(f"step_10_download.py Warning: Excluded domains file not found: {csv_path}")
            ExcludedDomains._loaded = True
        except Exception as e:
            logging.warning(f"step_10_download.py Warning: Failed to load excluded domains: {e}")
            ExcludedDomains._loaded = True
    
    @staticmethod
    def is_excluded(*, url: str) -> bool:
        """
        Check if a URL's domain is in the excluded list.
        
        Args:
            url: URL to check
            
        Returns:
            True if domain is excluded, False otherwise
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check exact match or if domain ends with any excluded domain
            for excluded in ExcludedDomains._excluded_domains:
                if domain == excluded or domain.endswith('.' + excluded):
                    return True
            
            return False
        except Exception:
            return False


class URLParser:
    """Handles parsing and validation of URLs from CSV and JSON files."""
    
    @staticmethod
    def parse_csv(*, csv_path: str) -> List[str]:
        """
        Parse CSV file and extract valid URLs.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            List of valid URLs
            
        Raises:
            ValueError: If a URL column contains invalid content
        """
        urls = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if 'URL' not in reader.fieldnames:
                raise ValueError(f"step_10_download.py Error: CSV file {csv_path} does not have a 'URL' column")
            
            for line_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
                url_column = row.get('URL', '').strip()
                
                # Skip empty URL columns
                if not url_column:
                    continue
                
                # Split space-separated URLs
                url_parts = url_column.split()
                
                for url_part in url_parts:
                    url_part = url_part.strip()
                    if not url_part:
                        continue
                    
                    # Validate URL
                    if not URLParser._validate_url(url=url_part):
                        raise ValueError(
                            f"step_10_download.py Error: Invalid URL at line {line_num}\n"
                            f"URL column contents: {url_column}\n"
                            f"Invalid URL: {url_part}"
                        )
                    
                    urls.append(url_part)
        
        return urls
    
    @staticmethod
    def _validate_url(*, url: str) -> bool:
        """
        Validate that a string is a properly formed URL.
        
        Args:
            url: URL string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            result = urlparse(url)
            # Must have scheme (http/https) and netloc (domain)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def extract_urls_from_json(*, json_content: bytes, base_url: str) -> Set[str]:
        """
        Extract URLs from JSON content.
        
        Permissive approach: looks for any string value that appears to be a URL.
        Supports both absolute URLs (http://, https://) and relative paths.
        Filters out URLs from excluded domains.
        
        Args:
            json_content: Raw JSON content as bytes
            base_url: Base URL for resolving relative paths
            
        Returns:
            Set of discovered URLs (excluding filtered domains)
        """
        urls = set()
        
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            logging.warning(f"step_10_download.py Warning: Failed to parse JSON from {base_url}: {e}")
            return urls
        
        # Recursively extract URLs from the JSON structure
        URLParser._extract_urls_recursive(data=data, base_url=base_url, urls=urls)
        
        # Filter out excluded domains
        filtered_urls = set()
        excluded_count = 0
        for url in urls:
            if ExcludedDomains.is_excluded(url=url):
                excluded_count += 1
            else:
                filtered_urls.add(url)
        
        if excluded_count > 0:
            logging.info(f"Filtered {excluded_count} URL(s) from excluded domains in {base_url}")
        
        return filtered_urls
    
    @staticmethod
    def _extract_urls_recursive(*, data: Any, base_url: str, urls: Set[str]) -> None:
        """
        Recursively walk JSON structure and extract URL-like strings.
        
        Args:
            data: JSON data (dict, list, or primitive)
            base_url: Base URL for resolving relative paths
            urls: Set to accumulate discovered URLs (modified in place)
        """
        if isinstance(data, dict):
            for value in data.values():
                URLParser._extract_urls_recursive(data=value, base_url=base_url, urls=urls)
        
        elif isinstance(data, list):
            for item in data:
                URLParser._extract_urls_recursive(data=item, base_url=base_url, urls=urls)
        
        elif isinstance(data, str):
            # Check if the string looks like a URL
            url_candidate = data.strip()
            
            # Absolute URLs
            if url_candidate.startswith(('http://', 'https://')):
                urls.add(url_candidate)
            
            # Relative URLs starting with /
            elif url_candidate.startswith('/'):
                absolute_url = urljoin(base_url, url_candidate)
                urls.add(absolute_url)
            
            # Other relative paths (contains / but not ://)
            elif '/' in url_candidate and '://' not in url_candidate:
                absolute_url = urljoin(base_url, url_candidate)
                urls.add(absolute_url)


class FileSystemManager:
    """Manages filesystem operations for downloaded files."""
    
    @staticmethod
    def url_to_filepath(*, url: str, output_dir: str) -> Path:
        """
        Convert URL to local filesystem path.
        
        Preserves the exact URL structure without adding extensions.
        
        Args:
            url: URL to convert
            output_dir: Root output directory
            
        Returns:
            Path object for the local file
        """
        parsed = urlparse(url)
        
        # Start with domain
        path_parts = [output_dir, parsed.netloc]
        
        # Add path components
        url_path = parsed.path.lstrip('/')
        
        if not url_path or url_path.endswith('/'):
            # URL ends with slash or has no path - use index.json
            if url_path:
                path_parts.extend(url_path.rstrip('/').split('/'))
            path_parts.append('index.json')
        else:
            # URL has a path - use it as-is (do not add extensions)
            path_parts.extend(url_path.split('/'))
        
        return Path(*path_parts)
    
    @staticmethod
    def is_file_fresh(*, filepath: Path, freshness_days: int) -> bool:
        """
        Check if a file exists and is fresh (recent enough).
        
        Args:
            filepath: Path to the file
            freshness_days: Number of days to consider fresh
            
        Returns:
            True if file exists and is fresh, False otherwise
        """
        if not filepath.exists():
            return False
        
        # Get file modification time
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        
        # Check if it's fresh enough
        threshold = datetime.now() - timedelta(days=freshness_days)
        
        return mtime > threshold
    
    @staticmethod
    def ensure_directory_exists(*, filepath: Path) -> None:
        """
        Create parent directories for a file path if they don't exist.
        
        Handles the case where a path component exists as a file but needs to be a directory.
        In this case, the file is moved to index.json within a directory of that name.
        
        Args:
            filepath: Path to the file (directories will be created for parent)
        """
        parent = filepath.parent
        
        # Collect all path components that need to exist as directories
        path_components = []
        current = parent
        while current != current.parent:  # Stop at root
            path_components.insert(0, current)
            current = current.parent
        
        # Check each component - convert files to directories if needed
        for component_path in path_components:
            if component_path.exists() and component_path.is_file():
                # This path exists as a file but needs to be a directory
                # Move the file to index.json inside a directory of the same name
                logging.warning(
                    f"step_10_download.py Warning: Converting file to directory: {component_path}"
                )
                
                # Read the existing file content
                content = component_path.read_bytes()
                
                # Remove the file
                component_path.unlink()
                
                # Create as directory
                component_path.mkdir(parents=True, exist_ok=True)
                
                # Save content as index.json
                index_file = component_path / 'index.json'
                index_file.write_bytes(content)
                
                logging.info(f"  Moved to: {index_file}")
            elif not component_path.exists():
                # Create the directory if it doesn't exist
                component_path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def save_content(*, filepath: Path, content: bytes) -> None:
        """
        Save content to a file exactly as received (binary mode).
        
        Handles the case where filepath exists as a directory (saves to index.json inside).
        
        Args:
            filepath: Path where content should be saved
            content: Raw bytes to save
        """
        # If the target path exists as a directory, save to index.json inside it
        if filepath.exists() and filepath.is_dir():
            logging.warning(
                f"step_10_download.py Warning: Path exists as directory, saving to index.json: {filepath}"
            )
            filepath = filepath / 'index.json'
        
        with open(filepath, 'wb') as f:
            f.write(content)


class Downloader:
    """Handles HTTP downloads with retry logic."""
    
    @staticmethod
    def download_url(*, url: str, max_retries: int = 3) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Download content from a URL with retry logic.
        
        Args:
            url: URL to download
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, content, error_message)
        """
        for attempt in range(max_retries):
            try:
                # Make request with redirects enabled
                response = requests.get(url, allow_redirects=True, timeout=30)
                response.raise_for_status()
                
                logging.info(f"Downloading: {url}")
                return True, response.content, None
                
            except Exception as e:
                error_msg = f"step_10_download.py Error downloading {url}: {str(e)}"
                
                # Check if we should retry
                if attempt < max_retries - 1 and Downloader._should_retry(exception=e):
                    logging.warning(f"Retrying: {url} (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    logging.error(f"Failed: {url} - {error_msg}")
                    return False, None, error_msg
        
        return False, None, f"step_10_download.py Error: Max retries exceeded for {url}"
    
    @staticmethod
    def _should_retry(*, exception: Exception) -> bool:
        """
        Determine if an exception represents a transient error worth retrying.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            True if the error seems transient, False otherwise
        """
        # Network errors, timeouts, and 5xx server errors are retryable
        if isinstance(exception, requests.exceptions.RequestException):
            if isinstance(exception, requests.exceptions.Timeout):
                return True
            if isinstance(exception, requests.exceptions.ConnectionError):
                return True
            if isinstance(exception, requests.exceptions.HTTPError):
                if exception.response is not None and exception.response.status_code >= 500:
                    return True
        
        return False


class DownloadQueue:
    """Manages a queue of URLs to download with deduplication."""
    
    _queue: Set[str] = set()
    _processed: Set[str] = set()
    
    @staticmethod
    def add_url(*, url: str) -> bool:
        """
        Add a URL to the download queue if not already present.
        
        Args:
            url: URL to add
            
        Returns:
            True if added, False if duplicate
        """
        if url not in DownloadQueue._processed and url not in DownloadQueue._queue:
            DownloadQueue._queue.add(url)
            return True
        return False
    
    @staticmethod
    def add_urls(*, urls: List[str]) -> int:
        """
        Add multiple URLs to the queue.
        
        Args:
            urls: List of URLs to add
            
        Returns:
            Number of URLs actually added (excluding duplicates)
        """
        added = 0
        for url in urls:
            if DownloadQueue.add_url(url=url):
                added += 1
        return added
    
    @staticmethod
    def get_next() -> Optional[str]:
        """
        Get the next URL from the queue.
        
        Returns:
            Next URL or None if queue is empty
        """
        if DownloadQueue._queue:
            url = DownloadQueue._queue.pop()
            DownloadQueue._processed.add(url)
            return url
        return None
    
    @staticmethod
    def is_empty() -> bool:
        """Check if the queue is empty."""
        return len(DownloadQueue._queue) == 0
    
    @staticmethod
    def clear() -> None:
        """Clear the queue and processed set."""
        DownloadQueue._queue.clear()
        DownloadQueue._processed.clear()


class DownloadOrchestrator:
    """Orchestrates the two-phase download process."""
    
    @staticmethod
    def run(*, csv_path: str, output_dir: str, freshness_days: int) -> None:
        """
        Main entry point for the download process.
        
        Args:
            csv_path: Path to CSV file with starting URLs
            output_dir: Output directory for downloads
            freshness_days: Freshness threshold in days
        """
        logging.info("="*70)
        logging.info("FHIR Dataset Downloader - Starting")
        logging.info(f"CSV file: {csv_path}")
        logging.info(f"Output directory: {output_dir}")
        logging.info(f"Freshness threshold: {freshness_days} days")
        logging.info("="*70)
        
        # Load excluded domains
        logging.info("\nLoading excluded domains...")
        ExcludedDomains.load_excluded_domains()
        
        # Parse CSV to get starting URLs
        logging.info("\nParsing CSV file...")
        try:
            urls = URLParser.parse_csv(csv_path=csv_path)
            logging.info(f"Found {len(urls)} URLs in CSV file")
        except Exception as e:
            logging.error(f"step_10_download.py Error: Failed to parse CSV: {e}")
            raise
        
        # Phase 1: Download index files
        logging.info("\n" + "="*70)
        logging.info("PHASE 1: Downloading index files from CSV")
        logging.info("="*70)
        index_files = DownloadOrchestrator._download_phase_1(
            urls=urls,
            output_dir=output_dir,
            freshness_days=freshness_days
        )
        logging.info(f"\nPhase 1 complete: {len(index_files)} index files available")
        
        # Phase 2: Parse index files and download referenced resources
        logging.info("\n" + "="*70)
        logging.info("PHASE 2: Parsing index files and downloading referenced resources")
        logging.info("="*70)
        DownloadOrchestrator._download_phase_2(
            index_files=index_files,
            output_dir=output_dir,
            freshness_days=freshness_days
        )
        
        logging.info("\n" + "="*70)
        logging.info("FHIR Dataset Downloader - Complete")
        logging.info("="*70)
    
    @staticmethod
    def _download_phase_1(*, urls: List[str], output_dir: str, freshness_days: int) -> List[Path]:
        """
        Phase 1: Download index files from CSV.
        
        Args:
            urls: List of URLs to download
            output_dir: Output directory
            freshness_days: Freshness threshold
            
        Returns:
            List of successfully downloaded (or fresh) index file paths
        """
        # Deduplicate URLs while preserving order
        unique_urls = []
        seen = set()
        for url in urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        if len(unique_urls) < len(urls):
            duplicates = len(urls) - len(unique_urls)
            logging.info(f"Removed {duplicates} duplicate URL(s), processing {len(unique_urls)} unique URLs")
        
        index_files = []
        download_count = 0
        
        for url in unique_urls:
            filepath = FileSystemManager.url_to_filepath(url=url, output_dir=output_dir)
            
            # Check if file is fresh (applies to BOTH Phase 1 and Phase 2)
            if FileSystemManager.is_file_fresh(filepath=filepath, freshness_days=freshness_days):
                # Skip silently - no logging for fresh files
                index_files.append(filepath)
                continue
            
            # Count only files being downloaded
            download_count += 1
            logging.info(f"\nDownload #{download_count}: {url}")
            
            # Download the file
            success, content, error = Downloader.download_url(url=url)
            
            if success:
                FileSystemManager.ensure_directory_exists(filepath=filepath)
                FileSystemManager.save_content(filepath=filepath, content=content)
                index_files.append(filepath)
            else:
                logging.error(f"step_10_download.py Error: Failed to download index file: {url}")
        
        return index_files
    
    @staticmethod
    def _download_phase_2(*, index_files: List[Path], output_dir: str, freshness_days: int) -> None:
        """
        Phase 2: Parse index files and download referenced resources.
        
        Args:
            index_files: List of index file paths to parse
            output_dir: Output directory
            freshness_days: Freshness threshold
        """
        # Clear the queue from any previous runs
        DownloadQueue.clear()
        
        # Parse all index files and collect URLs
        logging.info("\nParsing index files to extract URLs...")
        total_urls_found = 0
        
        for index_file in index_files:
            try:
                # Read the index file
                with open(index_file, 'rb') as f:
                    content = f.read()
                
                # Reconstruct the base URL from the filepath
                # This is needed to resolve relative URLs
                base_url = DownloadOrchestrator._reconstruct_url_from_path(
                    filepath=index_file,
                    output_dir=output_dir
                )
                
                # Extract URLs
                urls = URLParser.extract_urls_from_json(json_content=content, base_url=base_url)
                
                if urls:
                    added = DownloadQueue.add_urls(urls=list(urls))
                    total_urls_found += len(urls)
                    logging.info(f"Extracted {len(urls)} URLs from {index_file.name} ({added} new)")
                
            except Exception as e:
                logging.warning(f"step_10_download.py Warning: Failed to parse {index_file}: {e}")
        
        logging.info(f"\nTotal URLs found: {total_urls_found}")
        logging.info(f"Unique URLs to process: {len(DownloadQueue._queue)}")
        
        # PREPROCESSING PASS: Identify which path components must be directories
        # This prevents file/directory conflicts before downloading
        logging.info("\nPreprocessing: Analyzing URL structure...")
        DownloadOrchestrator._preprocess_directory_structure(
            urls=list(DownloadQueue._queue),
            output_dir=output_dir
        )
        
        # Download all queued resources
        logging.info("\nDownloading referenced resources...")
        downloaded = 0
        skipped = 0
        failed = 0
        
        while not DownloadQueue.is_empty():
            url = DownloadQueue.get_next()
            if url is None:
                break
            
            filepath = FileSystemManager.url_to_filepath(url=url, output_dir=output_dir)
            
            # Check if file is fresh
            if FileSystemManager.is_file_fresh(filepath=filepath, freshness_days=freshness_days):
                # Skip silently - no logging for fresh files
                skipped += 1
                continue
            
            # Download the file
            success, content, error = Downloader.download_url(url=url)
            
            if success:
                FileSystemManager.ensure_directory_exists(filepath=filepath)
                FileSystemManager.save_content(filepath=filepath, content=content)
                downloaded += 1
            else:
                failed += 1
        
        logging.info(f"\nPhase 2 complete:")
        logging.info(f"  Downloaded: {downloaded}")
        logging.info(f"  Skipped (fresh): {skipped}")
        logging.info(f"  Failed: {failed}")
    
    @staticmethod
    def _preprocess_directory_structure(*, urls: List[str], output_dir: str) -> None:
        """
        Preprocess filesystem to identify path components that must be directories.
        
        Converts any existing files to directories if they are part of a longer path.
        For example, if 'resources' exists as a file but 'resources/file.json' needs
        to be downloaded, convert 'resources' to a directory with the content moved
        to 'resources/index.json'.
        
        Args:
            urls: List of all URLs that will be downloaded
            output_dir: Root output directory
        """
        # Collect all path components that need to be directories
        paths_must_be_dirs = set()
        
        for url in urls:
            filepath = FileSystemManager.url_to_filepath(url=url, output_dir=output_dir)
            
            # All parent directories must exist as directories
            parent = filepath.parent
            while parent != parent.parent:  # Stop at root
                paths_must_be_dirs.add(parent)
                parent = parent.parent
        
        # Sort by depth (shortest first) to process top-down
        sorted_paths = sorted(paths_must_be_dirs, key=lambda p: len(p.parts))
        
        # Convert any files to directories
        conversions = 0
        for path in sorted_paths:
            if path.exists() and path.is_file():
                logging.warning(
                    f"step_10_download.py Warning: Converting file to directory: {path}"
                )
                
                # Read the existing file content
                content = path.read_bytes()
                
                # Remove the file
                path.unlink()
                
                # Create as directory
                path.mkdir(parents=True, exist_ok=True)
                
                # Save content as index.json
                index_file = path / 'index.json'
                index_file.write_bytes(content)
                
                logging.info(f"  Moved to: {index_file}")
                conversions += 1
        
        if conversions > 0:
            logging.info(f"Converted {conversions} file(s) to directories")
        else:
            logging.info("No file/directory conflicts detected")
    
    @staticmethod
    def _reconstruct_url_from_path(*, filepath: Path, output_dir: str) -> str:
        """
        Reconstruct the original URL from a filesystem path.
        
        Args:
            filepath: Path to the downloaded file
            output_dir: Root output directory
            
        Returns:
            Reconstructed URL
        """
        # Get relative path from output_dir
        try:
            rel_path = filepath.relative_to(output_dir)
        except ValueError:
            # If filepath is not relative to output_dir, just use it as-is
            rel_path = filepath
        
        # First part is the domain
        parts = list(rel_path.parts)
        if not parts:
            return ""
        
        domain = parts[0]
        path_parts = parts[1:]
        
        # Remove 'index.json' if it's the last part
        if path_parts and path_parts[-1] == 'index.json':
            path_parts = path_parts[:-1]
        
        # Construct URL
        path = '/' + '/'.join(path_parts) if path_parts else '/'
        url = f"https://{domain}{path}"
        
        return url


def main():
    """Main entry point when script is run directly."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Download FHIR dataset resources from starting URLs'
    )
    parser.add_argument(
        'csv_path',
        help='Path to CSV file containing starting URLs'
    )
    parser.add_argument(
        'output_dir',
        help='Output directory for downloaded files'
    )
    
    args = parser.parse_args()
    
    # Load configuration (for freshness setting)
    ConfigLoader.load_config()
    freshness_days = ConfigLoader.get_freshness_days()
    
    # Run the downloader
    try:
        DownloadOrchestrator.run(
            csv_path=args.csv_path,
            output_dir=args.output_dir,
            freshness_days=freshness_days
        )
    except Exception as e:
        logging.error(f"step_10_download.py Error: Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
