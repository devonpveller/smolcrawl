# Mercator-Style URL Frontier Implementation Plan

## Overview

This document outlines the implementation plan for upgrading SmolCrawler from a simple FIFO queue to a **Mercator-style URL Frontier** with multiple queues. This architecture is used by large-scale crawlers (Google, Bing, Internet Archive) to achieve:

- **True BFS traversal** with depth-based prioritization
- **Politeness** through per-host rate limiting
- **Scalability** for millions of URLs
- **Flexibility** for custom prioritization strategies

## Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SmolCrawler                          │
│  ┌─────────────┐     ┌─────────────┐    ┌───────────┐  │
│  │ asyncio     │────▶│  Fetcher    │───▶│ Extractor │  │
│  │ Queue       │     │  (httpx)    │    │           │  │
│  │ (FIFO)      │     └─────────────┘    └───────────┘  │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

**Limitations:**
- No depth tracking (approximate BFS)
- No per-host politeness (can overwhelm single hosts)
- No priority differentiation
- Single queue bottleneck

---

## Proposed Mercator Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              URL Frontier                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         FRONT QUEUES                                    │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │  │
│  │  │ Priority 0   │ │ Priority 1   │ │ Priority 2   │ │ Priority N   │   │  │
│  │  │ (Depth 0-1)  │ │ (Depth 2-3)  │ │ (Depth 4-5)  │ │ (Depth 6+)   │   │  │
│  │  │ High Priority│ │ Med Priority │ │ Low Priority │ │ Lowest       │   │  │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │  │
│  │         │                │                │                │           │  │
│  │         └────────────────┴────────────────┴────────────────┘           │  │
│  │                                  │                                      │  │
│  │                                  ▼                                      │  │
│  │                        ┌─────────────────┐                              │  │
│  │                        │  Front Queue    │                              │  │
│  │                        │  Selector       │                              │  │
│  │                        │  (Weighted)     │                              │  │
│  │                        └────────┬────────┘                              │  │
│  └─────────────────────────────────┼───────────────────────────────────────┘  │
│                                    │                                          │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐  │
│  │                         BACK QUEUES                                      │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │  │
│  │  │ Host Queue   │ │ Host Queue   │ │ Host Queue   │ │ Host Queue   │    │  │
│  │  │ example.com  │ │ docs.site.io │ │ api.dev.com  │ │ blog.org     │    │  │
│  │  │ next: 10:05  │ │ next: 10:06  │ │ next: 10:04  │ │ next: 10:07  │    │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘    │  │
│  │                                                                          │  │
│  │                        ┌─────────────────┐                               │  │
│  │                        │  Back Queue     │                               │  │
│  │                        │  Heap           │                               │  │
│  │                        │  (by next_time) │                               │  │
│  │                        └────────┬────────┘                               │  │
│  └─────────────────────────────────┼────────────────────────────────────────┘  │
│                                    │                                          │
│                                    ▼                                          │
│                          ┌─────────────────┐                                  │
│                          │    Fetcher      │                                  │
│                          │    Workers      │                                  │
│                          └─────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. URLEntry Data Model

```python
from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass(order=True)
class URLEntry:
    """A URL with metadata for frontier scheduling."""
    
    # Primary sort key (for priority queue)
    priority: int = field(compare=True)
    
    # Secondary sort key (FIFO within same priority)
    timestamp: float = field(default_factory=time.time, compare=True)
    
    # URL data (not used for comparison)
    url: str = field(compare=False)
    depth: int = field(default=0, compare=False)
    host: str = field(default="", compare=False)
    parent_url: Optional[str] = field(default=None, compare=False)
    
    # Retry tracking
    retries: int = field(default=0, compare=False)
    last_error: Optional[str] = field(default=None, compare=False)
```

### 2. Front Queue Manager

The front queues prioritize URLs by **importance** (depth, custom scoring).

```python
from collections import deque
from typing import Dict, List, Optional
import heapq

class FrontQueueManager:
    """Manages priority-based front queues for URL scheduling.
    
    URLs are distributed across queues by priority level.
    Lower priority number = higher importance = processed first.
    """
    
    def __init__(self, num_queues: int = 4, priority_weights: Optional[List[float]] = None):
        """
        Args:
            num_queues: Number of priority levels (default 4)
            priority_weights: Probability weights for queue selection
                              Default: [0.5, 0.3, 0.15, 0.05] (favor high priority)
        """
        self.num_queues = num_queues
        self.queues: List[deque] = [deque() for _ in range(num_queues)]
        self.priority_weights = priority_weights or self._default_weights(num_queues)
        self.total_urls = 0
    
    def _default_weights(self, n: int) -> List[float]:
        """Generate decreasing weights: [0.5, 0.3, 0.15, 0.05, ...]"""
        weights = [1.0 / (2 ** (i + 1)) for i in range(n)]
        # Normalize to sum to 1.0
        total = sum(weights)
        return [w / total for w in weights]
    
    def _depth_to_priority(self, depth: int) -> int:
        """Map crawl depth to priority queue index.
        
        Depth 0-1  -> Priority 0 (highest)
        Depth 2-3  -> Priority 1
        Depth 4-5  -> Priority 2
        Depth 6+   -> Priority 3 (lowest)
        """
        priority = min(depth // 2, self.num_queues - 1)
        return priority
    
    def add(self, entry: URLEntry) -> None:
        """Add a URL entry to the appropriate priority queue."""
        priority = self._depth_to_priority(entry.depth)
        entry.priority = priority
        self.queues[priority].append(entry)
        self.total_urls += 1
    
    def get(self) -> Optional[URLEntry]:
        """Get next URL using weighted random selection.
        
        Higher priority queues are selected more frequently,
        but lower priority queues still get some attention.
        """
        import random
        
        # Find non-empty queues
        available = [(i, q) for i, q in enumerate(self.queues) if q]
        if not available:
            return None
        
        # Weighted selection among available queues
        indices = [i for i, _ in available]
        weights = [self.priority_weights[i] for i in indices]
        
        # Normalize weights for available queues
        total_weight = sum(weights)
        normalized = [w / total_weight for w in weights]
        
        selected_idx = random.choices(indices, weights=normalized, k=1)[0]
        entry = self.queues[selected_idx].popleft()
        self.total_urls -= 1
        return entry
    
    def __len__(self) -> int:
        return self.total_urls
    
    def is_empty(self) -> bool:
        return self.total_urls == 0
```

### 3. Back Queue Manager (Politeness)

The back queues ensure **per-host rate limiting**.

```python
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Set
import heapq
import time
import asyncio

@dataclass(order=True)
class HostQueue:
    """Queue for a single host with timing information."""
    next_fetch_time: float = field(compare=True)
    host: str = field(compare=False)
    urls: deque = field(default_factory=deque, compare=False)
    
    def add(self, entry: URLEntry) -> None:
        self.urls.append(entry)
    
    def get(self) -> Optional[URLEntry]:
        return self.urls.popleft() if self.urls else None
    
    def is_empty(self) -> bool:
        return len(self.urls) == 0


class BackQueueManager:
    """Manages per-host queues with politeness delays.
    
    Each host gets its own queue with a minimum delay between requests.
    A heap tracks which host is ready for the next request.
    """
    
    def __init__(
        self,
        default_delay: float = 1.0,
        host_delays: Optional[Dict[str, float]] = None,
    ):
        """
        Args:
            default_delay: Default seconds between requests to same host
            host_delays: Custom delays for specific hosts
        """
        self.default_delay = default_delay
        self.host_delays = host_delays or {}
        
        # Host -> HostQueue mapping
        self.host_queues: Dict[str, HostQueue] = {}
        
        # Min-heap of (next_fetch_time, host) for scheduling
        self.schedule_heap: List[HostQueue] = []
        
        # Track hosts currently in heap (to avoid duplicates)
        self.hosts_in_heap: Set[str] = set()
        
        self.total_urls = 0
    
    def _get_delay(self, host: str) -> float:
        """Get the politeness delay for a host."""
        return self.host_delays.get(host, self.default_delay)
    
    def add(self, entry: URLEntry) -> None:
        """Add a URL to its host's queue."""
        host = entry.host
        
        if host not in self.host_queues:
            # New host - create queue, ready immediately
            host_queue = HostQueue(
                next_fetch_time=time.time(),
                host=host,
            )
            self.host_queues[host] = host_queue
        
        self.host_queues[host].add(entry)
        self.total_urls += 1
        
        # Add to heap if not already scheduled
        if host not in self.hosts_in_heap:
            heapq.heappush(self.schedule_heap, self.host_queues[host])
            self.hosts_in_heap.add(host)
    
    async def get(self) -> Optional[URLEntry]:
        """Get next URL respecting politeness delays.
        
        Waits if necessary until a host is ready.
        Returns None if all queues are empty.
        """
        while self.schedule_heap:
            # Peek at next ready host
            host_queue = self.schedule_heap[0]
            
            # Wait if not ready yet
            now = time.time()
            if host_queue.next_fetch_time > now:
                wait_time = host_queue.next_fetch_time - now
                await asyncio.sleep(wait_time)
            
            # Pop from heap
            heapq.heappop(self.schedule_heap)
            self.hosts_in_heap.discard(host_queue.host)
            
            # Get URL from host queue
            entry = host_queue.get()
            if entry is None:
                continue  # Queue was empty, try next host
            
            self.total_urls -= 1
            
            # Reschedule host if more URLs remain
            if not host_queue.is_empty():
                host_queue.next_fetch_time = time.time() + self._get_delay(host_queue.host)
                heapq.heappush(self.schedule_heap, host_queue)
                self.hosts_in_heap.add(host_queue.host)
            
            return entry
        
        return None
    
    def __len__(self) -> int:
        return self.total_urls
    
    def is_empty(self) -> bool:
        return self.total_urls == 0
```

### 4. URL Frontier (Orchestrator)

The main frontier that combines front and back queues.

```python
from urllib.parse import urlparse
from typing import Set, Optional
import asyncio

class URLFrontier:
    """Mercator-style URL Frontier combining priority and politeness.
    
    Flow:
    1. New URLs enter front queues (prioritized by depth/importance)
    2. Front queue selector picks next URL
    3. URL is routed to its host's back queue
    4. Back queue manager enforces per-host delays
    5. Ready URLs are dispatched to fetchers
    """
    
    def __init__(
        self,
        num_priority_levels: int = 4,
        default_host_delay: float = 1.0,
        max_urls: int = 100_000,
    ):
        self.front_queues = FrontQueueManager(num_queues=num_priority_levels)
        self.back_queues = BackQueueManager(default_delay=default_host_delay)
        
        # Deduplication
        self.seen_urls: Set[str] = set()
        self.max_urls = max_urls
        
        # Stats
        self.urls_added = 0
        self.urls_fetched = 0
        self.urls_deduplicated = 0
        
        # Background task to move URLs from front to back
        self._transfer_task: Optional[asyncio.Task] = None
        self._running = False
    
    def _extract_host(self, url: str) -> str:
        """Extract host from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def add(self, url: str, depth: int = 0, parent_url: Optional[str] = None) -> bool:
        """Add a URL to the frontier.
        
        Returns True if URL was added, False if deduplicated.
        """
        # Normalize URL
        url = normalize_url(url)
        
        # Deduplication
        if url in self.seen_urls:
            self.urls_deduplicated += 1
            return False
        
        if len(self.seen_urls) >= self.max_urls:
            return False  # Frontier full
        
        self.seen_urls.add(url)
        
        # Create entry and add to front queue
        entry = URLEntry(
            priority=0,  # Will be set by front queue
            url=url,
            depth=depth,
            host=self._extract_host(url),
            parent_url=parent_url,
        )
        
        self.front_queues.add(entry)
        self.urls_added += 1
        return True
    
    async def get(self) -> Optional[URLEntry]:
        """Get next URL to fetch, respecting priority and politeness."""
        # Transfer from front to back queues as needed
        while not self.back_queues.is_empty() or not self.front_queues.is_empty():
            # First, try to get from back queues (ready URLs)
            if not self.back_queues.is_empty():
                entry = await self.back_queues.get()
                if entry:
                    self.urls_fetched += 1
                    return entry
            
            # If back queues empty, transfer from front queues
            if not self.front_queues.is_empty():
                entry = self.front_queues.get()
                if entry:
                    self.back_queues.add(entry)
                continue
            
            break
        
        return None
    
    def is_empty(self) -> bool:
        return self.front_queues.is_empty() and self.back_queues.is_empty()
    
    def stats(self) -> dict:
        """Return frontier statistics."""
        return {
            "urls_added": self.urls_added,
            "urls_fetched": self.urls_fetched,
            "urls_deduplicated": self.urls_deduplicated,
            "front_queue_size": len(self.front_queues),
            "back_queue_size": len(self.back_queues),
            "seen_urls": len(self.seen_urls),
            "hosts_tracked": len(self.back_queues.host_queues),
        }
```

---

## Integration with SmolCrawler

### Updated SmolCrawler Class

```python
class SmolCrawler:
    """Mercator-style web crawler with URL frontier."""
    
    def __init__(
        self,
        max_pages: int = 500,
        max_concurrent: int = 10,
        host_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        num_priority_levels: int = 4,
        user_agent: str = "SmolCrawl/2.0",
    ):
        self.max_pages = max_pages
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        
        # Mercator-style frontier
        self.frontier = URLFrontier(
            num_priority_levels=num_priority_levels,
            default_host_delay=host_delay,
            max_urls=max_pages * 10,  # Allow buffer for discovered URLs
        )
        
        # Results
        self.pages: List[Page] = []
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _worker(self, client: httpx.AsyncClient, base_url: str):
        """Worker that fetches URLs from frontier."""
        while len(self.pages) < self.max_pages:
            entry = await self.frontier.get()
            if entry is None:
                break
            
            async with self.semaphore:
                await self._process_url(client, entry, base_url)
    
    async def _process_url(
        self, 
        client: httpx.AsyncClient, 
        entry: URLEntry, 
        base_url: str
    ):
        """Fetch and process a single URL."""
        html = await self._fetch_url(client, entry.url)
        if not html:
            return
        
        # Extract content
        page = extract_from_html(entry.url, html)
        if page:
            self.pages.append(page)
            logger.debug(f"[Depth {entry.depth}] {page.title[:40]}... ({entry.url})")
        
        # Discover links and add to frontier (depth + 1)
        if len(self.pages) < self.max_pages:
            links = extract_links(html, entry.url)
            for link in links:
                if is_same_domain(link, base_url):
                    self.frontier.add(
                        url=link,
                        depth=entry.depth + 1,
                        parent_url=entry.url,
                    )
    
    async def crawl(self, start_url: str) -> List[Page]:
        """Start crawling from the given URL."""
        logger.info(f"Starting Mercator crawl of {start_url}")
        start_time = time.time()
        
        # Seed the frontier
        self.frontier.add(start_url, depth=0)
        
        # Configure client
        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            http2=True,
        ) as client:
            
            # Run workers
            workers = [
                asyncio.create_task(self._worker(client, start_url))
                for _ in range(self.max_concurrent)
            ]
            
            await asyncio.gather(*workers, return_exceptions=True)
        
        elapsed = time.time() - start_time
        stats = self.frontier.stats()
        logger.success(
            f"Crawled {len(self.pages)} pages in {elapsed:.1f}s | "
            f"Deduped: {stats['urls_deduplicated']} | "
            f"Hosts: {stats['hosts_tracked']}"
        )
        
        return self.pages
```

---

## Implementation Phases

### Phase 1: Core Data Structures (2-3 hours)
- [ ] Implement `URLEntry` dataclass
- [ ] Implement `FrontQueueManager` with priority queues
- [ ] Unit tests for front queue operations

### Phase 2: Back Queue Politeness (2-3 hours)
- [ ] Implement `HostQueue` dataclass
- [ ] Implement `BackQueueManager` with per-host delays
- [ ] Implement heap-based scheduling
- [ ] Unit tests for politeness timing

### Phase 3: URL Frontier Integration (2-3 hours)
- [ ] Implement `URLFrontier` orchestrator
- [ ] Add deduplication with seen set
- [ ] Add statistics tracking
- [ ] Integration tests

### Phase 4: SmolCrawler Upgrade (2-3 hours)
- [ ] Update `SmolCrawler` to use frontier
- [ ] Add depth tracking to extracted links
- [ ] Update logging to show depth/priority info
- [ ] End-to-end tests

### Phase 5: Advanced Features (Optional, 3-4 hours)
- [ ] Bloom filter for deduplication at scale
- [ ] robots.txt respect per host
- [ ] Custom priority scoring (not just depth)
- [ ] Persistent frontier (resume interrupted crawls)
- [ ] DNS caching and prefetching

---

## Configuration Options

```python
# Example configuration
crawler = SmolCrawler(
    max_pages=1000,
    max_concurrent=20,
    
    # Mercator-specific options
    host_delay=1.0,              # Seconds between requests to same host
    num_priority_levels=4,        # Number of front queue priority levels
    priority_weights=[0.5, 0.3, 0.15, 0.05],  # Queue selection weights
    
    # Optional host-specific delays
    host_delays={
        "api.example.com": 2.0,   # More polite to API
        "static.cdn.com": 0.1,    # Less delay for CDN
    },
)
```

---

## Testing Strategy

### Unit Tests

```python
def test_front_queue_priority_ordering():
    """URLs are distributed by depth to correct priority queues."""
    fq = FrontQueueManager(num_queues=4)
    
    fq.add(URLEntry(priority=0, url="http://a.com", depth=0))  # Priority 0
    fq.add(URLEntry(priority=0, url="http://b.com", depth=3))  # Priority 1
    fq.add(URLEntry(priority=0, url="http://c.com", depth=6))  # Priority 3
    
    assert len(fq.queues[0]) == 1  # depth 0
    assert len(fq.queues[1]) == 1  # depth 3
    assert len(fq.queues[3]) == 1  # depth 6


async def test_back_queue_politeness():
    """Per-host delays are respected."""
    bq = BackQueueManager(default_delay=0.5)
    
    bq.add(URLEntry(priority=0, url="http://a.com/1", host="a.com"))
    bq.add(URLEntry(priority=0, url="http://a.com/2", host="a.com"))
    
    start = time.time()
    await bq.get()  # Immediate
    await bq.get()  # Should wait 0.5s
    elapsed = time.time() - start
    
    assert 0.4 < elapsed < 0.6  # ~0.5 second delay


async def test_frontier_deduplication():
    """Duplicate URLs are rejected."""
    frontier = URLFrontier()
    
    assert frontier.add("http://example.com/page") == True
    assert frontier.add("http://example.com/page") == False  # Duplicate
    assert frontier.stats()["urls_deduplicated"] == 1
```

### Integration Tests

```python
async def test_bfs_order():
    """Pages are crawled in breadth-first order."""
    crawler = SmolCrawler(max_pages=20, host_delay=0.1)
    pages = await crawler.crawl("http://test-site.local")
    
    # Verify depth ordering
    depths = [get_depth_for_url(p.url) for p in pages]
    assert depths == sorted(depths), "Pages should be in BFS order"
```

---

## Performance Considerations

| Aspect | Simple Queue | Mercator Frontier |
|--------|--------------|-------------------|
| Memory | O(n) URLs | O(n) URLs + O(h) hosts |
| Add URL | O(1) | O(log h) heap push |
| Get URL | O(1) | O(log h) heap pop |
| Dedup Check | O(1) set | O(1) set or Bloom |
| Politeness | None | O(log h) per request |

Where `n` = number of URLs, `h` = number of unique hosts.

For most crawls (< 100k URLs, < 1000 hosts), overhead is negligible.

---

## References

1. **Mercator Paper**: "Mercator: A Scalable, Extensible Web Crawler" (Heydon & Najork, 1999)
2. **IRLbot Paper**: "IRLbot: Scaling to 6 Billion Pages and Beyond" (Lee et al., 2008)
3. **Scrapy Architecture**: https://docs.scrapy.org/en/latest/topics/architecture.html
4. **Heritrix Frontier**: https://heritrix.readthedocs.io/en/latest/

---

## File Locations

After implementation, the new files will be:

```
src/smolcrawl/
├── crawl.py              # Updated SmolCrawler class
├── frontier/
│   ├── __init__.py       # Exports URLFrontier
│   ├── models.py         # URLEntry dataclass
│   ├── front_queues.py   # FrontQueueManager
│   ├── back_queues.py    # BackQueueManager
│   └── frontier.py       # URLFrontier orchestrator
├── db.py
└── utils.py

tests/
├── test_frontier/
│   ├── test_front_queues.py
│   ├── test_back_queues.py
│   └── test_frontier.py
└── test_crawl.py
```
