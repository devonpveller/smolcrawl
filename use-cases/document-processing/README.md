# Document Processing Use Case

This directory contains tools and utilities for general document processing, HTML to Markdown conversion, and web crawling tasks.

## Files

### Core Document Processor
- `doc_processor.py` - Main unified document processing engine
- `doc_processor_config.json` - Configuration file for document processor

### Batch Processing
- `batch_processor.py` - Processes multiple documents in batches
- `complete_extractor.py` - Complete extraction pipeline for documents

### URL and Content Extraction
- `extract_urls.py` - Extracts URLs from documents and websites
- `migrate_to_doc_processor.py` - Migration utility for updating to new processor

### Monitoring and Progress
- `monitor_progress.py` - General progress monitoring for document processing

### Utilities
- `readabilipy_windows_fix.py` - Windows compatibility fixes for readabilipy
- `check_cache.py` - Cache checking and validation utility
- `examine_cache.py` - Cache examination and analysis tool
- `cleanup_project.py` - Project cleanup and maintenance utility

## Features

- **Multi-threaded processing** - Efficient processing of large document sets
- **HTML to Markdown conversion** - Clean, structured markdown output
- **Configurable extraction** - Customizable content extraction rules
- **Progress monitoring** - Real-time processing status and statistics
- **Caching system** - Intelligent caching to avoid duplicate processing
- **Cross-platform support** - Works on Windows, macOS, and Linux

## Usage

1. Configure `doc_processor_config.json` for your specific use case
2. Run `doc_processor.py` with appropriate parameters
3. Monitor progress with `monitor_progress.py`
4. Use utility scripts for maintenance and analysis

## Configuration

The document processor supports various configuration options including:
- Worker thread count
- Processing delays
- Output formatting
- Content categorization
- Cache settings
