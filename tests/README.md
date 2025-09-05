# Tests

This directory contains all test files for the smolcrawl framework.

## Test Files

- `test_doc_processor.py` - Tests for the document processor functionality
- `test_http_server.py` - Tests for HTTP server components
- `test_manual_crawl.py` - Tests for manual crawling features
- `test_readability.py` - Tests for readability extraction
- `test_merge/` - Directory containing merge operation tests
- `localhost-test_urls.txt` - Test URLs for localhost:1313 testing
- `localhost-test_urls_temp.txt` - Temporary test URLs
- Various other test URL files for different test scenarios

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

## Test with Sample URLs

```bash
# Test with a small set of URLs
python use-cases/document-processing/doc_processor.py extract --urls-file tests/localhost-test_urls.txt --output-dir tests/output --server-intensity 0.3
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

Test files are organized by source:
- `localhost-*` - Files for testing localhost servers
- `docker-*` - Files for testing Docker documentation  
- Other prefixed files for specific test scenarios
