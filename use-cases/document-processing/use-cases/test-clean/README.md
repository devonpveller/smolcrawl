# Test Clean Documentation Crawler

This use case is configured to crawl and process documentation from `http://example.com`.

## Purpose

Extracts, processes, and merges web documentation from http://example.com into clean markdown collections.

## Configuration

- **Base URL**: `http://example.com`
- **Output Directory**: `output/test-clean/`
- **Merged Output**: `output/test-clean/merged_documentation.md`
- **Categories**: Documentation, API, Guides, Other

## Usage

### Quick Start
```bash
# Discover all URLs automatically (recommended first step)
python use-cases/document-processing/doc_processor.py discover-urls --base-url http://example.com --save-urls use-cases/test-clean/discovered_urls.txt

# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/test-clean/config.json
```

### Step-by-Step Processing
```bash
# 1. Discover URLs (automatic crawling)
python use-cases/document-processing/doc_processor.py discover-urls --base-url http://example.com --save-urls use-cases/test-clean/discovered_urls.txt

# 2. Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/test-clean/config.json

# 3. Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/test-clean/config.json
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
output/test-clean/                      # Root output directory
├── Documentation/                # Documentation category
├── API/                # API documentation  
├── Guides/                # Guides documents
├── Other/                          # Other content
└── merged_documentation.md         # Combined documentation

use-cases/test-clean/                   # Use case configuration
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

Make sure your server at http://example.com is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
