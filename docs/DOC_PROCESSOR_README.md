# Universal Document Processing Tool

A unified, configurable tool for extracting, processing, and merging web documentation. This tool combines the functionality of multiple specialized scripts into a single, parameterized solution.

## Features

- **Multi-threaded extraction** with configurable worker count
- **Flexible source handling** (URL lists, start URLs, configuration files)
- **Content processing** with readability extraction and markdown conversion
- **Categorization and organization** with customizable categories
- **Document merging** with table of contents generation
- **Multiple configuration formats** (JSON, YAML)
- **Progress tracking** and detailed statistics
- **Error handling** with retry logic

## Installation

```bash
pip install requests readabilipy markdownify pyyaml
```

For Windows users, you may need the readabilipy Windows fix included in this project.

## Quick Start

### 1. Create Configuration File
```bash
python doc_processor.py create-config
```

### 2. Extract Documents
```bash
# Using configuration file
python doc_processor.py extract --config config_unreal.json

# Using command line arguments
python doc_processor.py extract --urls-file discovered_urls.txt --output-dir output/docs --max-workers 8
```

### 3. Merge Documents
```bash
# Merge extracted documents
python doc_processor.py merge --input-dir output/docs --merge-output final_documentation.md

# Using configuration
python doc_processor.py merge --config config_unreal.json
```

### 4. Full Pipeline
```bash
# Run complete extraction and merge pipeline
python doc_processor.py full-pipeline --config config_unreal.json
```

## Configuration

### Configuration File Format (JSON)
```json
{
  "base_url": "http://localhost:8080",
  "url_list_file": "discovered_urls.txt",
  "max_workers": 6,
  "timeout": 15,
  "output_dir": "output/extracted_docs",
  "merge_output": "merged_documentation.md",
  "categories": ["Other", "Runtime", "Editor", "Plugins"],
  "category_order": ["Runtime", "Editor", "Plugins", "Other"],
  "clean_content": true,
  "add_metadata": true,
  "use_readability": true,
  "convert_to_markdown": true,
  "include_toc": true
}
```

### Configuration File Format (YAML)
```yaml
base_url: "http://localhost:8080"
url_list_file: "discovered_urls.txt"
max_workers: 6
timeout: 15
output_dir: "output/extracted_docs"
merge_output: "merged_documentation.md"
categories:
  - "Other"
  - "Runtime" 
  - "Editor"
  - "Plugins"
category_order:
  - "Runtime"
  - "Editor"
  - "Plugins"
  - "Other"
clean_content: true
add_metadata: true
use_readability: true
convert_to_markdown: true
include_toc: true
```

## Command Reference

### Extract Command
Extract documents from URLs with multi-threading:
```bash
python doc_processor.py extract [options]

Options:
  --config, -c          Configuration file (JSON or YAML)
  --base-url           Base URL for extraction (default: http://localhost:8080)
  --urls-file          File containing URLs to process
  --output-dir         Output directory (default: output/extracted_docs)
  --max-workers        Number of worker threads (default: 6)
```

### Merge Command
Merge extracted documents into single file:
```bash
python doc_processor.py merge [options]

Options:
  --config, -c         Configuration file
  --input-dir          Input directory containing extracted docs
  --merge-output       Output file for merged content
  --title              Title for merged document
  --no-toc             Skip table of contents generation
  --no-clean           Skip content cleaning
```

### Full Pipeline Command
Run complete extraction and merge process:
```bash
python doc_processor.py full-pipeline [options]

Options:
  --config, -c         Configuration file (recommended)
  [All extract and merge options also available]
```

## Usage Examples

### Example 1: Unreal Engine Documentation
```bash
# Create Unreal-specific config
cat > unreal_config.json << EOF
{
  "base_url": "http://localhost:8080",
  "url_list_file": "discovered_urls.txt",
  "max_workers": 8,
  "output_dir": "output/unreal_docs",
  "merge_output": "UnrealEngine_Complete_Documentation.md",
  "categories": ["Runtime", "Editor", "Plugins", "Other"],
  "category_order": ["Runtime", "Editor", "Plugins", "Other"]
}
EOF

# Run full pipeline
python doc_processor.py full-pipeline --config unreal_config.json
```

### Example 2: Custom Documentation Project
```bash
# Direct command line usage
python doc_processor.py extract \
  --base-url "https://docs.example.com" \
  --urls-file "my_urls.txt" \
  --output-dir "output/my_docs" \
  --max-workers 4

python doc_processor.py merge \
  --input-dir "output/my_docs" \
  --merge-output "my_complete_docs.md" \
  --title "My Project Documentation"
```

### Example 3: Processing Different Document Types
```bash
# API documentation
cat > api_config.json << EOF
{
  "base_url": "https://api.example.com",
  "categories": ["Authentication", "Endpoints", "Examples", "Other"],
  "output_dir": "output/api_docs",
  "merge_output": "API_Documentation.md"
}
EOF

# Technical manuals  
cat > manual_config.json << EOF
{
  "base_url": "https://manual.example.com",
  "categories": ["Installation", "Configuration", "Usage", "Troubleshooting"],
  "output_dir": "output/manual_docs", 
  "merge_output": "User_Manual.md"
}
EOF
```

## Configuration Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `base_url` | string | `"http://localhost:8080"` | Base URL for document extraction |
| `url_list_file` | string | `null` | File containing URLs to process |
| `start_urls` | array | `null` | List of starting URLs |
| `max_workers` | integer | `6` | Number of concurrent worker threads |
| `max_retries` | integer | `3` | Maximum retry attempts for failed requests |
| `timeout` | integer | `15` | Request timeout in seconds |
| `delay_between_requests` | float | `0.1` | Delay between requests in seconds |
| `output_dir` | string | `"output/extracted_docs"` | Directory for extracted documents |
| `merge_output` | string | `"merged_documentation.md"` | Filename for merged output |
| `categories` | array | `["Other", "Runtime", "Editor", "Plugins"]` | Available document categories |
| `category_order` | array | same as categories | Order for organizing merged content |
| `clean_content` | boolean | `true` | Enable content cleaning and standardization |
| `add_metadata` | boolean | `true` | Add metadata headers to documents |
| `use_readability` | boolean | `true` | Use readability extraction for content |
| `convert_to_markdown` | boolean | `true` | Convert HTML content to Markdown |
| `include_toc` | boolean | `true` | Include table of contents in merged output |

## Migrating from Specialized Scripts

### From complete_extractor.py
```bash
# Old way
python complete_extractor.py

# New way  
python doc_processor.py extract --config config.json
```

### From merge_unreal_docs.py
```bash
# Old way
python merge_unreal_docs.py

# New way
python doc_processor.py merge --config config.json
```

### From batch_processor.py
```bash
# Old way
python batch_processor.py

# New way (equivalent functionality)
python doc_processor.py full-pipeline --config config.json
```

## Output Structure

```
output/
├── extracted_docs/
│   ├── Runtime/
│   │   ├── document1.md
│   │   └── document2.md
│   ├── Editor/
│   │   └── document3.md
│   └── Other/
│       └── document4.md
└── merged_documentation.md
```

## Error Handling

The tool includes comprehensive error handling:
- **Network errors**: Automatic retry with exponential backoff
- **Content extraction failures**: Graceful degradation with error logging
- **File system errors**: Safe directory creation and file writing
- **Configuration errors**: Clear validation messages

## Performance Tips

1. **Adjust worker count**: Increase `max_workers` for faster processing, but respect server limits
2. **Optimize delays**: Reduce `delay_between_requests` for local servers, increase for remote
3. **Use local servers**: Process local documentation copies when possible
4. **Configure categories**: Proper categorization improves organization and processing speed

## Troubleshooting

### Common Issues

1. **Import errors**: Install missing dependencies with pip
2. **Timeout errors**: Increase `timeout` value in configuration
3. **Memory issues**: Reduce `max_workers` for large document sets
4. **Permission errors**: Check file system permissions for output directory

### Debug Mode
Add verbose logging by modifying the script to include:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

This tool is part of the SmolCrawl project and inherits its licensing terms.
