# NPD Payer Slurp

Second generation project for the National Provider/Payer Directory to download and process public payer data.

## Overview

This project downloads and maintains a local mirror of FHIR-related resources from payer URLs. It operates in two phases:

1. **Phase 1:** Download index files from a CSV list of starting URLs
2. **Phase 2:** Parse index files and download all referenced resources

The downloader is designed to be resumable, idempotent, and preserves files exactly as received from servers.

## Setup

### Prerequisites

- Python 3.12+
- Virtual environment (recommended)

### Installation

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp example.env .env
# Edit .env to customize settings if needed
```

## Usage

### Basic Usage

Run the downloader using the pipeline runner:

```bash
python go.py 10
```

This executes Step 10 (the downloader) using configuration from `.env`.

### Direct Usage

You can also run the downloader directly:

```bash
python step_10_download.py <csv_file> <output_directory>
```

Example:

```bash
python step_10_download.py payer_url_list.csv payer_raw_data_cache
```

## Configuration

Configuration is managed through the `.env` file (see `example.env` for documentation):

- **STARTING_URLS_CSV**: Path to CSV file with starting URLs (default: `payer_url_list.csv`)
- **OUTPUT_DIRECTORY**: Root directory for downloads (default: `payer_raw_data_cache`)
- **DOWNLOAD_FRESHNESS_DAYS**: How many days before re-downloading files (default: `1`)

## CSV Format

The input CSV must have a `URL` column containing:

- One URL per row, OR
- Multiple space-separated URLs in a single cell
- Empty URL cells are skipped
- Invalid URLs will cause the program to halt with an error message

## Features

- **Resumable**: Re-running the downloader skips fresh files (based on `DOWNLOAD_FRESHNESS_DAYS`)
- **Idempotent**: Multiple runs produce identical results (unless remote data changed)
- **URL Deduplication**: Each unique URL is downloaded only once per run
- **Error Handling**: Individual download failures don't stop the entire process
- **Retry Logic**: Transient network errors are automatically retried
- **Exact Preservation**: Downloaded content is saved exactly as received (no reformatting)

## Output Structure

Downloaded files mirror the URL structure:

```
payer_raw_data_cache/
    example.com/
        api/
            index.json
        fhir/
            Practitioner
    payer.org/
        directory/
            Bundle.json
```

- Domain names become top-level directories
- URL paths are preserved exactly
- Files without extensions remain without extensions
- URLs ending in `/` are saved as `index.json`

## Architecture

The downloader uses a modular, class-based design with static methods:

- **ConfigLoader**: Manages `.env` configuration
- **URLParser**: Parses CSV and extracts URLs from JSON
- **FileSystemManager**: Handles file path generation and storage
- **Downloader**: Performs HTTP downloads with retry logic
- **DownloadQueue**: Manages URL queue with deduplication
- **DownloadOrchestrator**: Coordinates the two-phase download process

## Logging

The downloader produces human-readable console output showing:

- Progress through phases
- Download status for each URL
- Retry attempts
- Failures and warnings
- Summary statistics

## Future Steps

This project is designed to support a pipeline of steps:

- **Step 10**: Download raw data (current)
- **Step 20+**: Future processing and analysis steps (to be implemented)


