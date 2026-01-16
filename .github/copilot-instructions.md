# SmolCrawl AI Agent Instructions

## Quick Start for AI Agents

**Primary Tool**: [use-cases/document-processing/doc_processor.py](use-cases/document-processing/doc_processor.py) - Universal HTML→Markdown processor with server intensity control.

**Easiest Entry Point**: [smolcrawl.bat](smolcrawl.bat) - Interactive batch file for non-technical users (Windows). Just run it and answer prompts.

**Key Commands**:
```bash
# Interactive batch workflow (Windows)
smolcrawl.bat

# Create new use case structure
python doc_processor.py create-use-case --name my-docs --base-url http://localhost:8080

# Full processing pipeline with intensity control (0.0=gentle, 1.0=aggressive)
python doc_processor.py full-pipeline --config config.json --server-intensity 0.3

# Extract, merge, or discover URLs individually
python doc_processor.py extract --config config.json
python doc_processor.py merge --input-dir output/docs --output merged.md
python doc_processor.py discover-urls --config config.json
```

**Initial Setup** (required once):
```bash
# Windows: Run setup script first
.\scripts\setup.ps1

# Linux/macOS:
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Manual: Verify Python 3.11+, Node.js, then install
pip install -e .
npm install  # Critical: Required for readabilipy content extraction
```

## Architecture Overview

SmolCrawl is a **lightweight web crawler** with unified document processing:

1. **SmolCrawler** (`src/smolcrawl/crawl.py`) - Async web crawler using httpx + BeautifulSoup (no heavy dependencies)
2. **Document Processor** (`use-cases/document-processing/`) - PRIMARY: Unified HTML→Markdown tool for bulk extraction
3. **Use Case Framework** (`use-cases/*/`) - Specialized workflows (Unreal Engine, Blueprint API, Docker docs, etc.)
4. **TantivyIndexer** (`src/smolcrawl/db.py`) - Optional full-text search indexing (install with `pip install smolcrawl[full]`)
5. **Cache System** (`smolcrawl-data/cache/`) - diskcache-based HTTP response caching to avoid re-fetching

**Critical Dependencies:**
- **Node.js + npm**: Required for readabilipy content extraction (runs JavaScript DOM parser)
- **package.json**: Defines readabilipy's Node.js dependencies
- **readabilipy_windows_fix**: Patches subprocess calls on Windows (uses `shell=True`)
- **diskcache**: Persistent caching at `smolcrawl-data/cache/crawl/`

## SOLID Principles & Coding Standards

### 1. Single Responsibility Principle (SRP)
**Each class should have only one reason to change.**

**✅ Current Implementation:**
- `TantivyIndexer` - Handles only Tantivy search indexing
- `MarkdownFileIndexer` - Handles only Markdown file creation
- `DocumentProcessor` - Handles only document processing workflows
- `Page` and `Section` - Handle only data modeling

**🎯 Enforcement Rules:**
- Keep classes focused on single domain concepts
- Separate data models (`Page`, `Section`) from business logic (`Indexer` classes)
- Extract utilities into dedicated modules (`utils.py`)
- Use composition over inheritance for complex behaviors

### 2. Open/Closed Principle (OCP)
**Classes should be open for extension, closed for modification.**

**✅ Current Implementation:**
- Abstract indexer pattern allows new indexer types (`TantivyIndexer`, `MarkdownFileIndexer`, `XmlFileIndexer`)
- Configuration dataclasses support extension without modifying core logic
- Plugin-style use case architecture under `/use-cases/`

**🎯 Enforcement Rules:**
- Use Protocol classes for interface definition
- Implement strategy pattern for processing variations
- Leverage dataclass inheritance for configuration extension
- Design indexers as pluggable components

### 3. Liskov Substitution Principle (LSP)
**Subtypes must be substitutable for their base types.**

**✅ Current Implementation:**
- All indexer classes implement the same interface (`add_pages`, `add_page`)
- Configuration dataclasses maintain consistent behavior across inheritance

**🎯 Enforcement Rules:**
- Ensure all indexer implementations handle `Page` objects identically
- Maintain consistent error handling across all implementations
- Preserve expected behavior in configuration inheritance

### 4. Interface Segregation Principle (ISP)
**Clients should not depend on interfaces they don't use.**

**✅ Current Implementation:**
- Focused indexer interfaces (no unnecessary methods)
- Separate CLI commands for different operations (`crawl`, `index`, `query`)
- Modular configuration with optional fields

**🎯 Enforcement Rules:**
- Keep indexer interfaces minimal and focused
- Use Protocol classes to define specific interface contracts
- Avoid monolithic configuration objects - use composition
- Separate read and write operations when appropriate

### 5. Dependency Inversion Principle (DIP)
**Depend on abstractions, not concretions.**

**✅ Current Implementation:**
- CLI layer depends on indexer abstractions, not concrete implementations
- Configuration injection pattern in `DocumentProcessor`
- External dependencies properly abstracted (Tantivy, readabilipy)

**🎯 Enforcement Rules:**
- Inject configuration objects rather than hardcoding values
- Use factory patterns for indexer creation
- Abstract external API dependencies behind wrapper classes
- Depend on Pydantic BaseModel abstractions, not dict structures

## Encapsulation & Data Protection

### Core Encapsulation Patterns

**🔒 Data Model Encapsulation (Pydantic BaseModel)**
```python
class Page(BaseModel):
    url: str
    title: str 
    content: str
    raw_html: str
    
    def __hash__(self) -> int:
        return hash(self.url)
    
    def get_sections(self) -> List[Section]:
        # Encapsulated section extraction logic
        pass
```

**🔒 Configuration Encapsulation (Dataclass)**
```python
@dataclass
class ProcessingConfig:
    base_url: str = "http://localhost:8080"
    max_workers: int = 6
    
    def __post_init__(self):
        # Encapsulated validation and defaults
        if self.categories is None:
            self.categories = ['Other', 'Runtime', 'Editor', 'Plugins']
```

**🔒 Thread-Safe State Encapsulation**
```python
class DocumentProcessor:
    def __init__(self, config: ProcessingConfig):
        self.lock = threading.Lock()  # Protect shared state
        self.processed_count = 0
        self.failed_count = 0
    
    def _update_counters(self):  # Private method
        with self.lock:
            self.processed_count += 1
```

### Encapsulation Rules

1. **Private Methods**: Use single underscore `_private_method()` for internal operations
2. **Protected State**: All mutable shared state must be protected by locks
3. **Immutable Data**: Prefer dataclasses and Pydantic models for data transfer
4. **Controlled Access**: Expose behavior through public methods, hide implementation
5. **Validation**: Encapsulate validation logic within `__post_init__()` and property setters

## Naming Conventions & Code Style

### File and Module Naming
- **Files**: `snake_case.py` (e.g., `doc_processor.py`, `blueprint_api_assistant.py`)
- **Modules**: `snake_case` package names (e.g., `smolcrawl`, `use_cases`)
- **Test Files**: `test_*.py` prefix (e.g., `test_doc_processor.py`)
- **Config Files**: Descriptive names with format extension (e.g., `ue_config.json`, `blueprint_config.yaml`)

### Class and Function Naming
- **Classes**: `PascalCase` (e.g., `DocumentProcessor`, `TantivyIndexer`, `ProcessingConfig`)
- **Functions/Methods**: `snake_case` (e.g., `crawl_target()`, `clean_filename()`, `get_sections()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DB_PATH`, `DEFAULT_TIMEOUT`)
- **Private Methods**: `_private_method()` with single underscore prefix
- **Magic Methods**: Double underscore when implementing protocols (`__hash__`, `__post_init__`)

### Variable Naming
- **Local Variables**: `snake_case` descriptive names (e.g., `crawl_results`, `html_content`)
- **Class Attributes**: `snake_case` (e.g., `self.output_dir`, `self.processed_count`)
- **Configuration Keys**: `snake_case` matching dataclass fields (e.g., `max_workers`, `base_url`)
- **Thread Objects**: Descriptive names (e.g., `self.lock`, `processing_thread`)

### Meaningful Names Rules
1. **Descriptive over Concise**: `processed_count` not `count`, `clean_filename()` not `clean()`
2. **Domain-Specific Terms**: Use `crawl`, `index`, `extract` consistently throughout codebase
3. **Avoid Abbreviations**: `maximum_workers` over `max_wrkrs`, `configuration` over `cfg`
4. **Boolean Prefixes**: `is_`, `has_`, `can_`, `should_` (e.g., `use_readability`, `add_metadata`)
5. **Collection Naming**: Plural for containers (e.g., `crawl_results`, `html_files`, `categories`)

## Framework Integration Standards

### Pydantic BaseModel Standards
```python
# ✅ Correct: Type hints, validation, immutable data
class Page(BaseModel):
    url: str
    title: str
    content: str
    raw_html: str
    
    class Config:
        frozen = True  # Immutable data models

# ❌ Avoid: Mutable dict-based data structures
page_data = {"url": url, "title": title}  # Use Pydantic instead
```

### Typer CLI Standards
```python
# ✅ Correct: Type hints, clear help text, argument validation
@app.command()
def crawl(target_url: str = typer.Argument(..., help="The URL to crawl.")) -> List[Page]:
    """Crawls a target URL and returns the extracted pages."""
    logger.info(f"Crawling {target_url}")
    # Implementation...

# ❌ Avoid: Untyped arguments, missing help text
@app.command()
def crawl(target_url):
    # Implementation...
```

### Threading Standards (ThreadPoolExecutor)
```python
# ✅ Correct: Context manager, error handling, thread-safe operations
with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
    futures = [executor.submit(process_url, url) for url in urls]
    for future in as_completed(futures):
        try:
            result = future.result()
            with self.lock:  # Thread-safe state updates
                self.processed_count += 1
        except Exception as e:
            logger.error(f"Processing failed: {e}")

# ❌ Avoid: Manual thread management, unprotected shared state
```

### Configuration Management Standards
```python
# ✅ Correct: Dataclass with defaults, validation, dual format support
@dataclass
class ProcessingConfig:
    base_url: str = "http://localhost:8080"
    max_workers: int = 6
    
    @classmethod
    def from_file(cls, path: str) -> 'ProcessingConfig':
        """Support both JSON and YAML"""
        with open(path) as f:
            if path.endswith(('.yml', '.yaml')):
                return cls(**yaml.safe_load(f))
            return cls(**json.load(f))

# ❌ Avoid: Hardcoded values, single format support
```

## Industry Framework Standards

### Python Best Practices
1. **Type Hints**: All public methods must have complete type annotations
2. **Docstrings**: Google-style docstrings for all classes and public methods
3. **Error Handling**: Specific exception types, proper logging with loguru
4. **Resource Management**: Context managers for files, connections, thread pools
5. **Import Organization**: Standard library, third-party, local imports (separated by blank lines)

### Async/Threading Patterns
1. **Thread Safety**: All shared state protected by appropriate synchronization primitives
2. **Resource Limits**: Use `max_workers` configuration to prevent resource exhaustion
3. **Graceful Degradation**: Handle external service failures with retries and fallbacks
4. **Progress Tracking**: Thread-safe counters for long-running operations

### Data Processing Patterns
1. **Immutable Data Models**: Use Pydantic BaseModel with `frozen=True` for data transfer
2. **Configuration Injection**: Dependency injection for all configurable behavior
3. **Stream Processing**: Handle large datasets without loading everything into memory
4. **Validation**: Input validation at system boundaries (CLI args, config files, web responses)

### External Dependencies
1. **Graceful Imports**: Handle missing optional dependencies with try/except and clear error messages
2. **Version Compatibility**: Use compatible API patterns across dependency versions
3. **Abstraction Layers**: Wrap external APIs behind internal interfaces for easier testing/mocking

## Core Data Structures

### Central Data Model: `Page` (Pydantic BaseModel)
Located in [src/smolcrawl/db.py](src/smolcrawl/db.py):
```python
class Page(BaseModel):
    url: str                    # Source URL
    title: str                  # Page title (from HTML <title>)
    content: str                # Markdown-converted main content
    raw_html: str               # Original HTML (for re-extraction)
    
    def __hash__(self) -> int:
        return hash(self.url)   # Enables set deduplication
    
    def get_sections(self) -> List[Section]:
        # Extracts sections from markdown headers (## format)
        pass
```

**Key Pattern**: `Page` objects are the central currency between:
- Crawling → Page extraction → Content processors → Indexers
- All components pass `List[Page]` for batch operations

### Configuration Pattern: `ProcessingConfig` (Dataclass)
Located in [use-cases/document-processing/doc_processor.py](use-cases/document-processing/doc_processor.py):
- **Server Intensity Control** (0.0-1.0): Auto-adjusts workers, delays, timeouts
  - Low (0.0): 1 worker, 2.0s delay, 30s timeout, 5 retries → gentle crawling
  - High (1.0): 12 workers, 0.0s delay, 10s timeout, 2 retries → aggressive
- **Dual Format**: Load from `.json` OR `.yaml` files
- **Auto-Validation**: `__post_init__()` sets category defaults and applies intensity

## Use Case Architecture & Workflows

The project is organized by **specific use cases** under [use-cases/](use-cases/):

1. **`document-processing/`** (PRIMARY) - Universal HTML→Markdown with server intensity control
   - Single entry point: `doc_processor.py` for all document extraction
   - Supports: `extract`, `merge`, `full-pipeline`, `create-config`, `create-use-case`, `discover-urls`
   
2. **`blueprint-api/`** - Specialized UE5.4 API processing
   - [blueprint_api_assistant.py](use-cases/blueprint-api/blueprint_api_assistant.py) - Windows batch integration
   - URL discovery and categorization for Blueprint API docs
   
3. **`unreal-docs/`** - Unreal Engine documentation merging
   - Inherits from document processor patterns
   
4. **`docker-docs/`, `mirror-doc/`, `open-web-ui-docs/`, etc.** - Past processing instances
   - Each has example configs and README showing processing patterns

**Pattern**: Each use case contains:
- `config.json` or `config.yaml` - Processing configuration
- README explaining the workflow and URL sources
- Output directory with categorized markdown files
- `*_merged.md` for consolidated documentation

## Critical Development Patterns

### Server Intensity Pattern (Key Innovation)
```python
# In ProcessingConfig.__post_init__():
self.server_intensity = 0.5  # 0.0 (gentle) to 1.0 (aggressive)
self._apply_server_intensity()  # Auto-calculates workers, delays, timeouts

# Auto-calculation formula:
# max_workers = 1 + (intensity * 11)           # 1-12 workers
# delay = (1.0 - intensity) * 2.0              # 2.0s to 0.0s  
# timeout = 30 - (intensity * 20)              # 30s to 10s
# retries = 5 - (intensity * 3)                # 5 to 2 retries

# Usage: Command-line override
python doc_processor.py full-pipeline --config config.json --server-intensity 0.3
```
This is the key innovation for respecting server load while maximizing throughput.

### Configuration Pattern
```python
# All document processing uses dataclass configs
@dataclass
class ProcessingConfig:
    base_url: str = "http://localhost:8080"
    max_workers: int = 6
    categories: List[str] = None
    server_intensity: float = 0.5
    # Supports both JSON and YAML loading via from_config_file()
```

### Multi-threaded Processing Pattern
```python
# Use ThreadPoolExecutor with thread-safe counters
with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
    futures = [executor.submit(process_url, url) for url in urls]
    for future in as_completed(futures):
        try:
            result = future.result()
            with self.lock:  # Thread-safe state updates
                self.processed_count += 1
        except Exception as e:
            logger.error(f"Processing failed: {e}")
```

### Content Extraction Pattern
```python
# readabilipy + markdownify is the standard pipeline
from readabilipy import simple_json_from_html_string
import markdownify

content = simple_json_from_html_string(html)['content']
markdown = markdownify.markdownify(content)
# CRITICAL: Windows compatibility requires import readabilipy_windows_fix
```

### Categorization Pattern
```python
# URL-based categorization for Unreal/Technical docs
def categorize_url(self, url: str) -> str:
    if '/Runtime/' in url: return 'Runtime'
    if '/Editor/' in url: return 'Editor'
    if '/Plugins/' in url: return 'Plugins'
    return 'Other'
    # Categories are fully configurable via ProcessingConfig.categories
```

### Cache System Pattern
```python
# HTTP response caching with diskcache (in src/smolcrawl/utils.py)
from diskcache import Cache

def get_cache() -> Cache:
    cache_dir = os.path.join(get_storage_path(), 'cache', 'crawl')
    return Cache(cache_dir)

# Usage in crawler - automatic caching of all HTTP responses
cache = get_cache()
cache_key = f"crawl:{url}"
if cache_key in cache:
    html = cache[cache_key]
else:
    response = await client.get(url)
    html = response.text
    cache[cache_key] = html

# Cache utilities
python use-cases/document-processing/check_cache.py    # Validate cache
python use-cases/document-processing/examine_cache.py  # Inspect cached entries
```

**Cache Benefits:**
- Avoids re-fetching same URLs during development/testing
- Speeds up repeated processing runs significantly
- Persistent across Python sessions (disk-based)
- Location: `smolcrawl-data/cache/crawl/`

## Essential Commands

### Document Processor (Primary Tool)
```bash
# Create configuration file (interactive wizard)
python use-cases/document-processing/doc_processor.py create-config

# Create organized use case folder structure
python use-cases/document-processing/doc_processor.py create-use-case --name my-docs --base-url http://localhost:8080

# Full processing pipeline with intensity control
python use-cases/document-processing/doc_processor.py full-pipeline --config config.json --server-intensity 0.5

# Individual operations
python use-cases/document-processing/doc_processor.py extract --config config.json
python use-cases/document-processing/doc_processor.py merge --input-dir output/docs --output merged.md
python use-cases/document-processing/doc_processor.py discover-urls --config config.json --output urls.txt

# Run tests to validate setup
python tests/test_doc_processor.py
```

### Original SmolCrawl CLI (Legacy - for search indexing)
```bash
# Traditional crawling and Tantivy search indexing
python -m smolcrawl crawl https://docs.unrealengine.com
python -m smolcrawl index https://docs.unrealengine.com unreal_docs
python -m smolcrawl query unreal_docs "blueprint components"
```

### Blueprint API Processing (Specialized)
```bash
# Unreal Engine 5.4 API-specific workflows
python use-cases/blueprint-api/discover_blueprint_urls_win.py
python use-cases/blueprint-api/blueprint_api_assistant.py
```

### Development & Testing
```bash
# Test configuration loading and URL processing
python tests/test_doc_processor.py

# Test readability extraction
python tests/test_readability.py

# Manual crawl validation
python tests/test_manual_crawl.py
```

## Configuration System

**Dual format support:** All tools accept both JSON and YAML configs.

**Key config patterns:**
- `base_url` - Usually localhost for local documentation servers
- `categories` - List for auto-categorization (`["Runtime", "Editor", "Plugins", "Other"]`)
- `max_workers` - Threading (6-12 for local processing)
- `use_readability` - Content extraction method (almost always true)

## Package Structure & Entry Points

**Project layout:**
```
src/smolcrawl/          # Core library (installable package)
  ├── crawl.py          # Async crawler with httpx + BeautifulSoup
  ├── db.py             # Page model, indexers (Tantivy, Markdown, XML)
  └── utils.py          # Storage paths, cache management

use-cases/              # Specialized workflows & examples
  └── document-processing/  # PRIMARY tool (doc_processor.py)

smolcrawl-data/         # Runtime data (auto-created)
  ├── cache/crawl/      # HTTP response cache (diskcache)
  ├── markdown_files/   # Markdown indexer output
  └── db/               # Tantivy search indexes

smolcrawl.bat           # Windows batch interface
scripts/                # Setup automation
pyproject.toml          # Package definition with CLI entry point
package.json            # Node.js dependencies for readabilipy
```

**CLI Entry Points:**
```bash
# Legacy CLI (defined in pyproject.toml [project.scripts])
python -m smolcrawl crawl <url>   # OR: smolcrawl crawl <url> (if installed)

# Modern workflow (document processor)
python use-cases/document-processing/doc_processor.py <command>

# Batch interface (Windows)
smolcrawl.bat   # Interactive prompts for all parameters
```

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

**Why this matters:**
- readabilipy calls Node.js via subprocess
- Windows requires `shell=True` for npm/node commands
- Without fix: "FileNotFoundError: [WinError 2] The system cannot find the file specified"
- Fix location: [use-cases/document-processing/readabilipy_windows_fix.py](use-cases/document-processing/readabilipy_windows_fix.py)

**Implementation Pattern:**
```python
# In crawl.py and doc_processor.py
if platform.system() == 'Windows':
    import subprocess
    import readabilipy.utils
    
    def _patched_have_npm():
        subprocess.run(["npm", "version"], shell=True, ...)  # shell=True is key
    
    # Monkey-patch the readabilipy functions
    readabilipy.utils.have_npm = _patched_have_npm
```

**Seen in**: [src/smolcrawl/crawl.py](src/smolcrawl/crawl.py) (lines 25-80), [use-cases/document-processing/doc_processor.py](use-cases/document-processing/doc_processor.py) (line 34)

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
