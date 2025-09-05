# Localhost:1313 Documentation Crawler

This use case is configured to crawl and process documentation from a local server running on `http://localhost:1313`.

## Purpose

Extracts, processes, and merges web documentation from localhost:1313 into clean markdown collections.

## Configuration

- **Base URL**: `http://localhost:1313`
- **Output Directory**: `output/localhost-1313/`
- **Merged Output**: `output/localhost-1313/merged_documentation.md`
- **Categories**: Documentation, API, Guides, Other

## Usage

### Quick Start
```bash
# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/localhost-1313/config.json
```

### Step-by-Step Processing
```bash
# Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/localhost-1313/config.json

# Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/localhost-1313/config.json
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
output/localhost-1313/                # Root output directory
├── Documentation/                   # Documentation category
├── API/                            # API documentation  
├── Guides/                         # Guide documents
├── Other/                          # Uncategorized content
└── merged_documentation.md         # Combined documentation

use-cases/localhost-1313/           # Use case configuration
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

Make sure your localhost:1313 server is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
