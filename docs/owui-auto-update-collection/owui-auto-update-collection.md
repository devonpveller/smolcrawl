# OWUI Knowledge Collection Auto-Update Plan

## Overview

Allow users to mark a knowledge collection as "keep up to date". SmolCrawl will
then periodically detect changes on the source domain and perform a targeted
incremental sync — only re-crawling and re-uploading pages that have actually
changed — rather than rebuilding the entire collection from scratch.

---

## Goals

- Zero-effort maintenance: once a KB is "watched", updates flow automatically.
- Lightweight detection: use cheap signals (ETags, sitemaps, RSS) before
  falling back to a full diff.
- Incremental uploads: only changed pages hit the OWUI API.
- Full observability: every update run is logged, and a summary message is
  posted to OWUI.
- Chat-native UX: all commands work inside the existing pipeline chat.

---

## User-Facing Commands (Pipeline Chat)

| Command | Effect |
|---|---|
| `watch https://docs.example.com as My KB` | Register KB, default 24 h interval |
| `watch … as My KB every 6 hours` | Custom check interval |
| `watch … as My KB rss https://…/feed.xml` | Add RSS/Atom hint |
| `watch … as My KB changelog https://…/changelog` | Add changelog-page hint |
| `unwatch My KB` | Remove from watch list |
| `check updates for My KB` | Trigger an immediate check |
| `list watched` | Show all watched KBs and last-checked timestamps |

These commands are handled by the existing `SmolCrawlPipeline.pipe()` method
alongside the current `crawl … into …` command.

---

## Architecture

### New Files

```
src/smolcrawl/
    watcher.py          ← WatchEntry model, WatchList, change detectors
    scheduler.py        ← Background scheduler thread + update orchestration

integrations/open-webui/
    smolcrawl_pipeline.py   ← extended (watch/unwatch/check/list commands)
```

### Persistent Storage

```
smolcrawl-data/
    watch_list.json                    ← all WatchEntry records
    update-logs/
        <safe_kb_name>_updates.jsonl   ← append-only run history
```

`watch_list.json` is written atomically (write-to-temp + rename) to avoid
corruption if the process is killed mid-write.

---

## Data Model

### `WatchEntry` (dataclass, stored in `watch_list.json`)

```python
@dataclass
class WatchEntry:
    kb_name: str
    source_url: str                      # domain root to crawl
    check_interval_hours: float = 24.0
    signals: List[str] = field(         # which detectors to run
        default_factory=lambda: ["etag", "sitemap", "rss", "changelog"]
    )
    changelog_url: Optional[str] = None  # explicit changelog page
    rss_url: Optional[str] = None        # explicit feed URL
    server_intensity: float = 0.3
    # State (updated after each run)
    last_checked: Optional[str] = None   # ISO-8601 UTC
    last_changed: Optional[str] = None   # ISO-8601 UTC
    next_check_at: Optional[str] = None  # ISO-8601 UTC
    # Detector caches (keyed by URL or feed entry id)
    etag_cache: Dict[str, str] = field(default_factory=dict)
    lastmod_cache: Dict[str, str] = field(default_factory=dict)
    rss_last_entry_id: Optional[str] = None
    rss_last_pub_date: Optional[str] = None
```

### `WatchList` (class in `watcher.py`)

Thin wrapper around `watch_list.json`:

- `load() -> List[WatchEntry]`
- `save(entries)`
- `add(entry)` / `remove(kb_name)` / `get(kb_name)`

Write strategy: `json.dump` to `<path>.tmp`, then `os.replace` (atomic on all
platforms).

---

## Change Detection: Signal Priority

Detectors run in cheapest-first order. Each returns a set of URLs suspected to
have changed. The union is the targeted re-crawl set.

### 1. RSS / Atom Feed Detector (`RssDetector`)

- Fetch the RSS/Atom feed (explicit `rss_url`, or auto-discovered from
  `<link rel="alternate">` on the home page).
- Parse with the stdlib `xml.etree.ElementTree` (no extra dependency).
- Collect all `<item>` / `<entry>` elements with `<pubDate>` / `<updated>`
  newer than `rss_last_pub_date`.
- Store the newest entry id/date back to the `WatchEntry`.
- **Returns:** set of `<link>` URLs from new/updated feed items.

### 2. Sitemap `<lastmod>` Detector (`SitemapDetector`)

- Fetch `{source_url}/sitemap.xml` (also try `robots.txt` for `Sitemap:`
  directives).
- For each `<url>` entry: compare `<lastmod>` to `lastmod_cache[url]`.
- Update cache for all seen entries.
- **Returns:** URLs where `<lastmod>` advanced.

### 3. HTTP ETag / Last-Modified Detector (`EtagDetector`)

- For each URL already in the manifest (`owui-manifests/<kb>.json`), send a
  `HEAD` request.
- Compare `ETag` or `Last-Modified` response header against `etag_cache`.
- Update cache.
- **Returns:** URLs where header changed or was absent before.
- Rate-limited by `server_intensity` (delay between HEAD requests).

### 4. Changelog Page Detector (`ChangelogDetector`)

- Fetch `changelog_url` (or auto-probe common paths: `/changelog`,
  `/release-notes`, `/whatsnew`).
- Hash the extracted markdown content.
- Compare to stored hash in `WatchEntry`.
- If changed: the changelog page itself plus all links on it are added to the
  re-crawl set.
- **Returns:** changelog URL + all linked URLs if content changed.

**Fallback:** if all detectors return an empty set but the entry has never
been successfully checked, treat the entire domain as outdated (triggers a
full sync identical to the original build).

---

## Incremental Update Flow

```
ChangeDetector.detect(entry) → changed_urls (Set[str])
          │
          ▼
SmolCrawler.crawl_urls(changed_urls)   ← targeted crawl, not domain-wide
          │
          ▼
augment_pages(pages)
          │
          ▼
OwuiKnowledgeClient.sync_pages(pages, kb_name)
          │   (existing manifest dedup ensures only truly changed content uploads)
          ▼
UpdateLog.append(run_result)
          │
          ▼
OwuiNotifier.post_summary(run_result)
```

`SmolCrawler` already supports arbitrary start URLs; we seed it with
`changed_urls` instead of a single domain root, and set `max_depth=0` so it
crawls exactly those pages without following links (configurable to `max_depth=1`
if shallow neighbour links should be included).

---

## Background Scheduler (`scheduler.py`)

### Design

- Single daemon thread (`UpdateSchedulerThread`) started in
  `Pipeline.on_startup()` and stopped in `Pipeline.on_shutdown()`.
- No extra dependencies — stdlib `threading` and `time` only.
- Loop wakes every 60 seconds, loads `WatchList`, finds entries where
  `next_check_at <= now()`, and runs the update pipeline sequentially
  (or with a bounded `ThreadPoolExecutor` for parallel KB checks if
  `max_concurrent_watches > 1` valve is set).

```python
class UpdateSchedulerThread(threading.Thread):
    def __init__(self, valves, stop_event): ...

    def run(self):
        while not self._stop_event.wait(timeout=60):
            due = self._get_due_entries()
            for entry in due:
                self._run_update(entry)

    def _get_due_entries(self) -> List[WatchEntry]: ...
    def _run_update(self, entry: WatchEntry): ...
```

### Thread Safety

`WatchList.save()` uses `os.replace` (atomic). The scheduler always
re-loads from disk before each batch to pick up changes made by the
pipeline (e.g., a manual `watch` command adding a new entry mid-run).

---

## OWUI Notification (`OwuiNotifier`)

After each update run (scheduled or manual), SmolCrawl:

1. **Appends a JSON line** to `smolcrawl-data/update-logs/<safe_name>_updates.jsonl`:
   ```json
   {
     "ts": "2026-04-11T14:00:00Z",
     "kb_name": "My KB",
     "trigger": "scheduled",
     "changed_urls": 5,
     "uploaded": 3,
     "skipped": 2,
     "failed": 0,
     "detectors_fired": ["rss", "etag"]
   }
   ```

2. **POSTs a chat message** to the OWUI API (`POST /api/v1/chats/` or a
   configurable channel id stored in `Valves`). Message format:
   ```
   🔄 **Auto-update: My KB**
   Checked: https://docs.example.com
   Signals: RSS feed (+2 items), ETag changes (3 pages)
   Uploaded: 3 pages | Skipped: 2 unchanged | Failed: 0
   ```
   If no changes were found, no message is posted (silent success).

---

## Pipeline Valves (new additions)

```python
class Valves(BaseModel):
    # ... existing ...
    watch_check_interval_hours: float = 24.0   # default interval for new watches
    watch_max_depth: int = 0                    # 0 = exact URLs only, 1 = +1 hop
    watch_max_concurrent: int = 1               # parallel KB updates
    owui_notify_channel_id: str = ""            # OWUI chat id to post summaries to
                                                # empty = skip notification POST
```

---

## New `SmolCrawler` method

```python
async def crawl_urls(self, urls: List[str]) -> List[Page]:
    """Crawl a specific list of URLs (no link following unless max_depth > 0)."""
```

This is a thin addition to `crawl.py` — seed the frontier with all given URLs
at depth 0, set effective `max_pages = len(urls) * (max_depth + 1)`.

---

## File-by-File Change Summary

| File | Change type | Description |
|---|---|---|
| `src/smolcrawl/watcher.py` | **New** | WatchEntry, WatchList, all 4 detectors, ChangeDetector orchestrator |
| `src/smolcrawl/scheduler.py` | **New** | UpdateSchedulerThread, OwuiNotifier |
| `src/smolcrawl/crawl.py` | **Extend** | Add `crawl_urls()` async method to `SmolCrawler` |
| `src/smolcrawl/__init__.py` | **Extend** | Export `WatchEntry`, `WatchList`, `UpdateSchedulerThread` |
| `integrations/open-webui/smolcrawl_pipeline.py` | **Extend** | Parse watch/unwatch/check/list commands; start/stop scheduler in on_startup/on_shutdown |

No existing behaviour is changed. The scheduler and watcher are additive.

---

## Implementation Order

1. `watcher.py` — WatchEntry + WatchList (data layer, no I/O side-effects)
2. `watcher.py` — detectors (RssDetector, SitemapDetector, EtagDetector, ChangelogDetector)
3. `crawl.py` — `crawl_urls()` method
4. `scheduler.py` — UpdateSchedulerThread + OwuiNotifier
5. `__init__.py` — exports
6. `smolcrawl_pipeline.py` — command parsing + scheduler wiring

---

## Open Questions / Deferred

- **Feed auto-discovery**: initial implementation requires an explicit `rss_url`
  or `changelog_url`; auto-probing of `<link rel="alternate">` / common paths
  is a nice-to-have for a follow-up.
- **Deleted pages**: if a URL disappears from the sitemap _and_ returns 404,
  it should be removed from the KB. Deferred to follow-up (needs a 404-aware
  `crawl_urls` pass).
- **OWUI channel auto-selection**: if `owui_notify_channel_id` is empty, a
  future improvement could query `/api/v1/chats/` and find a SmolCrawl-owned
  channel. For now, log-only if not configured.
