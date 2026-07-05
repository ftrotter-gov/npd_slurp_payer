# FHIR Dataset Downloader Specification

## Purpose

Develop a Python command-line utility that downloads and maintains a local mirror of FHIR-related JSON resources from a collection of starting URLs.

The downloader is intended to support later analysis of payer and provider directory implementations. Its primary goal is to create a reproducible, resumable, filesystem-based mirror of all downloaded resources while minimizing unnecessary network traffic.

This utility is **only responsible for downloading resources**. It performs no semantic analysis of the JSON content beyond extracting additional URLs from index files.

---

# Overall Workflow

The downloader operates in two phases.

## Phase 1: Download Index Files

The input to the program is a CSV file containing starting URLs.

Each URL points to an "index" JSON document. These may include Da Vinci FAST Directory Exchange indexes, CMS Provider Directory index documents, or similar JSON resources that contain references to additional downloadable resources.

The downloader shall:

* Read every URL from the CSV file.
* Download each index JSON.
* Store each downloaded file in the local mirror.
* Skip downloads when a sufficiently recent local copy already exists (see Resume Behavior).

---

## Phase 2: Download Referenced Resources

After all index files have been downloaded, the downloader shall parse every downloaded index file to discover additional URLs.

These discovered URLs become the secondary download queue.

The downloader shall then:

* Download every referenced resource.
* Store each resource in the local mirror.
* Skip downloads when a recent copy already exists.

This phase should also be resumable.

---

### Command-Line Interface

The utility shall accept exactly two command-line arguments.

```bash
python downloader.py <starting_urls.csv> <output_directory>
```

Example:

```bash
python downloader.py seed_urls.csv downloads/
```

Arguments:

### starting_urls.csv

CSV file containing the initial list of URLs.

The first implementation may assume one URL per row.

Future versions may support additional metadata columns.

There are many rows of data in the payer_url_list.csv file that have no url. These should be ignored.
Sometimes there are space-seperated urls. These should be seperated and parsed.

Please throw an  and immediately halt the program if the URL column of the csv file has contents.. that cannot be converted to one or more valid urls.
When this happens, print the line in the file and the offending URL column contents.

Do not consider or attempt to process the other data in the payer_url_list.csv file. Later stages of the program will handle this.

---

### output_directory

Root directory of the local mirror.

If the directory does not exist, it shall be created automatically.

---

### Local Mirror Layout

The output directory shall contain a filesystem mirror of the downloaded URLs.

For example:

```diagram
payer_raw_data_cache/

    example.com/
        directory/
            index.json

    payer.org/
        fhir/
            Bundle.json

    cms.gov/
        provider-directory/
            index.json
```

The directory hierarchy beneath each domain should exactly match the URL path.

For example:

URL:

```url
https://payer.example.org/fhir/Organization/123
```

becomes

```diagram
downloads/

    payer.example.org/

        fhir/

            Organization/

                123
```

If the URL ends with a slash or otherwise has no filename, the implementation may append a default filename such as `index.json`.

The goal is that the local filesystem visually resembles a local copy of the Internet.

---

## Directory Creation

The downloader shall automatically create any required intermediate directories before writing files.

The implementation should use standard Python filesystem utilities (e.g. `pathlib.Path.mkdir(..., parents=True, exist_ok=True)`).

---

## Resume Behavior

The downloader must be resumable.

Before downloading any resource, it shall determine whether a local copy already exists.

If:

* the file exists, and
* its modification timestamp is less than a freshness value ,then the download shall be skipped.Otherwise, the resource shall be downloaded again.

The download freshness value should default to 24 hours, but should be overridden by DOWNLOAD_FRESHNESS_DAYS in a .env file.. and then also documented clearly in the ./example.env. The env variable DOWNLOAD_FRESHNESS_DAYS should accept only whole integers)

This allows repeated executions of the downloader without unnecessarily re-downloading previously retrieved resources.

---

## Idempotency

Running the downloader multiple times against the same inputs should produce identical results, aside from resources that have changed remotely.

Repeated executions should primarily perform filesystem checks rather than network requests.

The file should always reload the ./payer_url_list.csv to ensure that new contents are checked.

---

## Parsing Index Files

After Phase 1 completes, the downloader shall inspect every downloaded index JSON.

The downloader only needs to discover additional URLs.

It is **not** responsible for validating or interpreting FHIR resources beyond locating referenced download URLs.

The URL extraction logic should be isolated into a dedicated function or module so that additional index formats can be supported later.

Every file that is referenced in an index file should be subsequently added to the download queue, including files that are not json files.
Note that the index files will vary greatly in how they are structured.

When judging when something is a url, be permissive: (starts with `http://`, `https://`, or looks like a relative path like `/api/resource`)

---

## Download Queue

The downloader should internally maintain a queue of URLs to download.

Duplicate URLs should only be downloaded once during a run.

If the same URL appears multiple times across different index files, it should only exist once in the download queue.

---

## Network Behavior

The downloader should:

* follow redirects
* use HTTPS whenever specified
* retry transient network failures
* continue processing if one URL fails
* log failures without terminating the overall download process
* handle both fully explict and reative url paths. Assume relative file locations have the same base url as the index file
* Look in every json value field and when the contents are a correctly formed relative or full url, download the results
* When a file does not have an extension. Do not add one. So if it is just 'Practicioner' leave it that way.
 

---

## Logging

The downloader should produce human-readable console output.

Examples:

```
Downloading:
https://payer.example.org/fhir/index.json

Skipping (fresh):
https://payer.example.org/fhir/Organization/123

Retrying:
https://example.com/file.json

Failed:
https://example.com/file.json
```

Progress information should make it easy to resume interrupted runs.

---

## File Preservation

Downloaded content shall be stored exactly as received.

The downloader must not:

* pretty-print JSON
* reorder JSON keys
* normalize formatting
* modify line endings
* rewrite content

The goal is to preserve the original server response exactly.

---

## Error Handling

Errors downloading individual resources shall not terminate the overall run.

The downloader should continue processing remaining URLs whenever possible.

Failures should be logged for later inspection.

---

## Implementation Requirements

Language:

* Python 3.12+

Preferred standard libraries:

* `pathlib`
* `urllib.parse`
* `csv`
* `json`
* `argparse`
* `logging`
* `hashlib`
* `datetime`

Preferred third-party library:

* `requests`

Avoid unnecessary dependencies.

---

## Design Goals

The implementation should be modular.

At minimum, separate responsibilities into functions or classes responsible for:

* command-line argument parsing
* filesystem path generation
* downloading resources
* determining freshness
* parsing index files
* extracting referenced URLs
* managing the download queue

The downloader is intended to serve as the foundation for later tools that will inventory, normalize, and analyze the downloaded FHIR ecosystem.

Accordingly, correctness, reproducibility, and resumability are significantly more important than maximum download speed.

This project will use venv and a requirements.txt file for storing its python dependacy settings.

The project should use a structure of 'step_xx' files and this should be step_10_download.py
There should be a go.py runner file. which allows for the steps to be run by referencing their numbers.
The arguments that go.py passes to the steps should all be defined in .env and explained in example.env

