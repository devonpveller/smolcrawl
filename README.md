# SmolCrawl

A lightweight web crawler with **unified document processing tools** for extracting, converting, and merging web documentation into clean markdown collections.

## Overview

SmolCrawl has evolved into a comprehensive document processing toolkit centered around the **Universal Document Processor** (`doc_processor.py`). The project provides:

- **Unified Document Processing**: Extract, process, and merge web documentation with a single configurable tool
- **Multi-threaded Extraction**: High-performance content extraction with configurable worker threads
- **Intelligent Content Processing**: Uses readability algorithms to extract clean content from HTML
- **Flexible Configuration**: JSON and YAML configuration support for different documentation types
- **Category-based Organization**: Automatic categorization and organization of extracted documents
- **Comprehensive Merging**: Combine thousands of documents into single, well-organized files

Perfect for creating unified documentation from large API references, technical documentation sites, and knowledge bases.

## 🚀 Quick Start with Unified Tool

The project now centers around `doc_processor.py` - a powerful, configurable tool that replaces multiple specialized scripts:

```bash
# Create configuration
python doc_processor.py create-config

# Run complete processing pipeline
python doc_processor.py full-pipeline --config config.json
```

## Core Features

### Universal Document Processor (`doc_processor.py`)
- **Multi-mode Operation**: `extract`, `merge`, `full-pipeline`, `create-config`
- **High Performance**: Multi-threaded processing with real-time progress tracking
- **Flexible Input**: URL lists, configuration files, or command-line parameters
- **Smart Categorization**: Automatic document organization by category
- **Content Cleaning**: Intelligent content extraction and markdown conversion
- **Comprehensive Output**: Individual files plus merged documentation with table of contents

### Configuration Management
- **JSON Configuration**: Production-ready configuration files
- **YAML Support**: Human-readable configuration format
- **Template Generation**: Automatic configuration file creation
- **Parameterized Processing**: Customize categories, output formats, and processing options

### Testing & Migration
- **Test Suite**: Comprehensive validation of all functionality
- **Migration Utility**: Easy transition from older specialized scripts
- **Cross-platform**: Windows, Linux, macOS support

## Installation

### Dependencies
```bash
pip install requests readabilipy markdownify pyyaml
```

### Development Setup
```bash
# Clone the repository
git clone https://github.com/bllchmbrs/smolcrawl.git
cd smolcrawl

# Install dependencies
pip install -e .
```

## Requirements

- Python 3.7 or higher
- Dependencies: requests, readabilipy, markdownify, pyyaml

## Usage Examples

### Extract Documents from URLs
```bash
# Extract using configuration file
python doc_processor.py extract --config config_unreal.json

# Extract with command-line options
python doc_processor.py extract \
  --base-url "http://localhost:8080" \
  --urls-file "discovered_urls.txt" \
  --output-dir "output/docs" \
  --max-workers 8
```

### Merge Extracted Documents
```bash
# Merge using configuration
python doc_processor.py merge --config config_unreal.json

# Merge with custom options
python doc_processor.py merge \
  --input-dir "output/docs" \
  --merge-output "Complete_Documentation.md" \
  --title "Project Documentation"
```

### Complete Processing Pipeline
```bash
# Run extraction and merge in one command
python doc_processor.py full-pipeline --config config_unreal.json
```

### Configuration Management
```bash
# Create sample configuration
python doc_processor.py create-config

# Test configuration and functionality
python test_doc_processor.py

# Migrate from old specialized scripts
python migrate_to_doc_processor.py
```

## Configuration

### Sample Configuration (JSON)
```json
{
  "base_url": "http://localhost:8080",
  "url_list_file": "discovered_urls.txt",
  "max_workers": 6,
  "timeout": 15,
  "output_dir": "output/extracted_docs",
  "merge_output": "merged_documentation.md",
  "categories": ["Runtime", "Editor", "Plugins", "Other"],
  "category_order": ["Runtime", "Editor", "Plugins", "Other"],
  "clean_content": true,
  "add_metadata": true,
  "use_readability": true,
  "convert_to_markdown": true,
  "include_toc": true
}
```

### Sample Configuration (YAML)
```yaml
base_url: "http://localhost:8080"
url_list_file: "discovered_urls.txt"
max_workers: 6
output_dir: "output/extracted_docs"
merge_output: "merged_documentation.md"
categories:
  - "Runtime"
  - "Editor"
  - "Plugins"
  - "Other"
clean_content: true
convert_to_markdown: true
include_toc: true
```

### Environment Variables
- `STORAGE_PATH`: Path to store extracted data (default: `./output`)
- `CACHE_PATH`: Path for caching downloaded pages (default: `./smolcrawl-data/cache`)

## Project Structure

```
smolcrawl/
├── 🚀 CORE TOOLS
│   ├── doc_processor.py              # Universal document processor (22.8KB)
│   ├── test_doc_processor.py         # Comprehensive test suite (4.4KB)
│   └── migrate_to_doc_processor.py   # Migration utility (7.8KB)
│
├── ⚙️ CONFIGURATION
│   ├── config_unreal.json            # JSON config for Unreal Engine docs
│   ├── config_unreal.yaml            # YAML configuration example
│   └── doc_processor_config.json     # Sample configuration template
│
├── 📚 DOCUMENTATION
│   ├── DOC_PROCESSOR_README.md       # Complete usage guide (9.1KB)
│   ├── PROJECT_STATUS.md             # Current project overview
│   ├── UNIFICATION_COMPLETE.md       # Consolidation summary
│   └── README.md                     # This file
│
├── 🔧 UTILITIES
│   ├── check_cache.py                # Cache debugging utility
│   └── readabilipy_windows_fix.py    # Windows compatibility fix
│
├── 📦 ORIGINAL SMOLCRAWL
│   └── src/smolcrawl/               # Original SmolCrawl source code
│       ├── __init__.py              # CLI definitions
│       ├── crawl.py                 # Web crawling functionality
│       ├── db.py                    # Database operations
│       └── utils.py                 # Utility functions
│
└── 💾 DATA & OUTPUT
    ├── output/                      # Document processing output
    ├── smolcrawl-data/             # Cache and crawl data
    └── storage/                    # Request queues and metadata
```

## How the Unified Tool Works

1. **Configuration Loading**: Load processing parameters from JSON/YAML files or command-line arguments
2. **URL Processing**: Read URLs from files or configuration, with support for URL discovery and filtering
3. **Multi-threaded Extraction**: Process multiple URLs concurrently with configurable worker threads
4. **Content Processing**: 
   - Fetch HTML content from URLs
   - Extract readable content using readability algorithms
   - Convert to clean markdown format
   - Add metadata and categorization
5. **Organization**: Automatically categorize and organize documents by type (Runtime, Editor, Plugins, etc.)
6. **Progress Tracking**: Real-time progress updates with statistics and ETA
7. **Merging**: Combine individual documents into comprehensive, organized files with table of contents
8. **Output Generation**: Create both individual categorized files and merged documentation

## Performance & Statistics

The unified tool has been tested and proven with large-scale documentation processing:

- **Unreal Engine Documentation**: Successfully processed 3,995 URLs in 16.6 minutes
- **Processing Rate**: 4.0 URLs/second average with 6 worker threads
- **Success Rate**: 99.97% success rate on large documentation sets
- **Output**: Generated 13.83MB of clean, organized markdown documentation
- **Memory Efficient**: Handles thousands of documents without memory issues

## Responsible Processing

The document processor is a powerful tool for processing web documentation. Please use responsibly:

- **Check `robots.txt`**: Review site policies before processing large documentation sets
- **Respect Rate Limits**: Use appropriate delays between requests (`delay_between_requests` setting)
- **Minimize Server Impact**: Process during off-peak hours when possible
- **Scope Appropriately**: Only process the documentation you actually need
- **Local Processing Preferred**: Use local copies of documentation when available
- **Get Permission**: For commercial use or large-scale processing, consider seeking permission

The tool includes built-in rate limiting and respectful defaults, but responsible usage is ultimately up to the user.

## Migration from Specialized Scripts

If you were using the previous specialized scripts, migration is straightforward:

### Old Scripts → New Unified Tool
| Old Command | New Command |
|-------------|-------------|
| `python complete_extractor.py` | `python doc_processor.py extract --config config.json` |
| `python merge_unreal_docs.py` | `python doc_processor.py merge --config config.json` |
| `python batch_processor.py` | `python doc_processor.py full-pipeline --config config.json` |

### Migration Steps
1. **Run migration utility**: `python migrate_to_doc_processor.py`
2. **Review generated config**: Edit `migrated_config.json` as needed
3. **Test functionality**: `python test_doc_processor.py` 
4. **Execute unified tool**: `python doc_processor.py full-pipeline --config migrated_config.json`

## Original SmolCrawl Features

The original SmolCrawl crawler functionality is still available in the `src/smolcrawl/` directory:

```bash
# Original SmolCrawl usage (if needed)
python -m smolcrawl crawl https://example.com
python -m smolcrawl index https://example.com my_index
```

However, the **recommended approach** is to use the unified `doc_processor.py` tool for all new document processing tasks.

## Command Reference

### Universal Document Processor Commands
```bash
# Show help
python doc_processor.py --help

# Create configuration template
python doc_processor.py create-config

# Extract documents only
python doc_processor.py extract --config config.json

# Merge existing documents
python doc_processor.py merge --input-dir output/docs --merge-output final.md

# Complete pipeline (extract + merge)
python doc_processor.py full-pipeline --config config.json
```

### Testing & Validation
```bash
# Run comprehensive test suite
python test_doc_processor.py

# Check cache contents (debugging)
python check_cache.py

# Migration assistance
python migrate_to_doc_processor.py
```

## License

MIT

## Contributing

Contributions are welcome! SmolCrawl is an open-source project focused on powerful document processing tools.

### Development Setup
```bash
# Clone and set up development environment
git clone https://github.com/bllchmbrs/smolcrawl.git
cd smolcrawl
pip install -e .
pip install requests readabilipy markdownify pyyaml
```

### Testing
```bash
# Run the test suite
python test_doc_processor.py

# Test specific functionality
python doc_processor.py create-config
python doc_processor.py --help
```

### Areas for Contribution
- **Enhanced Processing**: Improve content extraction and markdown conversion
- **New Output Formats**: Add support for additional output formats
- **Performance Optimization**: Optimize multi-threading and memory usage  
- **Configuration**: Expand configuration options and validation
- **Documentation**: Improve guides, examples, and API documentation
- **Testing**: Increase test coverage and add integration tests
- **Cross-platform Support**: Ensure compatibility across operating systems

### Community & Support
- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and community engagement
- **Documentation**: Comprehensive guides in `DOC_PROCESSOR_README.md`

## Project Status

**Current State**: Production-ready unified document processing tool

### Recent Improvements
- ✅ **Consolidated**: Multiple specialized scripts unified into single tool
- ✅ **Tested**: Comprehensive test suite and validation
- ✅ **Documented**: Complete usage guides and examples  
- ✅ **Cleaned**: Streamlined project structure with obsolete files removed
- ✅ **Performance Proven**: Successfully processed 3,995+ documents

### Key Files
- **`doc_processor.py`** - Universal document processing tool (22.8KB)
- **`DOC_PROCESSOR_README.md`** - Complete usage documentation (9.1KB)
- **`config_unreal.json`** - Production configuration example
- **`test_doc_processor.py`** - Comprehensive test suite
- **`PROJECT_STATUS.md`** - Detailed project overview

The project has evolved from basic web crawling to a comprehensive, production-ready document processing toolkit suitable for large-scale documentation extraction and organization.

