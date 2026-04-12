# Deep Research Pipeline — Plan

## Problem Statement

When a user queries a RAG-backed knowledge base, the quality of results is bounded by the user's vocabulary. If the user doesn't prompt with the exact term stored in the collection, relevant chunks are missed. An LLM can bridge this gap by propagating adjacent concepts, synonyms, and abstractions to pull a broader set of knowledge — but today there is no mechanism for this iterative expansion within Open WebUI.

Additionally, the crawl process that _builds_ these knowledge collections is currently user-directed. The user must supply seed URLs. An LLM can discover related domains and resources that the user wouldn't think to search for, widening the knowledge base before the iterative RAG loop even begins.

## Solution Overview

Two complementary components:

1. **Deep Research Pipeline** (Open WebUI) — an OWUI Pipeline that intercepts queries, iteratively expands search terms across knowledge collections, and streams a synthesized answer with full provenance.
2. **LLM-Guided Crawl Discovery** (SmolCrawl) — a crawl-time module that uses an LLM to evaluate discovered links and decide which adjacent domains to follow, expanding the crawl frontier intelligently.

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  Deep Research Pipeline (OWUI)  │
│                                 │
│  1. List all knowledge          │
│     collections (OWUI API)      │
│  2. LLM picks relevant ones     │
│  3. Iteration loop:             │
│     a. Query selected KBs       │
│     b. LLM extracts new terms   │
│     c. Re-query with expansions │
│  4. Synthesize + stream answer  │
└─────────────────────────────────┘

SmolCrawl (build-time):
┌─────────────────────────────────┐
│  LLM-Guided Crawl Discovery     │
│                                 │
│  During crawl:                  │
│  1. LLM evaluates discovered    │
│     links against crawl goal    │
│  2. Scores relevance            │
│  3. Proposes discovered URLs    │
│     to user for approval        │
│  4. User approves → crawl       │
│     continues to new domains    │
└─────────────────────────────────┘
```

## Component 1: Deep Research Pipeline

### Architecture

The pipeline is an OWUI **Pipeline** (intercepts messages, streams responses). It lives alongside the existing SmolCrawl Knowledge Builder pipeline but serves the opposite direction: _reading_ from knowledge collections instead of _writing_ to them.

**Activation**: User prefixes query with a trigger phrase (e.g., `deep research: <query>` or `/research <query>`).

### Iteration Model

- **Fixed 2 iterations** by default.
- After iteration 2, the LLM evaluates whether a 3rd iteration would yield meaningful new information. If yes, it continues; if not, it synthesizes.
- A `max_iterations` valve caps the upper bound (default: 3).

### Pipeline Flow

```
Step 1 — Collection Discovery
│  GET /api/v1/knowledge/  →  list all collections
│  LLM prompt: "Given this user query and these collection names/descriptions,
│               which are most likely relevant? Rank them."
│  → Stream: "🔍 Searching [N] knowledge collections..."
│
Step 2 — Initial RAG Query
│  For each selected collection:
│    POST /api/v1/retrieval/query  →  top-K chunks
│  Combine chunks into context window
│  → Stream: "📚 Found [N] relevant passages across [M] collections"
│
Step 3 — Term Expansion (Iteration 1)
│  LLM prompt: "Given the original query and these retrieved passages,
│               what adjacent concepts, synonyms, or related terms
│               should we search for that the user might not have used?"
│  → New search terms generated
│  → Stream: "🔄 Expanding search: [term1], [term2], [term3]..."
│  Re-query collections with expanded terms
│  Deduplicate against already-seen chunks
│
Step 4 — Term Expansion (Iteration 2)
│  Same as Step 3 with cumulative context
│  → Stream: "🔄 Iteration 2: [term4], [term5]..."
│
Step 5 — Continue Decision
│  LLM prompt: "Based on iterations 1-2, would a third pass likely
│               surface meaningfully new information? Answer YES/NO
│               with a one-line rationale."
│  If YES → one more iteration (Step 3 logic)
│  → Stream: "🔄 Continuing — LLM detected untapped context..."
│    OR
│  → Stream: "✅ Search complete — synthesizing answer..."
│
Step 6 — Synthesis
│  LLM prompt: full accumulated context + original query
│  → "Compose a comprehensive answer citing sources."
│  → Stream: final answer with inline source references
│  → Stream: "\n---\n**Sources:** [list of collection/chunk refs]"
```

### Valve Configuration

| Valve                  | Type | Default                   | Description                                    |
| ---------------------- | ---- | ------------------------- | ---------------------------------------------- |
| `trigger_prefix`       | str  | `"deep research:"`        | Message prefix that activates the pipeline     |
| `max_iterations`       | int  | `3`                       | Hard cap on expansion iterations               |
| `fixed_iterations`     | int  | `2`                       | Guaranteed iterations before continue-decision |
| `top_k_per_collection` | int  | `5`                       | Chunks retrieved per collection per query      |
| `max_collections`      | int  | `10`                      | Max collections to search (LLM selects best)   |
| `owui_base_url`        | str  | `"http://openwebui:8080"` | OWUI API base                                  |
| `owui_api_key`         | str  | `""`                      | Bearer token for OWUI API                      |
| `include_sources`      | bool | `True`                    | Append source references to final answer       |

### OWUI API Endpoints Used

| Endpoint                  | Method | Purpose                        |
| ------------------------- | ------ | ------------------------------ |
| `/api/v1/knowledge/`      | GET    | List all knowledge collections |
| `/api/v1/knowledge/{id}`  | GET    | Get collection metadata        |
| `/api/v1/retrieval/query` | POST   | RAG query against a collection |

### Sub-Agent Pattern

Following the pattern established by **Superpowers** (`_run_sub_agent`), each LLM call (collection ranking, term expansion, continue-decision, synthesis) is a sub-agent invocation using `generate_chat_completion` with `bypass_filter=True`. This avoids recursive pipeline triggering and allows the pipeline to use the user's currently selected model.

```python
# Pattern from Superpowers — reused for all LLM calls
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import UserModel

response = await generate_chat_completion(
    request=__request__,
    form_data={
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "metadata": {"task": "deep_research_sub_agent"},
    },
    user=UserModel(**__user__),
    bypass_filter=True,
)
```

### Integration with Existing Functions

#### Fileshed Integration (Persistence)

Research results can be persisted to Fileshed for later reference:

- After synthesis, the pipeline writes the full research report (query + iterations + sources + synthesis) to `{STORAGE_BASE_PATH}/users/{user_id}/Storage/data/deep-research/{timestamp}-{slug}.md`.
- If Fileshed is installed, reports appear in the user's Fileshed Storage zone automatically.
- Controlled by a `save_to_fileshed` valve (default: `True`).
- The report includes iteration metadata (which terms were expanded, which collections contributed).

#### Superpowers Integration (Spec/Plan Workflows)

When the user is in a Superpowers brainstorm or spec phase:

- Superpowers can call deep research as a "gather prior art" step — the brainstorm tool can trigger the deep research pipeline to find relevant context from existing knowledge before generating a spec.
- This is a future integration; v1 operates independently.

### Deduplication Strategy

Across iterations, the same chunks may surface under different search terms. The pipeline maintains a `seen_chunks: set[str]` keyed on `(collection_id, chunk_hash)` to avoid feeding duplicates into synthesis context.

### Context Window Management

With multiple iterations across multiple collections, context can overflow. Strategy:

1. Each iteration's retrieved chunks are **summarized** by the LLM before being added to the cumulative context.
2. Only the summaries (not raw chunks) carry forward between iterations.
3. For final synthesis, the top chunks (by relevance score) from ALL iterations are included alongside the iteration summaries.

## Component 2: LLM-Guided Crawl Discovery (SmolCrawl)

See [plan-llm-crawl-discovery.md](plan-llm-crawl-discovery.md) for full details.

### Summary

During crawling, SmolCrawl's frontier encounters outgoing links. Today these are filtered by domain rules. With LLM-guided discovery:

1. The crawler collects outgoing links that leave the seed domain.
2. Periodically (batch of N links), the LLM evaluates them against the crawl goal.
3. **Approved links are presented to the user** in the OWUI chat (or CLI) for confirmation before being added to the frontier.
4. The user can approve all, selectively approve, or skip.
5. Approved URLs enter the frontier and are crawled normally.

This "human-in-the-loop" step ensures the user maintains control over what gets crawled and added to their knowledge collections.

## File Layout

```
docs/owui-deep-research-function/
├── plan-deep-research.md          ← this file
├── plan-llm-crawl-discovery.md    ← SmolCrawl LLM frontier component
└── reference-owui-retrieval-api.md ← OWUI retrieval API patterns

integrations/open-webui/
├── smolcrawl_pipeline.py          ← existing crawl pipeline (unchanged)
└── deep_research_pipeline.py      ← NEW: deep research pipeline

src/smolcrawl/
├── crawl.py                       ← modified: LLM link evaluation hook
└── frontier/
    └── llm_evaluator.py           ← NEW: LLM-based link scoring
```

## Implementation Phases

### Phase 1: Deep Research Pipeline (OWUI)

1. Scaffold `deep_research_pipeline.py` with Valves, trigger detection
2. Implement collection listing + LLM ranking
3. Implement RAG query loop with term expansion
4. Implement continue-decision logic
5. Implement streaming synthesis with source references
6. Add Fileshed persistence (optional)
7. Docker integration (add to existing `docker-compose.yml`)

### Phase 2: LLM-Guided Crawl Discovery (SmolCrawl)

1. Create `frontier/llm_evaluator.py` with link scoring
2. Hook into `crawl.py` to collect outbound cross-domain links
3. Implement user approval flow (OWUI chat + CLI modes)
4. Integrate approved URLs back into frontier
5. Tests for LLM evaluator (mocked LLM responses)

### Phase 3: Integration

1. Connect crawl discovery → knowledge collection → deep research loop
2. End-to-end test: crawl new docs → research across updated collections
3. Superpowers integration (brainstorm → deep research → spec)
