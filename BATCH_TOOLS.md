# SmolCrawl Batch Tools

Easy-to-use Windows batch files for SmolCrawl document processing.

## Quick Start

```bash
# Test with a small sample
smolcrawl test http://localhost:1313

# Complete site crawl
smolcrawl crawl my-docs http://localhost:1313
```

## Available Commands

### `smolcrawl.bat` - Main launcher
Central command that provides access to all other tools.

```bash
smolcrawl help                              # Show help
smolcrawl test http://localhost:1313        # Quick test
smolcrawl crawl my-docs http://localhost:1313 # Full workflow
```

### Individual Tools

#### `discover-urls.bat` - URL Discovery
Discover all URLs from a website using SmolCrawl's crawling engine.

```bash
discover-urls.bat http://localhost:1313
discover-urls.bat http://localhost:1313 my_urls.txt
```

#### `create-use-case.bat` - Use Case Setup
Create a new use case with configuration template.

```bash
create-use-case.bat my-docs http://localhost:8080
```

#### `process-docs.bat` - Document Processing
Process documentation from a config file.

```bash
process-docs.bat use-cases\my-docs\config.json
process-docs.bat use-cases\my-docs\config.json extract
process-docs.bat use-cases\my-docs\config.json merge
```

#### `crawl-site.bat` - Complete Workflow
End-to-end processing: create use case → discover URLs → process all docs.

```bash
crawl-site.bat docker-docs http://localhost:1313
```

#### `quick-test.bat` - Small Test
Test with just the first 5 URLs from a site for debugging.

```bash
quick-test.bat http://localhost:1313
```

## Typical Workflows

### 1. Quick Test (Recommended First Step)
```bash
smolcrawl test http://localhost:1313
```
- Discovers URLs
- Processes first 5 URLs
- Creates test output
- Good for verifying site accessibility

### 2. Full Site Processing
```bash
smolcrawl crawl my-project http://localhost:1313
```
- Creates use case directory
- Discovers all URLs
- Processes complete site
- Generates merged documentation

### 3. Step-by-Step Manual Process
```bash
# 1. Create use case
smolcrawl create my-docs http://localhost:8080

# 2. Discover URLs
smolcrawl discover http://localhost:8080 use-cases\my-docs\discovered_urls.txt

# 3. Edit config to use discovered URLs
# (Edit use-cases\my-docs\config.json: set "url_list_file": "discovered_urls.txt")

# 4. Process documentation
smolcrawl process use-cases\my-docs\config.json
```

## Output Locations

- **Quick test**: `output\quick-test\merged_documentation.md`
- **Full crawl**: `use-cases\{name}\output\{name}\merged_documentation.md`
- **Individual files**: `use-cases\{name}\output\{name}\{category}\*.md`

## Configuration

The tools create optimized configurations automatically:

- **Local sites** (localhost): High worker count (6-12), minimal delays
- **Remote sites**: Lower worker count (2-6), respectful delays
- **Test mode**: Conservative settings (2 workers, longer delays)

## Prerequisites

- Python environment with SmolCrawl dependencies installed
- Windows with batch file support
- Target documentation site running and accessible

## Troubleshooting

1. **"Command not found"**: Ensure you're in the SmolCrawl root directory
2. **Connection errors**: Verify the target URL is accessible in your browser
3. **Permission errors**: Run from a directory with write permissions
4. **Empty output**: Check if the site requires authentication or has CORS restrictions
