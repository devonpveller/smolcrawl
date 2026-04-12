# LLM-Guided Crawl Discovery — Plan

## Problem

SmolCrawl's crawler currently follows links within configured domain rules. When crawling documentation, the user must pre-supply every seed URL or rely on same-domain link following. Valuable related resources on other domains (tutorials, API references, community wikis, related libraries) are invisible unless the user manually adds them.

An LLM can evaluate discovered outbound links during the crawl and suggest which cross-domain resources are worth following — but the **user must approve** before any new domain is crawled.

## Design

### Where It Fits

This runs **during crawl**, integrated into the existing Mercator-style URL frontier. It is not a pre-crawl phase; it operates on links the crawler actually discovers in page content.

```
Crawl Loop (existing)
    │
    ├── Same-domain links → frontier (unchanged)
    │
    └── Cross-domain links → LLM Evaluator (NEW)
                                │
                                ├── Score + rationale
                                │
                                ▼
                         User Approval Queue
                                │
                           ┌────┴────┐
                           │  User   │
                           │ reviews │
                           │ in chat │
                           └────┬────┘
                                │
                         Approved URLs → frontier
```

### LLM Evaluator (`frontier/llm_evaluator.py`)

A new module that:

1. Receives batches of outbound cross-domain URLs (collected during crawl).
2. Sends them to an LLM with the crawl goal/topic for relevance scoring.
3. Returns scored URLs with rationales.

```python
@dataclass
class EvaluatedLink:
    url: str
    score: float          # 0.0–1.0 relevance to crawl goal
    rationale: str        # LLM's one-line explanation
    source_page: str      # Page where the link was found
    domain: str           # Extracted domain

@dataclass
class EvaluatorConfig:
    llm_base_url: str = "http://openwebui:8080"  # OWUI model endpoint
    llm_api_key: str = ""
    model_id: str = ""                            # Uses OWUI's selected model
    batch_size: int = 20                          # Links per LLM call
    min_score: float = 0.6                        # Threshold for user presentation
    crawl_goal: str = ""                          # User-supplied topic description
```

### LLM Prompt Design

```
System: You are a web crawl advisor. Given a crawl goal and a list of
outbound URLs discovered during crawling, score each URL's relevance
to the goal from 0.0 (irrelevant) to 1.0 (highly relevant).

Crawl Goal: {crawl_goal}

Current crawl seed: {seed_url}
Already crawling domains: {current_domains}

Discovered outbound links (found on {source_page}):
{url_list}

For each URL, respond in JSON:
[
  {"url": "...", "score": 0.8, "rationale": "Official API reference for the library"},
  {"url": "...", "score": 0.2, "rationale": "Marketing page, unlikely to have technical content"}
]

Only include URLs scoring >= 0.4. Omit clearly irrelevant links (social media, ads, tracking).
```

### User Approval Flow

The LLM evaluator does **not** add URLs to the frontier directly. Instead:

1. Scored URLs (above `min_score`) are placed in an **approval queue**.
2. The approval queue is presented to the user for review.
3. The user can: approve all, approve selectively, or skip.
4. Only approved URLs enter the frontier.

#### OWUI Pipeline Mode (Interactive)

When running via the SmolCrawl Knowledge Builder pipeline in OWUI chat:

```
📡 Crawl discovered 8 potentially relevant external links:

 ✅ [0.92] docs.unrealengine.com/5.4/api/
    "Official UE5.4 C++ API reference — directly related to Blueprint docs"
    Found on: docs.unrealengine.com/5.4/en-US/blueprints/

 ✅ [0.85] benui.ca/unreal/
    "Community UE tutorials covering Blueprint patterns"
    Found on: docs.unrealengine.com/5.4/en-US/community/

 ⚠️ [0.67] www.youtube.com/playlist?list=PLZlv_N0_O1gb...
    "UE5 Blueprint tutorial playlist — video content, may not extract well"
    Found on: docs.unrealengine.com/5.4/en-US/learning/

 ⬚ [0.61] forums.unrealengine.com/t/blueprint-best-practices
    "Forum thread — may contain useful patterns but noisy"
    Found on: docs.unrealengine.com/5.4/en-US/blueprints/

Reply with numbers to approve (e.g., "1,2") or "all" / "skip":
```

The pipeline waits for the user's next message, then adds approved URLs to the crawl.

#### CLI Mode (Batch)

When running via `doc_processor.py`:

```
Discovered 8 cross-domain links (scored by LLM):

  [1] 0.92  docs.unrealengine.com/5.4/api/
             "Official UE5.4 C++ API reference"
  [2] 0.85  benui.ca/unreal/
             "Community UE tutorials"
  [3] 0.67  www.youtube.com/playlist?list=...
             "UE5 Blueprint tutorial playlist"
  [4] 0.61  forums.unrealengine.com/t/blueprint-best-practices
             "Forum thread"

Approve which? [1,2,3,4/all/skip]:
```

### Integration Points

#### With `crawl.py`

The crawler's link extraction phase gains a hook:

```python
# In crawl loop, after extracting links from a page:
same_domain_links, cross_domain_links = partition_links(links, seed_domain)

# Same-domain: add to frontier as before
for link in same_domain_links:
    frontier.add(link)

# Cross-domain: batch for LLM evaluation
if cross_domain_links and llm_evaluator:
    llm_evaluator.add_batch(cross_domain_links, source_page=current_url)
```

#### With `frontier/`

The existing Mercator frontier is unchanged. Approved URLs simply enter via `frontier.add()` like any other URL, but with a new domain registered in the back queues.

#### With OWUI Pipeline

The existing `smolcrawl_pipeline.py` gains an optional phase between crawl and upload:

```
Phase 1: Crawl (existing) — with LLM evaluator active
Phase 1.5: User Approval (NEW) — present discovered links, wait for reply
Phase 1b: Extended Crawl (NEW) — crawl approved domains
Phase 2: Augment (existing)
Phase 3: Upload (existing)
```

### Batching Strategy

To avoid calling the LLM for every single outbound link:

1. Cross-domain links accumulate in a buffer.
2. When the buffer reaches `batch_size` (default 20) OR the crawl completes the current domain, the buffer is flushed to the LLM.
3. Multiple batches may produce multiple approval prompts during a long crawl.
4. A `max_approval_prompts` valve (default 3) limits interruptions.

### Configuration

Added to `ProcessingConfig` (doc_processor.py) and pipeline Valves:

| Setting                     | Type  | Default | Description                         |
| --------------------------- | ----- | ------- | ----------------------------------- |
| `enable_llm_discovery`      | bool  | `False` | Enable LLM link evaluation          |
| `crawl_goal`                | str   | `""`    | Topic description for LLM scoring   |
| `llm_discovery_batch_size`  | int   | `20`    | Links per LLM evaluation call       |
| `llm_discovery_min_score`   | float | `0.6`   | Minimum score for user presentation |
| `llm_discovery_max_prompts` | int   | `3`     | Max user approval interruptions     |
| `llm_base_url`              | str   | `""`    | LLM endpoint (defaults to OWUI)     |
| `llm_api_key`               | str   | `""`    | LLM auth token                      |

## Implementation Steps

1. **`frontier/llm_evaluator.py`** — `LinkEvaluator` class with `add_batch()`, `evaluate()`, `get_pending_approvals()`
2. **`crawl.py` hook** — partition links, route cross-domain to evaluator
3. **Approval queue** — thread-safe queue bridging evaluator → user interaction
4. **OWUI pipeline integration** — approval prompt in chat, wait for reply
5. **CLI integration** — `input()` prompt in `doc_processor.py`
6. **Tests** — mock LLM responses, verify scoring/filtering/approval flow
