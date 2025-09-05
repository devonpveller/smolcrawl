# Open Web Ui Docs Documentation Crawler

This use case is configured to crawl and process documentation from `https://docs.openwebui.com/`.

## Purpose

Extracts, processes, and merges web documentation from https://docs.openwebui.com/ into clean markdown collections.

## Configuration

- **Base URL**: `https://docs.openwebui.com/`
- **Output Directory**: `output/open-web-ui-docs/`
- **Merged Output**: `output/open-web-ui-docs/merged_documentation.md`
- **Categories**: Documentation, API, Guides, Other

## Usage

### Quick Start
```bash
# Discover all URLs automatically (recommended first step)
python use-cases/document-processing/doc_processor.py discover-urls --base-url https://docs.openwebui.com/ --save-urls use-cases/open-web-ui-docs/discovered_urls.txt

# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/open-web-ui-docs/config.json
```

### Step-by-Step Processing
```bash
# 1. Discover URLs (automatic crawling)
python use-cases/document-processing/doc_processor.py discover-urls --base-url https://docs.openwebui.com/ --save-urls use-cases/open-web-ui-docs/discovered_urls.txt

# 2. Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/open-web-ui-docs/config.json

# 3. Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/open-web-ui-docs/config.json
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
output/open-web-ui-docs/                      # Root output directory
├── Documentation/                # Documentation category
├── API/                # API documentation  
├── Guides/                # Guides documents
├── Other/                          # Other content
└── merged_documentation.md         # Combined documentation

use-cases/open-web-ui-docs/                   # Use case configuration
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

Make sure your server at https://docs.openwebui.com/ is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
