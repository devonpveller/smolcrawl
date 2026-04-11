# Plan: SmolCrawl → OWUI Knowledge Collection Pipeline

## Overview

Extend SmolCrawl into an end-to-end pipeline that:

1. **Crawls** a domain (existing capability)
2. **Augments** the resulting markdown for RAG (header normalization + metadata injection)
3. **Uploads** to an Open WebUI knowledge collection (create or update)

**Two independent deployment modes** share the same core library but live in separate directories with distinct entry points:

| Mode                    | Entry Point                                          | User                                     | When to use                                                |
| ----------------------- | ---------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------- |
| **Batch / CLI**         | `smolcrawl` CLI, `doc_processor.py`, `smolcrawl.bat` | Developer at a terminal, cron job, CI/CD | Scripted or one-off runs; no OWUI dependency required      |
| **Open WebUI Pipeline** | OWUI Pipelines server + `smolcrawl_pipeline.py`      | Chat UI user                             | Interactive crawl-on-demand inside the OWUI chat interface |

Both modes call the same core modules (`augment.py`, `owui_client.py`, `crawl.py`). Neither depends on the other.

---

## Folder Structure (with deployment boundaries)

```
src/smolcrawl/                          ← CORE LIBRARY (shared by both modes)
  ├── __init__.py                        ← Typer CLI app (batch entry point)
  ├── crawl.py                           ← Async crawler (existing)
  ├── db.py                              ← Page model, indexers (existing)
  ├── utils.py                           ← Storage paths, cache (existing)
  ├── augment.py                         ← NEW: Markdown RAG augmenter
  ├── owui_client.py                     ← NEW: OWUI Knowledge REST client
  └── frontier/                          ← URL frontier (existing)

use-cases/
  └── document-processing/
      ├── doc_processor.py               ← BATCH: extended with augment + owui-sync commands
      ├── readabilipy_windows_fix.py     ← (existing)
      └── ...

scripts/                                 ← BATCH: setup & automation
  ├── setup.ps1
  └── setup.sh

smolcrawl.bat                            ← BATCH: interactive Windows entry point

integrations/                            ← NEW TOP-LEVEL: all external integrations
  └── open-webui/                        ← OWUI PIPELINE: self-contained deployment
      ├── smolcrawl_pipeline.py          ← Pipeline class (pipe + Valves)
      ├── Dockerfile                     ← Builds Pipelines image with smolcrawl
      ├── docker-compose.yml             ← OWUI + Pipelines together
      └── README.md                      ← Deployment & usage guide

tests/
  ├── test_augment.py                    ← NEW: augmenter tests
  ├── test_owui_client.py                ← NEW: OWUI client tests (mocked)
  └── ...                                ← (existing tests unchanged)

smolcrawl-data/                          ← RUNTIME DATA (both modes)
  ├── cache/crawl/                       ← HTTP response cache
  └── owui-manifests/                    ← NEW: per-KB sync manifests
```

**Key boundary rule:** Nothing inside `integrations/open-webui/` is imported by the core library or the batch CLI. Nothing inside `use-cases/` or `scripts/` is imported by the pipeline. Both sides depend only on `src/smolcrawl/`.

---

## Architecture

### Batch / CLI Mode

```
Terminal / cron / CI
  │
  ├── smolcrawl crawl <url>                    ← existing
  ├── smolcrawl augment --input-dir ...        ← NEW
  ├── smolcrawl owui-sync --input-dir ...      ← NEW
  ├── smolcrawl owui-pipeline --url ...        ← NEW (all-in-one)
  │
  └── doc_processor.py full-pipeline ...       ← existing, extended
      doc_processor.py owui-sync ...           ← NEW command
      smolcrawl.bat                            ← existing, extended
  │
  ▼
┌──────────────────────────────────────────┐
│  src/smolcrawl/  (core library)          │
│  crawl.py → augment.py → owui_client.py  │
└──────────────────────────────────────────┘
```

### Open WebUI Pipeline Mode

```
┌─────────────────────────────────────────────────────────────────┐
│  Open WebUI Chat UI                                             │
│  User: "crawl https://docs.example.com"                        │
│  ↓                                                              │
│  Pipeline "model" (smolcrawl-pipeline)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ OpenAI-compatible API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Pipelines Server (Docker, port 9099)                           │
│                                                                 │
│  integrations/open-webui/smolcrawl_pipeline.py                  │
│  ├── pipe() → parse user message, orchestrate workflow          │
│  │   ├── 1. SmolCrawler.crawl(url)                              │
│  │   │      → List[Page]  (src/smolcrawl/crawl.py)              │
│  │   ├── 2. augment_pages(pages)                                │
│  │   │      → augmented Pages  (src/smolcrawl/augment.py)       │
│  │   ├── 3. OwuiKnowledgeClient.sync_pages(pages, kb_name)     │
│  │   │      → upload to OWUI KB  (src/smolcrawl/owui_client.py) │
│  │   └── 4. yield progress strings (streaming response)         │
│  └── Valves: owui_base_url, owui_api_key, server_intensity, …  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phases

### Phase 1: Markdown RAG Augmenter Module

**Goal:** Standalone module that normalizes headers and injects metadata into crawled markdown, making it optimal for OWUI's RAG chunking.

**New file:** `src/smolcrawl/augment.py`

**Responsibilities:**

- Accept a `Page` object (or raw markdown string + path)
- Walk line-by-line detecting pseudo-headers (bold, colon, date, numbered, ALL CAPS)
- Determine correct header level from breadcrumb context
- Inject metadata block after each header:
  ```
  [DocTitle: <title>]
  [Path: <source-url>]
  [Section: H1 > H2 > H3]
  [Aliases: keyword1, keyword2]
  ```
- Return augmented markdown string

**Key functions (from reference-rag-augmentation.md):**

| Function                                                            | Purpose                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `check_header_patterns(line)`                                       | Classify line into header pattern type                             |
| `determine_header_level_by_context(breadcrumb, pattern_type, text)` | Assign header level 1–6                                            |
| `convert_to_proper_header(text, level, pattern_type)`               | Build clean `#` header                                             |
| `guess_aliases_from_heading(text)`                                  | Extract up to 5 keywords                                           |
| `build_metadata_block(doc_title, source_url, breadcrumb, aliases)`  | Format 4-line metadata block                                       |
| `augment_markdown(md_text, source_url, doc_title)`                  | Orchestrate line-by-line walk                                      |
| `augment_pages(pages: List[Page]) -> List[Page]`                    | Batch process Page objects, return Pages with augmented `.content` |

**Design constraints:**

- Zero external dependencies (only `re`, `pathlib` — matches reference)
- Operates on `Page.content` (markdown) — does not need `raw_html`
- Returns new `Page` objects with augmented content (immutability)
- Thread-safe (stateless functions)

**Tests:** `tests/test_augment.py`

- Verify bold → header conversion
- Verify metadata block injection
- Verify breadcrumb tracking across nested sections
- Verify `augment_pages()` batch processing

---

### Phase 2: OWUI Knowledge Client

**Goal:** A client that talks to the Open WebUI REST API to manage knowledge collections and upload files.

**New file:** `src/smolcrawl/owui_client.py`

**OWUI REST API endpoints used:**

| Endpoint                             | Method   | Purpose                          |
| ------------------------------------ | -------- | -------------------------------- |
| `/api/v1/knowledge/`                 | `GET`    | List existing knowledge bases    |
| `/api/v1/knowledge/`                 | `POST`   | Create a new knowledge base      |
| `/api/v1/knowledge/{id}`             | `GET`    | Get KB details (files, metadata) |
| `/api/v1/files/`                     | `POST`   | Upload a markdown file           |
| `/api/v1/files/{id}/process/status`  | `GET`    | Poll file processing status      |
| `/api/v1/knowledge/{id}/file/add`    | `POST`   | Link processed file to KB        |
| `/api/v1/knowledge/{id}/file/remove` | `POST`   | Unlink a file from KB            |
| `/api/v1/files/{id}`                 | `DELETE` | Delete an uploaded file          |

**Classes:**

```python
@dataclass
class OwuiConfig:
    base_url: str                       # e.g. "http://localhost:3000"
    api_key: str                        # Bearer token
    knowledge_base_name: str            # e.g. "SmolCrawl - docs.example.com"
    upload_concurrency: int = 3         # parallel upload workers
    retry_attempts: int = 3             # retries per upload
    retry_backoff_base: float = 1.0     # exponential backoff base (seconds)
    processing_timeout: int = 300       # max seconds to wait for file processing


class OwuiKnowledgeClient:
    """Manages knowledge base lifecycle and file uploads to Open WebUI."""

    def __init__(self, config: OwuiConfig):
        ...

    # --- Knowledge Base Management ---
    def find_knowledge_base(self, name: str) -> Optional[dict]:
        """GET /api/v1/knowledge/ → find KB by name."""

    def create_knowledge_base(self, name: str, description: str = "") -> dict:
        """POST /api/v1/knowledge/ → create new KB, return KB dict."""

    def get_or_create_knowledge_base(self, name: str, description: str = "") -> str:
        """Returns KB id. Creates if not found."""

    # --- File Upload ---
    def upload_file(self, filename: str, content: bytes) -> str:
        """POST /api/v1/files/ → returns file_id."""

    def wait_for_processing(self, file_id: str) -> dict:
        """Poll GET /api/v1/files/{id}/process/status until completed/failed."""

    def add_file_to_knowledge_base(self, kb_id: str, file_id: str) -> dict:
        """POST /api/v1/knowledge/{id}/file/add."""

    # --- Sync Orchestration ---
    def sync_pages(
        self,
        pages: List[Page],
        kb_name: str,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> SyncResult:
        """
        Full sync workflow:
        1. get_or_create_knowledge_base(kb_name)
        2. For each page:
           a. Upload as .md file
           b. Wait for processing
           c. Link to KB
        3. Return SyncResult with stats

        Uses ThreadPoolExecutor(max_workers=config.upload_concurrency).
        Calls on_progress(current, total, filename) after each file.
        """

    # --- Manifest (Incremental Sync) ---
    def _load_manifest(self, kb_name: str) -> dict:
        """Load {content_hash → file_id} mapping from disk."""

    def _save_manifest(self, kb_name: str, manifest: dict):
        """Persist manifest to smolcrawl-data/owui-manifests/{kb_name}.json."""

    def _content_hash(self, content: str) -> str:
        """SHA-256 of content for dedup."""
```

**`SyncResult` dataclass:**

```python
@dataclass
class SyncResult:
    knowledge_base_id: str
    total_files: int
    uploaded: int           # new or changed
    skipped: int            # unchanged (hash match)
    failed: int
    errors: List[str]
```

**Key patterns (from reference-owui-knowledge-collection-api.md):**

- **Manifest + incremental sync:** Store `{content_hash → file_id}` in `smolcrawl-data/owui-manifests/`. Only upload files whose content hash changed.
- **Content-hash dedup:** SHA-256 of augmented markdown. Skip upload if hash matches manifest.
- **Concurrent uploads:** `ThreadPoolExecutor` with configurable concurrency (default 3).
- **Retry with exponential backoff:** 3 attempts, 1s → 2s → 4s.
- **Processing wait:** Poll `/api/v1/files/{id}/process/status` every 2s until `completed` or `failed`.
- **Progress callback:** `on_progress(current, total, filename)` for UI reporting.

**Dependencies:** `httpx` (already in project), or `requests` for sync operations.

**Tests:** `tests/test_owui_client.py`

- Mock HTTP responses for all endpoints
- Test manifest load/save and content-hash dedup
- Test retry logic
- Test get_or_create flow

---

### Phase 3: Batch CLI Integration

**Goal:** Expose the full crawl → augment → upload pipeline from the terminal and batch scripts. This is the primary interface for scripted/automated use — no OWUI Pipelines server needed.

**Changes to:** `src/smolcrawl/__init__.py` (Typer app)

**New CLI commands:**

```bash
# Augment existing markdown files (standalone — no OWUI required)
smolcrawl augment --input-dir output/docs --output-dir output/docs_augmented

# Upload a directory of markdown files to OWUI KB
smolcrawl owui-sync \
  --input-dir output/docs \
  --owui-url http://localhost:3000 \
  --owui-api-key sk-xxx \
  --kb-name "My Documentation" \
  --concurrency 3

# Full pipeline: crawl → augment → upload (all-in-one)
smolcrawl owui-pipeline \
  --url https://docs.example.com \
  --owui-url http://localhost:3000 \
  --owui-api-key sk-xxx \
  --kb-name "Example Docs" \
  --server-intensity 0.3 \
  --max-pages 500
```

**Also add to `doc_processor.py`:**

```bash
# New doc_processor commands
python doc_processor.py augment --input-dir output/docs --output-dir output/docs_augmented
python doc_processor.py owui-sync --config config.json \
  --owui-url http://localhost:3000 \
  --owui-api-key sk-xxx \
  --kb-name "My Docs"
```

**Extend `smolcrawl.bat`:**
Add prompts for the new OWUI fields (optional — user can skip to use batch-only augmentation):

```
Would you like to upload to Open WebUI? (y/n)
  OWUI URL [http://localhost:3000]:
  API Key:
  Knowledge Base Name:
```

**Config extension (`ProcessingConfig`):**

```python
# New optional fields — all default to None/disabled so existing configs are unaffected
owui_base_url: Optional[str] = None
owui_api_key: Optional[str] = None
owui_knowledge_base_name: Optional[str] = None
owui_upload_concurrency: int = 3
augment_for_rag: bool = True        # enable/disable augmentation step
```

**Batch-only workflow** (no OWUI at all):

```bash
# Crawl + augment + save to disk. No upload. Works completely offline.
smolcrawl crawl https://docs.example.com
smolcrawl augment --input-dir smolcrawl-data/markdown_files --output-dir output/augmented
# Result: augmented markdown files ready for manual import or other tooling
```

---

### Phase 4: Open WebUI Pipeline Integration

**Goal:** Package SmolCrawl as an OWUI Pipeline that appears as a selectable "model" in the chat UI. This is an **optional, separate deployment** — it does not affect the batch CLI.

**New directory:** `integrations/open-webui/`

**New file:** `integrations/open-webui/smolcrawl_pipeline.py`

**Pipeline structure (follows OWUI Pipeline conventions):**

```python
"""
title: SmolCrawl Knowledge Builder
author: smolcrawl
date: 2026-04-10
version: 1.0
license: MIT
description: Crawl a website, augment markdown for RAG, and upload to an OWUI knowledge collection. Streams progress in chat.
requirements: smolcrawl, httpx, markdownify, readabilipy, beautifulsoup4, lxml
"""

from typing import List, Union, Generator, Iterator


class Pipeline:
    class Valves(BaseModel):
        """User-configurable settings shown in OWUI admin panel."""
        owui_base_url: str = "http://localhost:3000"
        owui_api_key: str = ""
        knowledge_base_name: str = ""   # empty = auto-generate from domain
        server_intensity: float = 0.3
        max_pages: int = 200
        upload_concurrency: int = 3
        augment_for_rag: bool = True

    def __init__(self):
        self.name = "SmolCrawl Knowledge Builder"
        self.valves = self.Valves()

    async def on_startup(self):
        """Verify smolcrawl is importable, check OWUI connection."""
        pass

    async def on_shutdown(self):
        pass

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Generator[str, None, None]:
        """
        Expects user_message containing a URL to crawl.
        Streams progress as markdown-formatted status updates.
        """
        # 1. Parse URL from user message
        url = self._extract_url(user_message)
        if not url:
            yield "Please provide a URL to crawl. Example: `crawl https://docs.example.com`"
            return

        # 2. Determine KB name
        kb_name = self.valves.knowledge_base_name or f"SmolCrawl - {domain}"
        yield f"## Starting SmolCrawl Pipeline\n\n"
        yield f"**Target:** {url}\n"
        yield f"**Knowledge Base:** {kb_name}\n"
        yield f"**Max Pages:** {self.valves.max_pages}\n\n"

        # 3. Crawl
        yield f"### Phase 1: Crawling\n\n"
        pages = crawl_target_sync(url, max_pages=self.valves.max_pages, ...)
        yield f"Crawled **{len(pages)}** pages.\n\n"

        # 4. Augment
        if self.valves.augment_for_rag:
            yield f"### Phase 2: Augmenting for RAG\n\n"
            pages = augment_pages(pages)
            yield f"Augmented **{len(pages)}** pages with metadata.\n\n"

        # 5. Upload to OWUI
        yield f"### Phase 3: Uploading to Knowledge Base\n\n"
        client = OwuiKnowledgeClient(config)
        result = client.sync_pages(
            pages, kb_name,
            on_progress=lambda cur, tot, name: None  # progress via yield below
        )

        # 6. Summary
        yield f"### Complete!\n\n"
        yield f"| Metric | Value |\n|--------|-------|\n"
        yield f"| Pages crawled | {len(pages)} |\n"
        yield f"| Files uploaded | {result.uploaded} |\n"
        yield f"| Files skipped (unchanged) | {result.skipped} |\n"
        yield f"| Failures | {result.failed} |\n"
        yield f"| Knowledge Base | {kb_name} |\n"
```

**Progress streaming approach:**

The `pipe()` method is a generator. Each `yield` sends a chunk to the chat UI in real-time. The user sees a live-updating markdown response as the pipeline progresses through crawl → augment → upload phases.

For granular upload progress (per-file), we use a background thread + queue pattern:

```python
import queue
import threading

def pipe(self, user_message, ...):
    ...
    progress_queue = queue.Queue()

    def upload_worker():
        client.sync_pages(pages, kb_name,
            on_progress=lambda cur, tot, name:
                progress_queue.put((cur, tot, name))
        )
        progress_queue.put(None)  # sentinel

    thread = threading.Thread(target=upload_worker)
    thread.start()

    while True:
        item = progress_queue.get()
        if item is None:
            break
        cur, tot, name = item
        yield f"Uploading: {cur}/{tot} — {name}\n"

    thread.join()
```

**Deployment options:**

1. **Docker (recommended):** Build a custom Pipelines image with SmolCrawl pre-installed:

   ```dockerfile
   FROM ghcr.io/open-webui/pipelines:main
   RUN pip install smolcrawl
   COPY smolcrawl_pipeline.py /app/pipelines/
   ```

2. **URL install:** Host `smolcrawl_pipeline.py` and install via OWUI admin panel (requires SmolCrawl installed on the Pipelines server).

3. **Local dev:** Run Pipelines server locally with SmolCrawl in the same Python environment.

**New files (all in `integrations/open-webui/`):**

- `smolcrawl_pipeline.py` — Pipeline class
- `Dockerfile` — Custom Pipelines Docker image
- `docker-compose.yml` — Docker Compose for OWUI + Pipelines together
- `README.md` — Deployment & usage guide (standalone from main README)

---

### Phase 5: Incremental Updates & Scheduling

**Goal:** Support re-crawling a domain and only uploading changed content to the existing KB.

**Manifest system (in `OwuiKnowledgeClient`):**

```
smolcrawl-data/
  owui-manifests/
    SmolCrawl - docs.example.com.json    ← per-KB manifest
```

**Manifest schema:**

```json
{
  "knowledge_base_id": "uuid-of-kb",
  "knowledge_base_name": "SmolCrawl - docs.example.com",
  "last_sync": "2026-04-10T12:00:00Z",
  "files": {
    "https://docs.example.com/intro": {
      "content_hash": "sha256:abc123...",
      "owui_file_id": "file-uuid-1",
      "last_updated": "2026-04-10T12:00:00Z"
    },
    "https://docs.example.com/api": {
      "content_hash": "sha256:def456...",
      "owui_file_id": "file-uuid-2",
      "last_updated": "2026-04-10T12:00:00Z"
    }
  }
}
```

**Sync logic:**

1. Crawl domain → get pages
2. Augment pages
3. Load manifest for this KB
4. For each page:
   - Compute content hash
   - If hash matches manifest → **skip** (already up-to-date)
   - If hash differs → **upload new version**, delete old file from OWUI, update manifest
   - If page is new → **upload**, add to manifest
5. For manifest entries not in crawl results → **delete from OWUI** (page was removed from source)
6. Save updated manifest

**Re-crawl via Pipeline:**

- User types: `crawl https://docs.example.com` (same URL again)
- Pipeline detects existing manifest → runs incremental sync
- Reports: "Updated 5, skipped 195, removed 2"

---

## File Inventory (New & Modified)

### New Files — Core Library (used by both modes)

| File                           | Phase | Description                      |
| ------------------------------ | ----- | -------------------------------- |
| `src/smolcrawl/augment.py`     | 1     | Markdown RAG augmentation module |
| `src/smolcrawl/owui_client.py` | 2     | OWUI knowledge base REST client  |
| `tests/test_augment.py`        | 1     | Augmenter unit tests             |
| `tests/test_owui_client.py`    | 2     | OWUI client tests (mocked HTTP)  |

### New Files — Open WebUI Integration (optional deployment)

| File                                            | Phase | Description                        |
| ----------------------------------------------- | ----- | ---------------------------------- |
| `integrations/open-webui/smolcrawl_pipeline.py` | 4     | OWUI Pipeline class                |
| `integrations/open-webui/Dockerfile`            | 4     | Custom Pipelines Docker image      |
| `integrations/open-webui/docker-compose.yml`    | 4     | Docker Compose for OWUI + Pipeline |
| `integrations/open-webui/README.md`             | 4     | Pipeline deployment & usage guide  |

### Modified Files — Batch CLI (existing terminal workflow)

| File                                             | Phase | Changes                                                           |
| ------------------------------------------------ | ----- | ----------------------------------------------------------------- |
| `src/smolcrawl/__init__.py`                      | 3     | Add `augment`, `owui-sync`, `owui-pipeline` CLI commands          |
| `use-cases/document-processing/doc_processor.py` | 3     | Add `augment` and `owui-sync` commands, extend `ProcessingConfig` |
| `smolcrawl.bat`                                  | 3     | Add optional OWUI upload prompts                                  |

### Modified Files — Project-wide

| File                              | Phase | Changes                                                            |
| --------------------------------- | ----- | ------------------------------------------------------------------ |
| `pyproject.toml`                  | 2     | Add `owui` optional dependency group                               |
| `.github/copilot-instructions.md` | 5     | Document new modules, both deployment modes                        |
| `README.md`                       | 5     | Add sections for augmentation, OWUI sync, and pipeline integration |

---

## Dependency Changes

**No new required dependencies.** The project already uses `httpx` for HTTP and `pydantic` for data models.

**New optional dependency group in `pyproject.toml`:**

```toml
[project.optional-dependencies]
full = ["tantivy>=0.22.2"]
owui = []  # no extra deps needed — httpx already required
```

**Pipeline server dependencies** (handled by Pipeline header `requirements:` field):

```
smolcrawl
httpx
markdownify
readabilipy
beautifulsoup4
lxml
```

---

## Implementation Order

```
                        ┌── CORE LIBRARY ──┐
Phase 1 ─── augment.py + tests ───────────┤
                                           │
Phase 2 ─── owui_client.py + tests ───────┤
                                           │
          ┌────────────────────────────────┤
          │                                │
     BATCH TRACK                    OWUI TRACK
          │                                │
Phase 3 ─── CLI commands              Phase 4 ─── Pipeline + Docker
            smolcrawl.bat                         integrations/open-webui/
            doc_processor.py                      │
          │                                │
          └────────────────────────────────┤
                                           │
                                    Phase 5 ─── Incremental sync + docs
```

Phases 1 and 2 are independent and can be built in parallel — they form the **shared core**.
Phase 3 (batch CLI) and Phase 4 (OWUI pipeline) are **independent of each other** and can be built in parallel once the core is ready. Phase 5 refines Phase 2's manifest logic and updates docs for both tracks.

---

## OWUI API Reference (Quick Lookup)

These are the actual verified API endpoints from the [Open WebUI API docs](https://docs.openwebui.com/reference/api-endpoints):

### File Upload Flow

```
POST /api/v1/files/                          ← upload .md file (multipart form)
  → returns { "id": "file-uuid", ... }

GET /api/v1/files/{id}/process/status        ← poll until status = "completed"
  → returns { "status": "pending|completed|failed" }

POST /api/v1/knowledge/{kb_id}/file/add      ← link file to KB
  → body: { "file_id": "file-uuid" }
```

### Knowledge Base Management

```
GET  /api/v1/knowledge/                      ← list all KBs
POST /api/v1/knowledge/                      ← create new KB
  → body: { "name": "...", "description": "..." }
GET  /api/v1/knowledge/{id}                  ← get KB details
```

### Alternative: Direct Web URL Processing

```
POST /api/v1/retrieval/process/web           ← fetch URL + embed directly
  → body: { "url": "...", "collection_name": "..." }
  → query: ?process=true&overwrite=false
```

> **Note:** The direct web URL processing endpoint (`/api/v1/retrieval/process/web`) is simpler but bypasses our custom augmentation. The file upload approach gives us control over content quality through the augmentation step.

---

## Key Design Decisions

### 1. Why two deployment modes?

The batch CLI and OWUI pipeline serve different users with different constraints. A developer running a cron job doesn't need Docker or an OWUI instance. A chat user interacting via OWUI doesn't want to open a terminal. By keeping the core logic in `src/smolcrawl/` and the deployment wiring in separate directories (`use-cases/` + `scripts/` for batch, `integrations/open-webui/` for OWUI), each mode can evolve independently without breaking the other. The `integrations/` folder is structured to welcome future integrations (e.g., `integrations/langchain/`, `integrations/mcp/`) without polluting the core.

### 2. Why Pipeline over Function (for the OWUI track)?

OWUI docs explicitly recommend Pipelines for "computationally heavy tasks (e.g., running large models or complex logic) that you want to offload from your main Open WebUI instance." Crawling + processing + uploading fits this exactly. Functions run inside the OWUI process and would block it.

### 3. Why augment before upload?

OWUI's built-in RAG chunking works on file content. By normalizing headers and injecting metadata blocks, we give the chunker clean section boundaries and each chunk includes its own context (DocTitle, Section breadcrumb, Aliases). This significantly improves retrieval quality without modifying OWUI's chunking logic.

### 4. Why manifest-based incremental sync?

Re-crawling a large documentation site shouldn't re-upload 500 unchanged files. The content-hash manifest (borrowed from the GAPS-app pattern in reference-owui-knowledge-collection-api.md) ensures only changed content is re-uploaded. This respects OWUI server resources and reduces sync time from minutes to seconds for incremental updates.

### 5. Why upload .md files instead of using /retrieval/process/web?

The web URL endpoint uses OWUI's own fetcher/parser, which we can't control. By uploading pre-processed augmented markdown files, we ensure consistent extraction quality and RAG-optimized content structure.

### 6. Why stream progress via generator?

The OWUI Pipeline `pipe()` method supports generators for streaming responses. This lets us show real-time progress in the chat UI without any additional websocket or polling infrastructure. The user sees a live markdown document being built as the pipeline runs.

---

## Risks & Mitigations

| Risk                                     | Impact                        | Mitigation                                                                             |
| ---------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------- |
| OWUI API changes between versions        | Upload/KB creation breaks     | Version-check on startup; abstract all API calls behind `OwuiKnowledgeClient`          |
| Large sites exceed Pipeline timeout      | Pipeline killed mid-sync      | Use `max_pages` valve; incremental sync recovers on next run                           |
| File processing takes too long           | Sync stalls on status polling | Configurable `processing_timeout`; skip failed files, report in summary                |
| Concurrent uploads overload OWUI         | 429/5xx errors                | Configurable concurrency; exponential backoff; default conservative (3 workers)        |
| Node.js not available in Pipeline Docker | readabilipy fails             | Pipeline Dockerfile installs Node.js + npm; or fall back to non-readabilipy extraction |
| Network issues between Pipeline and OWUI | Upload failures               | Retry with backoff (3 attempts); report partial results                                |

---

## Success Criteria

### Core Library (Phases 1–2)

- [ ] `augment_pages()` produces augmented markdown with metadata blocks
- [ ] `OwuiKnowledgeClient.sync_pages()` uploads files to a named KB with manifest-based dedup
- [ ] Re-running sync on unchanged content skips all files (hash match)
- [ ] All existing tests continue to pass
- [ ] New modules have test coverage

### Batch / CLI Track (Phase 3)

- [ ] `smolcrawl augment` CLI command works standalone (no OWUI required)
- [ ] `smolcrawl owui-sync` uploads augmented files from a local directory
- [ ] `smolcrawl owui-pipeline` runs the full crawl → augment → upload from terminal
- [ ] `doc_processor.py augment` and `doc_processor.py owui-sync` commands work
- [ ] `smolcrawl.bat` supports optional OWUI upload prompts
- [ ] Batch workflow works fully offline (crawl + augment only, no OWUI)

### Open WebUI Pipeline Track (Phase 4)

- [ ] Pipeline appears as selectable "model" in OWUI chat UI
- [ ] Typing a URL in chat triggers crawl and streams progress
- [ ] Valves (settings) are configurable from OWUI admin panel
- [ ] Docker Compose in `integrations/open-webui/` brings up working OWUI + Pipeline stack
- [ ] `integrations/open-webui/README.md` covers deployment independently
