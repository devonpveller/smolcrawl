# Test Usecase2 Documentation Crawler

This use case is configured to crawl and process documentation from `http://localhost:8080`.

## Purpose

Extracts, processes, and merges web documentation from http://localhost:8080 into clean markdown collections.

## Configuration

- **Base URL**: `http://localhost:8080`
- **Output Directory**: `output/test-usecase2/`
- **Merged Output**: `output/test-usecase2/merged_documentation.md`
- **Categories**: Documentation, API, Guides, Other

## Usage

### Quick Start
```bash
# Discover all URLs automatically (recommended first step)
python use-cases/document-processing/doc_processor.py discover-urls --base-url http://localhost:8080 --save-urls use-cases/test-usecase2/discovered_urls.txt

# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/test-usecase2/config.json
```

### Step-by-Step Processing
```bash
# 1. Discover URLs (automatic crawling)
python use-cases/document-processing/doc_processor.py discover-urls --base-url http://localhost:8080 --save-urls use-cases/test-usecase2/discovered_urls.txt

# 2. Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/test-usecase2/config.json

# 3. Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/test-usecase2/config.json
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
output/test-usecase2/                      # Root output directory
├── Documentation/                # Documentation category
├── API/                # API documentation  
├── Guides/                # Guides documents
├── Other/                          # Other content
└── merged_documentation.md         # Combined documentation

use-cases/test-usecase2/                   # Use case configuration
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

Make sure your server at http://localhost:8080 is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
