# Tests

This directory contains all test files for the smolcrawl framework.

## Test Files

- `test_doc_processor.py` - Tests for the document processor functionality
- `test_http_server.py` - Tests for HTTP server components
- `test_manual_crawl.py` - Tests for manual crawling features
- `test_readability.py` - Tests for readability extraction
- `test_merge/` - Directory containing merge operation tests

## Running Tests

To run all tests:
```bash
python -m pytest tests/
```

To run specific test files:
```bash
python tests/test_doc_processor.py
python tests/test_http_server.py
```

## Test Structure

Tests are organized to cover:
- Core framework functionality
- Document processing features
- HTTP server operations
- Content extraction and readability
- Merge operations for documentation

## Test Data

The `test_merge/` directory contains test data and fixtures used for testing merge operations and document processing workflows.
