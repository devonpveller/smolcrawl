# SmolCrawl AI Agent Instructions

## Architecture Overview

SmolCrawl is a **dual-architecture** document processing system:

1. **Original SmolCrawl** (`src/smolcrawl/`) - Traditional web crawler with Tantivy search indexing
2. **Document Processor** (`use-cases/document-processing/`) - Modern unified tool for large-scale HTML→Markdown conversion

The project has evolved from a simple web crawler into a **production document processing toolkit** optimized for technical documentation extraction.

## Core Data Flow

```
URLs → Crawling/Fetching → Content Extraction → Categorization → Output (Markdown/Search Index)
```

**Key Components:**
- `Page` objects (url, title, content, raw_html) are the central data structure
- Three indexer types: `TantivyIndexer` (search), `MarkdownFileIndexer` (files), `XmlFileIndexer` (single XML)
- Document processor uses `ProcessingConfig` dataclass for all configuration

## Use Case Architecture

The project is organized by **specific use cases** under `/use-cases/`:

- **`blueprint-api/`** - UE5.4 Blueprint API processing with Windows batch scripts
- **`document-processing/`** - Universal HTML→Markdown conversion (primary tool)
- **`unreal-docs/`** - Specialized Unreal Engine documentation merging

Each use case is **self-contained** with its own README, configs, and scripts.

## Critical Development Patterns

### Configuration Pattern
```python
# All document processing uses dataclass configs
@dataclass
class ProcessingConfig:
    base_url: str = "http://localhost:8080"
    max_workers: int = 6
    categories: List[str] = None
    # Supports both JSON and YAML loading
```

### Multi-threaded Processing Pattern
```python
# Use ThreadPoolExecutor with thread-safe counters
with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
    futures = [executor.submit(process_url, url) for url in urls]
    # Always use self.lock for shared state updates
```

### Content Extraction Pattern
```python
# readabilipy + markdownify is the standard pipeline
content = simple_json_from_html_string(html)['content']
markdown = markdownify.markdownify(content)
# Windows compatibility requires readabilipy_windows_fix import
```

### Categorization Pattern
```python
# URL-based categorization for Unreal/Technical docs
def categorize_url(self, url: str) -> str:
    if '/Runtime/' in url: return 'Runtime'
    if '/Editor/' in url: return 'Editor'
    # Categories are configurable via ProcessingConfig.categories
```

## Essential Commands

### Original SmolCrawl (CLI)
```bash
# Traditional crawling and search indexing
python -m smolcrawl crawl https://docs.unrealengine.com
python -m smolcrawl index https://docs.unrealengine.com unreal_docs
python -m smolcrawl query unreal_docs "blueprint components"
```

### Document Processor (Primary Tool)
```bash
# Modern document processing workflow
python use-cases/document-processing/doc_processor.py create-config
python use-cases/document-processing/doc_processor.py full-pipeline --config config.json

# Testing and validation
python tests/test_doc_processor.py
```

### Blueprint API Processing
```bash
# Specialized UE5.4 workflow
python use-cases/blueprint-api/discover_blueprint_urls_win.py
python use-cases/blueprint-api/blueprint_api_assistant.py
```

## Configuration System

**Dual format support:** All tools accept both JSON and YAML configs.

**Key config patterns:**
- `base_url` - Usually localhost for local documentation servers
- `categories` - List for auto-categorization (`["Runtime", "Editor", "Plugins", "Other"]`)
- `max_workers` - Threading (6-12 for local processing)
- `use_readability` - Content extraction method (almost always true)

## Testing Philosophy

- `tests/test_doc_processor.py` - Comprehensive validation of document processor
- Each use case includes example configs and validation scripts
- Tests verify config loading, URL processing, and content extraction
- Focus on **integration testing** rather than unit tests

## Windows Compatibility

Critical pattern: **All readabilipy usage requires Windows fix**
```python
# Always import this for Windows compatibility
import readabilipy_windows_fix
# Patches subprocess calls to use shell=True on Windows
```

## Performance Considerations

- **Local processing optimized:** High worker counts (12+) for localhost servers
- **Remote processing:** Lower workers (6) with delays (0.1s) for respectful crawling
- **Memory efficient:** Processes documents in streams, not batches
- **Progress tracking:** Real-time statistics with ETA calculations

## Output Patterns

1. **Individual categorized files** - Organized by URL structure
2. **Merged documentation** - Single comprehensive files with TOC
3. **Search indexes** - Tantivy full-text search databases

All output includes metadata headers with source URLs and generation timestamps.

## Integration Points

- **HTTP servers** - Often serves local documentation (localhost:8080/8081)
- **File systems** - Organized output directories with category-based structure
- **External tools** - Node.js for readabilipy, npm for dependencies
- **Cross-platform** - Windows batch files, Python for core logic

## Common Workflows

1. **Large documentation extraction:** Use document processor with high worker counts
2. **Search index creation:** Use original SmolCrawl CLI for queryable indexes  
3. **Blueprint API processing:** Specialized workflow with URL discovery and batch processing
4. **Configuration management:** Create templates, then customize for specific documentation sets

Always start with `create-config` for new processing tasks, and use `tests/` to validate functionality.
