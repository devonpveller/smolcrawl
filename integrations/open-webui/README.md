# SmolCrawl OWUI Pipeline

An Open WebUI Pipeline that crawls websites and uploads the content to a knowledge base — directly from the chat UI.

## Quick Start

### Docker Compose (recommended)

```bash
cd integrations/open-webui
docker compose up -d
```

This starts:
- **Open WebUI** at `http://localhost:3000`
- **Pipelines server** at `http://localhost:9099` with SmolCrawl pre-installed

### Usage

1. Open `http://localhost:3000` in your browser.
2. Select **SmolCrawl Knowledge Builder** as the model.
3. Type a URL to crawl:
   ```
   crawl https://docs.example.com
   ```
4. Watch live progress as SmolCrawl crawls, augments, and uploads.

### Configuration

Configure via the OWUI admin panel under **Pipelines > SmolCrawl Knowledge Builder > Valves**:

| Setting | Default | Description |
|---------|---------|-------------|
| `owui_base_url` | `http://localhost:3000` | Open WebUI API URL |
| `owui_api_key` | (empty) | API key for authentication |
| `knowledge_base_name` | (auto) | KB name (auto-generated from domain if empty) |
| `server_intensity` | `0.3` | Crawl aggressiveness (0.0 gentle – 1.0 aggressive) |
| `max_pages` | `200` | Maximum pages to crawl |
| `upload_concurrency` | `3` | Parallel upload workers |
| `augment_for_rag` | `true` | Enable RAG metadata injection |

### Alternative: URL Install

If you have SmolCrawl installed on your Pipelines server, install the pipeline via the OWUI admin panel using the raw file URL.

### Alternative: Local Dev

```bash
pip install smolcrawl
# Copy smolcrawl_pipeline.py to your Pipelines server directory
```

## How It Works

1. **Crawl** — Uses SmolCrawl's async crawler to fetch pages from the target URL
2. **Augment** — Normalizes headers and injects RAG metadata blocks
3. **Upload** — Uploads .md files to an OWUI knowledge base with incremental sync

Re-crawling the same URL performs an incremental sync — only changed pages are re-uploaded.
