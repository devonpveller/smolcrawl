# SmolCrawl AI Agent Instructions

## Quick Start

```bash
# Setup (once)
pip install -e .
npm install                    # Required for readabilipy content extraction

# Document processing (standalone)
python use-cases/document-processing/doc_processor.py full-pipeline --config config.json --server-intensity 0.3

# Deep research (requires Open WebUI + Docker)
docker compose -f integrations/open-webui/docker-compose.yml up -d --build

# CLI crawling
python -m smolcrawl crawl <url>
```

## Architecture Overview

SmolCrawl has three operational modes:

1. **Core Library** (`src/smolcrawl/`) — Async crawler, data models, indexers, RAG augmentation, OWUI client
2. **Document Processor** (`use-cases/document-processing/doc_processor.py`) — Standalone HTML→Markdown bulk extraction
3. **Open WebUI Integration** (`integrations/open-webui/`) — Deep research tools + crawl pipeline running inside OWUI

```
User query in OWUI chat
  │
  ├─→ research()              Quick web-search-only exploration (no crawling)
  │     └─→ web search → relevance gate → topic extraction → iterate → synthesize
  │
  ├─→ knowledge_research()    RAG-only research across existing knowledge collections
  │     └─→ anchor → rank collections → iterative RAG with term expansion
  │         → gap analysis → web search recommendations if exhausted → synthesize
  │
  └─→ deep_research()         Hybrid: knowledge_research → research → crawl → knowledge_research
        └─→ anchor → rank existing collections → iterative RAG (pass 1)
            → gap analysis → web search for sources → crawl via SmolCrawl
            → iterative RAG (pass 2, expanded collections) → synthesize → verify
```

## Project Structure

```
src/smolcrawl/                    # Core library (pip install -e .)
  ├── crawl.py                    # Async crawler: httpx + BeautifulSoup + readabilipy
  ├── db.py                       # Page/Section models, indexers (Tantivy, Markdown, XML)
  ├── augment.py                  # Markdown pseudo-header normalization + metadata injection for RAG
  ├── owui_client.py              # Open WebUI Knowledge Base API client (upload, sync, manifests)
  ├── utils.py                    # Storage paths, diskcache management
  └── frontier/                   # Mercator-style URL scheduling
      ├── models.py               #   URLEntry dataclass (priority queue ordering)
      ├── frontier.py             #   URLFrontier: front queues → back queues pipeline
      ├── front_queues.py         #   FrontQueueManager: depth-based priority (4 levels)
      ├── back_queues.py          #   BackQueueManager: per-host politeness delays
      └── llm_evaluator.py        #   LLM-based cross-domain link scoring

integrations/open-webui/          # OWUI integration (deployed via Docker)
  ├── deep_research_tool.py       # Single-file OWUI Tool (~1800 lines, self-contained)
  ├── smolcrawl_pipeline.py       # OWUI Pipeline: crawl → augment → upload to KB
  ├── docker-compose.yml          # SmolCrawl Pipelines container config
  ├── Dockerfile                  # Based on open-webui/pipelines, adds Node.js + smolcrawl
  └── deep_research/              # Modular version (same logic, split into modules)
      ├── models.py               #   Valves, ResearchPhase, dataclasses
      ├── tool.py                 #   Tools entry point: research() + knowledge_research() + deep_research()
      ├── sub_agent.py            #   SubAgent: internal LLM calls via generate_chat_completion
      ├── research.py             #   QuickResearcher: web-search-only iteration loop
      ├── knowledge_research.py   #   KnowledgeResearcher: RAG-only iteration across existing collections
      ├── domain_discovery.py     #   DomainDiscovery: web search + LLM domain scoring
      ├── crawl_integration.py    #   CrawlClient: HTTP to SmolCrawl Pipelines container
      ├── rag_research.py         #   RagResearcher: iterative RAG across OWUI collections
      ├── synthesis.py            #   Synthesizer: chain-of-thought + verification + remediation
      └── journal.py              #   ResearchJournal: Fileshed-compatible session storage

use-cases/                        # Standalone processing workflows
  └── document-processing/        # PRIMARY: doc_processor.py (extract, merge, discover-urls)

smolcrawl-data/cache/crawl/       # diskcache HTTP response cache (auto-created)
```

**Two versions of deep research exist and must be kept in sync:**

- `deep_research_tool.py` — single-file for direct OWUI deployment (copy-paste into admin panel)
- `deep_research/` — modular package for development and testing

## Core Data Models

### `Page` — Central data currency (`src/smolcrawl/db.py`)

All components exchange `List[Page]` objects. `Page` uses `__hash__` on URL for set deduplication.

Fields: `url`, `title`, `content` (markdown), `raw_html`. Method: `get_sections()` splits on `##` headers.

### `Valves` — OWUI configuration (`deep_research/models.py`)

Pydantic BaseModel exposed in OWUI admin panel. Key fields:

- `smolcrawl_url` / `smolcrawl_api_key` — container connection
- `owui_base_url` / `owui_api_key` — OWUI API access
- `max_iterations` (1-15), `fixed_iterations` (1-5), `min_relevant_sources` (1-30)
- `top_k_per_collection`, `max_collections`, `max_domains`
- `auto_approve_domains` — skip manual approval for discovered domains
- `fileshed_compatible` / `storage_base_path` / `save_journal` — session persistence

### `ResearchSession` — Session state

Tracks: `anchor`, `discovered_domains`, `crawl_results`, `iterations`, `seen_chunks` (dedup set).

### `ProcessingConfig` — Document processor config (`doc_processor.py`)

Dataclass with server intensity control (0.0-1.0):

- `max_workers`: 1-12, `delay`: 2.0s-0.0s, `timeout`: 30s-10s, `retries`: 5-2
- Dual format: loads from `.json` or `.yaml`

## Deep Research Architecture

### Pipeline Flow

```
1. Anchor Extraction  (all tools)
   Query → LLM decomposes into research anchor + initial_search_terms (3-5 diverse queries)

2. Collection Ranking  (knowledge_research + deep_research)
   List all OWUI KB collections → LLM ranks by relevance to anchor
   → select top-N collections (high/medium relevance)

3. Iterative Research
   research():             web search → relevance gate → topic extraction → loop
   knowledge_research():   RAG across ranked KB collections → term expansion → stale detection → loop
   deep_research():        runs knowledge_research pass 1 → then research for sources → crawl → knowledge_research pass 2
   All: consecutive-miss/stale detection (3 iterations → stop), dedup via seen_urls/seen_chunks

4. Gap Analysis  (knowledge_research + deep_research)
   LLM identifies topic gaps + checks for official source presence
   knowledge_research(): if exhausted, web search to recommend sources for future crawling
   deep_research(): if gaps remain after pass 1, proceeds to source discovery + crawling

5. Source Discovery + Crawling  (deep_research only)
   Web search → LLM recommends domains/sources to fill gaps
   → SmolCrawl Pipelines container: crawl → augment → upload to OWUI Knowledge Base
   → Progress streamed via SSE to chat
   → knowledge_research pass 2 on expanded collections

6. Synthesis + Verification  (all tools)
   Chain-of-thought synthesis with [SOURCED]/[INFERRED]/[UNCERTAIN] tagging
   → Programmatic URL scrubbing (remove URLs not in collected sources)
   → LLM verification pass (fabricated URLs, unsupported claims, scope mismatch)
   → Remediation if issues found
   → Credibility report appended to output
   knowledge_research(): source recommendations table appended if gaps remain
```

### Key Patterns

**Relevance Gating** — Every web result scored on two axes: relevance to anchor + source authority (0.0-1.0). Authority scale: 1.0=official docs, 0.8=publications, 0.6=reputable blogs, 0.4=forums, 0.2=content farms, 0.0=spam. Sources sorted by authority.

**OWUI Web Search** — `generate_chat_completion()` does NOT trigger web search (metadata flag silently ignored). Must call `search_web()` directly:

```python
from open_webui.routers.retrieval import search_web
from starlette.concurrency import run_in_threadpool
results = await run_in_threadpool(search_web, request, engine, query)
```

**SubAgent LLM Calls** — Uses `generate_chat_completion` with `bypass_filter=True` to prevent recursive tool invocation. JSON extraction handles: pure JSON → markdown code blocks → embedded JSON.

**Fileshed Journal** — Session artifacts persisted at `users/{user_id}/Storage/data/{namespace}/{timestamp}-{slug}/`. Files: `00-prompt.md`, `00-anchor.md`, `01-domains.md`, `02-crawl-status.md`, `03-iteration-*.md`, `0N-synthesis.md`, `manifest.json`.

**Synthesis Verification** — Three-stage: (1) programmatic URL scrubbing against collected source set, (2) LLM verification for unsupported claims / fabricated examples / scope mismatch, (3) LLM remediation to fix flagged issues. Credibility report always appended.

## SmolCrawl Pipeline (OWUI)

`smolcrawl_pipeline.py` — OWUI Pipeline that accepts chat messages like "crawl https://docs.example.com into my-kb".

Flow: extract URL + KB name from message → `crawl_target_sync()` → `augment_pages()` → `OwuiKnowledgeClient.sync_pages()`.

Progress batched every 15s to reduce SSE traffic. Server intensity controls (Valves) auto-scale workers/delays/timeouts.

## Crawler & Frontier

**SmolCrawler** (`src/smolcrawl/crawl.py`) — Async httpx crawler with Mercator-style URL scheduling.

- Content extraction: `readabilipy.simple_json_from_html_string` → `markdownify`
- BFS traversal with configurable depth, concurrent workers, per-host delays
- Disk caching via diskcache at `smolcrawl-data/cache/crawl/`

**URLFrontier** (`src/smolcrawl/frontier/`) — Front queues (4 priority levels by depth) → back queues (per-host rate limiting). Weighted random selection biases toward high-priority while still servicing low-priority URLs.

**LlmLinkEvaluator** (`frontier/llm_evaluator.py`) — Scores cross-domain outbound links (0.0-1.0) using LLM to decide whether to expand crawl to new domains. Batches links for efficiency.

## Augment Module

`src/smolcrawl/augment.py` — Normalizes pseudo-headers (bold lines, colon-terminated, dates, numbered items, ALL CAPS) into proper `##` markdown headers. Injects metadata blocks after each header:

```
[Section: parent > child > item]
[URL: source-url]
[Aliases: keyword1, keyword2, ...]
```

Used by the pipeline to improve RAG chunking quality before uploading to OWUI.

## OWUI Knowledge Client

`src/smolcrawl/owui_client.py` — `OwuiKnowledgeClient` manages OWUI knowledge base lifecycle:

- `find_knowledge_base()` / `create_knowledge_base()` — KB CRUD
- `sync_pages()` — crawl + augment + upload with manifest-based incremental sync (skip unchanged files)
- Thread-safe with per-collection locking, configurable retry backoff and concurrency

## Docker Deployment

```bash
# Build and start SmolCrawl Pipelines container
docker compose -f integrations/open-webui/docker-compose.yml up -d --build
```

The Dockerfile extends `ghcr.io/open-webui/pipelines:main`, adds Node.js (for readabilipy), installs smolcrawl from source, and pins `jsdom@24.1.3` (v25+ breaks readabilipy ESM compatibility). Container joins `ai-stack_default` network for OWUI access. Port 9099, API key `0p3n-w3bu!`.

## Windows Compatibility

**All readabilipy usage requires Windows fix** — readabilipy calls Node.js via subprocess; Windows requires `shell=True`. Implemented as monkey-patch in `crawl.py` lines 26-97 and in `readabilipy_windows_fix.py`. Without it: `FileNotFoundError: [WinError 2]`.

## Coding Standards

- **Type hints** on all public methods. **Google-style docstrings**.
- **Pydantic BaseModel** for data transfer (immutable). **Dataclasses** for configuration (with `__post_init__` validation).
- **Private methods**: single underscore `_method()`. **Constants**: `UPPER_SNAKE_CASE`.
- **Thread safety**: all shared mutable state protected by `threading.Lock()`.
- **Logging**: `loguru`. **Error handling**: specific exception types, retry with backoff for external services.
- **Imports**: stdlib → third-party → local, separated by blank lines.
- **Indexers follow pluggable pattern**: `TantivyIndexer`, `MarkdownFileIndexer`, `XmlFileIndexer` all implement `add_pages()`/`add_page()`.
- **Config injection**: never hardcode values; use `ProcessingConfig`/`Valves` with defaults.
- **Dual-file sync**: changes to `deep_research/` modules must be mirrored in `deep_research_tool.py` and vice versa.

## Essential Commands

```bash
# Document processor
python use-cases/document-processing/doc_processor.py full-pipeline --config config.json --server-intensity 0.5
python use-cases/document-processing/doc_processor.py extract --config config.json
python use-cases/document-processing/doc_processor.py merge --input-dir output/docs --output merged.md
python use-cases/document-processing/doc_processor.py discover-urls --config config.json
python use-cases/document-processing/doc_processor.py create-use-case --name my-docs --base-url http://localhost:8080

# CLI crawling + indexing
python -m smolcrawl crawl <url>
python -m smolcrawl index <url> <index_name>
python -m smolcrawl query <index_name> "search terms"

# Docker (deep research + pipeline)
docker compose -f integrations/open-webui/docker-compose.yml up -d --build
docker compose -f integrations/open-webui/docker-compose.yml logs -f

# Tests
python tests/test_doc_processor.py
python tests/test_crawl.py
python tests/test_augment.py
python tests/test_owui_client.py
```

## Testing

- `tests/test_doc_processor.py` — config loading, URL processing
- `tests/test_crawl.py` — crawler behavior
- `tests/test_augment.py` — markdown augmentation
- `tests/test_owui_client.py` — OWUI API client
- `tests/test_frontier/` — front queues, back queues
- Focus on **integration testing** over unit tests
