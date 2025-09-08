# Mirror Doc Api Documentation Crawler

This use case is configured to crawl and process documentation from `https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html`.

## Purpose

Extracts, processes, and merges web documentation from https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html into clean markdown collections.

## Configuration

- **Base URL**: `https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html`
- **Output Directory**: `output/mirror-doc-api/`
- **Merged Output**: `output/mirror-doc-api/merged_documentation.md`
- **Categories**: Documentation, API, Guides, Other

## Usage

### Quick Start
```bash
# Discover all URLs automatically (recommended first step)
python use-cases/document-processing/doc_processor.py discover-urls --base-url https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html --save-urls use-cases/mirror-doc-api/discovered_urls.txt

# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/mirror-doc-api/config.json
```

### Step-by-Step Processing
```bash
# 1. Discover URLs (automatic crawling)
python use-cases/document-processing/doc_processor.py discover-urls --base-url https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html --save-urls use-cases/mirror-doc-api/discovered_urls.txt

# 2. Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/mirror-doc-api/config.json

# 3. Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/mirror-doc-api/config.json
```

### Verify Configuration
```bash
# Show help and available commands
python use-cases/document-processing/doc_processor.py --help

# Test configuration
python use-cases/document-processing/doc_processor.py create-config
```

## Output Structure

```
output/mirror-doc-api/                      # Root output directory
├── Documentation/                # Documentation category
├── API/                # API documentation  
├── Guides/                # Guides documents
├── Other/                          # Other content
└── merged_documentation.md         # Combined documentation

use-cases/mirror-doc-api/                   # Use case configuration
├── config.json                     # Configuration file
└── README.md                       # This file
```

## Configuration Details

- **Max Workers**: 6 (configurable for performance)
- **Timeout**: 15 seconds per request
- **Delay**: 0.1 seconds between requests (respectful crawling)
- **Content Processing**: Uses readability algorithm for clean extraction
- **Output Format**: Markdown with metadata headers
- **Table of Contents**: Automatically generated

## Prerequisites

Make sure your server at https://storage.googleapis.com/mirror-api-docs/html/df/d6f/class_mirror_1_1_network_client.html is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
