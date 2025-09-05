# Utilities

This directory contains utility scripts and debug tools for SmolCrawl development.

## Debug Scripts

- `debug_test.py` - General debugging utilities
- `debug_processor.py` - Document processor debugging
- `test_filename.py` - Filename testing utilities

## Usage

These are standalone utility scripts for debugging and development:

```bash
# Run debug tests
python utils/debug_test.py

# Debug processor functionality  
python utils/debug_processor.py

# Test filename utilities
python utils/test_filename.py
```

## Purpose

These utilities are modular test and debug tools that help with:
- Testing specific functionality in isolation
- Debugging document processing issues
- Validating file handling and naming
- Development and troubleshooting

For comprehensive testing, use the main test suite in the `tests/` directory.
