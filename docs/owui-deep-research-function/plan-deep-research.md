# Deep Research Pipeline — Plan

## Problem Statement

When a user queries a RAG-backed knowledge base, the quality of results is bounded by the user's vocabulary. If the user doesn't prompt with the exact term stored in the collection, relevant chunks are missed. An LLM can bridge this gap by propagating adjacent concepts, synonyms, and abstractions to pull a broader set of knowledge — but today there is no mechanism for this iterative expansion within Open WebUI.

Additionally, the crawl process that _builds_ these knowledge collections is currently user-directed. The user must supply seed URLs. An LLM can discover related domains and resources that the user wouldn't think to search for, widening the knowledge base before the iterative RAG loop even begins.

## Solution Overview

Two complementary components:

1. **Deep Research Function** (Open WebUI) — an OWUI **Function** (`class Tools`) that the user's selected LLM invokes via native function calling. Iteratively expands search terms across knowledge collections, persists a research journal to Fileshed, and returns a synthesized chain-of-thought answer.
2. **LLM-Guided Crawl Discovery** (SmolCrawl) — a crawl-time module that uses an LLM to evaluate discovered links and decide which adjacent domains to follow, expanding the crawl frontier intelligently.

```
User selects real LLM model + enables Deep Research function
    │
    ▼
┌──────────────────────────────────────────────────┐
│  LLM (e.g. llama3:70b)                          │
│  "The user wants deep research on X..."          │
│  → calls deep_research(query="X")                │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  Deep Research Function (class Tools)      │  │
│  │                                            │  │
│  │  1. Init Fileshed journal                  │  │
│  │  2. List collections → sub-agent ranks     │  │
│  │  3. Iteration loop:                        │  │
│  │     a. Query selected KBs (OWUI API)       │  │
│  │     b. Sub-agent extracts new terms        │  │
│  │     c. Write findings to Fileshed journal  │  │
│  │     d. Read back summaries for next iter   │  │
│  │  4. Sub-agent synthesizes via CoT          │  │
│  │  5. Return answer to outer LLM             │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  LLM presents synthesized answer to user         │
│  (can chain with Fileshed, Superpowers, etc.)    │
└──────────────────────────────────────────────────┘

SmolCrawl (build-time, separate Pipeline):
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

## Component 1: Deep Research

### LLM Engagement Architecture (Critical Design Decision)

Open WebUI has two extension types with fundamentally different LLM access:

| Type              | Class                           | LLM Present?                                 | User Selects As                 | Can Call Tools?              |
| ----------------- | ------------------------------- | -------------------------------------------- | ------------------------------- | ---------------------------- |
| **Pipeline**      | `class Pipeline` with `pipe()`  | **No** — pipeline _replaces_ the model       | A "model" in the model dropdown | No — it IS the model         |
| **Function/Tool** | `class Tools` with tool methods | **Yes** — runs inside a real model's context | Enabled alongside a model       | Yes — LLM calls the function |

The existing SmolCrawl Knowledge Builder is a **Pipeline**: the user selects it as a "model", types `crawl https://... into My KB`, and the pipeline handles everything. No LLM is in the loop — which is fine for crawling, where the workflow is deterministic.

Deep research **requires an LLM** for collection ranking, term expansion, continue-decisions, and synthesis. There are three approaches:

#### Option A: Pipeline + Hardcoded Model Valve (Current SmolCrawl Pattern)

The deep research pipeline replaces the model. A valve specifies which real LLM to call via `generate_chat_completion`. The pipeline orchestrates everything.

```
User selects "Deep Research" as model
  → Pipeline intercepts message
  → Pipeline calls LLM (specified in valve) via generate_chat_completion
  → Pipeline streams results back
```

**Problem**: The user must configure a `model_id` valve and cannot use the model they already have selected. The pipeline is an island — it can't leverage other Functions/Tools the user has enabled (Fileshed, Superpowers).

#### Option B: Function/Tool (Superpowers Pattern) ← RECOMMENDED

Deep research is a **Function** (`class Tools`). The user selects a real LLM model and enables the deep research function alongside it. The LLM can call `deep_research(query)` natively.

```
User selects "llama3:70b" as model
User enables: Deep Research, Fileshed, Superpowers (functions)
  → User types: "deep research: how does Blueprint replication work?"
  → LLM recognizes the tool call → invokes deep_research(query="...")
  → Function runs the iterative loop internally (sub-agent calls for each step)
  → Function returns structured result to the LLM
  → LLM presents the synthesized answer to the user
```

**Advantages**:

- LLM is present and engaged — it can reason about what to do
- Other Functions/Tools are accessible: the deep research function can call Fileshed operations programmatically, and the LLM can call Superpowers before/after
- The user doesn't need to switch "models" — they use their preferred LLM and toggle the function on
- Native function calling means the LLM decides when to invoke deep research vs. answering directly
- Matches the established pattern (Superpowers = `class Tools`, Fileshed = `class Tools`)

**Sub-agent pattern unchanged**: Inside the `deep_research()` tool method, the function still calls `generate_chat_completion` with `bypass_filter=True` for each reasoning step (collection ranking, term expansion, synthesis). The difference is that the outer LLM orchestrates _when_ to invoke the function, and the function orchestrates the internal multi-step loop.

#### Option C: Hybrid — Function for Research + Pipeline for Crawl

Keep SmolCrawl Knowledge Builder as a Pipeline (it doesn't need an LLM). Make deep research a Function. They coexist independently.

```
Pipeline: SmolCrawl Knowledge Builder  → user selects as model to crawl
Function: Deep Research                → user enables alongside a real model
Function: Fileshed                     → persistence (shared by both)
Function: Superpowers                  → spec/plan workflows
```

**This is the recommended architecture.** The crawl pipeline stays a pipeline (deterministic, no LLM needed). Deep research becomes a function (LLM-native, tool-calling, composable with other functions).

#### Chosen Approach: Option C (Hybrid)

```
┌─────────────────────────────────────────────────────────┐
│  User's Model Selection: e.g. "llama3:70b"              │
│                                                         │
│  Enabled Functions:                                     │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────────────┐│
│  │ Deep Research │ │ Fileshed │ │ Superpowers          ││
│  │ (class Tools) │ │ (Tools)  │ │ (Tools)              ││
│  └──────┬───────┘ └─────┬────┘ └──────────┬───────────┘│
│         │               │                  │            │
│         │    ┌──────────┴──────────┐       │            │
│         │    │ Shared Fileshed     │       │            │
│         └───►│ Storage Zone        │◄──────┘            │
│              │ deep-research/      │                    │
│              │ superpowers/        │                    │
│              └─────────────────────┘                    │
│                                                         │
│  Available Pipelines (separate model selection):        │
│  ┌────────────────────────┐                             │
│  │ SmolCrawl KB Builder   │ ← select as model to crawl │
│  │ (class Pipeline)       │                             │
│  └────────────────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

#### Function Signature

```python
class Tools:
    class Valves(BaseModel):
        max_iterations: int = 3
        fixed_iterations: int = 2
        top_k_per_collection: int = 5
        max_collections: int = 10
        owui_base_url: str = "http://openwebui:8080"
        owui_api_key: str = ""
        include_sources: bool = True
        fileshed_compatible: bool = True
        storage_base_path: str = "/app/backend/data/user_files"
        save_journal: bool = True

    def __init__(self):
        self.valves = self.Valves()

    async def deep_research(
        self,
        query: str,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: typing.Callable[[dict], typing.Any] = None,
        __request__=None,
        __model__: dict = None,
        __event_call__=None,
        __chat_id__: str = "",
        __message_id__: str = "",
    ) -> str:
        """
        Perform deep iterative research across all OWUI knowledge collections.
        Expands search terms using LLM reasoning to find context the user
        might not know to search for. Returns a synthesized answer with sources.

        Args:
            query: The research question or topic to investigate.
        """
        # 1. Initialize Fileshed journal
        # 2. List + rank collections (sub-agent call)
        # 3. Iterative RAG loop with term expansion (sub-agent calls)
        # 4. Chain-of-thought synthesis (sub-agent call)
        # 5. Return result to the outer LLM
```

The `__event_emitter__` provides streaming status updates to the user during the research loop (same mechanism Superpowers uses). The final return value is the synthesized answer, which the outer LLM can then present or build upon.

#### How the Outer LLM Engages

With native function calling enabled, the LLM sees the `deep_research()` tool description and can:

1. **Auto-invoke**: User says "research how Blueprint replication works" → LLM calls `deep_research(query="Blueprint replication")`
2. **Contextualize results**: The function returns the synthesis → the LLM can add its own commentary, answer follow-ups, or feed results into Superpowers
3. **Chain with other tools**: LLM calls `deep_research()`, then calls `shed_patch_text()` to save a summary, then calls `brainstorm()` to start a spec — all in one conversation
4. **Decide NOT to invoke**: For simple questions the LLM can answer directly, it skips deep research entirely

### Iteration Model

- **Fixed 2 iterations** by default.
- After iteration 2, the LLM evaluates whether a 3rd iteration would yield meaningful new information. If yes, it continues; if not, it synthesizes.
- A `max_iterations` valve caps the upper bound (default: 3).

### Pipeline Flow

```
Step 0 — Initialize Research Journal
│  Create session directory in Fileshed: deep-research/{timestamp}-{slug}/
│  Write 00-prompt.md: original query, timestamp, model, goal context
│  → Stream: "📋 Research session started — journal: deep-research/{slug}"
│
Step 1 — Collection Discovery
│  GET /api/v1/knowledge/  →  list all collections
│  LLM prompt: "Given this user query and these collection names/descriptions,
│               which are most likely relevant? Rank them."
│  Write 01-collections.md: all collections, LLM ranking + rationale
│  → Stream: "🔍 Searching [N] knowledge collections..."
│
Step 2 — Initial RAG Query + Journal Write
│  For each selected collection:
│    POST /api/v1/retrieval/query  →  top-K chunks
│  LLM summarizes findings + identifies new concepts
│  Write 02-iteration-1.md: terms, chunks, summary, new concepts
│  → Stream: "📚 Found [N] passages across [M] collections"
│
Step 3 — Term Expansion (Iteration 1)
│  Read back: 00-prompt.md + 02-iteration-1.md (summary section)
│  LLM prompt: "Given the original query and these findings,
│               what adjacent concepts, synonyms, or related terms
│               should we search for that the user might not have used?"
│  → New search terms generated
│  Re-query collections with expanded terms
│  Deduplicate against seen_chunks
│  LLM summarizes new findings
│  Write 03-iteration-2.md: expanded terms, new chunks, summary
│  → Stream: "🔄 Expanding: [term1], [term2] — [N] new passages found"
│
Step 4 — Continue Decision
│  Read back: summaries from all iteration files
│  LLM prompt: "Based on iterations 1-2, would a third pass likely
│               surface meaningfully new information? Answer YES/NO
│               with a one-line rationale."
│  Append decision to last iteration file
│  If YES → one more iteration (write 04-iteration-3.md)
│  → Stream: "🔄 Continuing — LLM detected untapped context..."
│    OR
│  → Stream: "✅ Search complete — synthesizing..."
│
Step 5 — Chain-of-Thought Synthesis
│  Read back: 00-prompt.md + all iteration summaries + top raw chunks
│  LLM prompt: "Reason step-by-step through the collected evidence.
│               Cite which iteration and collection each insight came from.
│               Then compose a comprehensive answer."
│  Write 05-synthesis.md: full CoT reasoning + final answer + sources
│  Write manifest.json: machine-readable session index
│  → Stream: chain-of-thought reasoning (abbreviated)
│  → Stream: final answer with inline source references
│  → Stream: "\n---\n📁 Full research journal: deep-research/{slug}/"
```

### Valve Configuration

No `trigger_prefix` needed — the LLM decides when to call `deep_research()` based on the tool description and native function calling.

| Valve                  | Type | Default                          | Description                                    |
| ---------------------- | ---- | -------------------------------- | ---------------------------------------------- |
| `max_iterations`       | int  | `3`                              | Hard cap on expansion iterations               |
| `fixed_iterations`     | int  | `2`                              | Guaranteed iterations before continue-decision |
| `top_k_per_collection` | int  | `5`                              | Chunks retrieved per collection per query      |
| `max_collections`      | int  | `10`                             | Max collections to search (LLM selects best)   |
| `owui_base_url`        | str  | `"http://openwebui:8080"`        | OWUI API base                                  |
| `owui_api_key`         | str  | `""`                             | Bearer token for OWUI API                      |
| `include_sources`      | bool | `True`                           | Append source references to final answer       |
| `fileshed_compatible`  | bool | `True`                           | Write journal to Fileshed Storage zone         |
| `storage_base_path`    | str  | `"/app/backend/data/user_files"` | Base path for Fileshed-compatible storage      |
| `save_journal`         | bool | `True`                           | Persist research journal to disk               |

### OWUI API Endpoints Used

| Endpoint                  | Method | Purpose                        |
| ------------------------- | ------ | ------------------------------ |
| `/api/v1/knowledge/`      | GET    | List all knowledge collections |
| `/api/v1/knowledge/{id}`  | GET    | Get collection metadata        |
| `/api/v1/retrieval/query` | POST   | RAG query against a collection |

### Sub-Agent Pattern (Internal LLM Calls)

The `deep_research()` tool method needs to make multiple internal LLM calls (collection ranking, term expansion, continue-decision, synthesis). These use `generate_chat_completion` with `bypass_filter=True` — the same pattern Superpowers uses in `_run_sub_agent`.

Because deep research is a **Function** (not a Pipeline), it runs inside the context of the user's selected model and receives `__metadata__` containing the active `model_id`. Sub-agent calls reuse that same model:

```python
async def _run_sub_agent(self, system_prompt, user_prompt, __request__, __user__, __metadata__, __model__):
    from open_webui.utils.chat import generate_chat_completion
    from open_webui.models.users import UserModel

    model_id = ((__metadata__ or {}).get("model") or {}).get("id", "") or (
        __model__ or {}
    ).get("id", "")

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
        bypass_filter=True,  # Prevents recursive function/filter invocation
    )
    return response["choices"][0]["message"]["content"]
```

The `bypass_filter=True` flag is critical — without it, the sub-agent call could re-trigger the deep research function, Superpowers, or other filters in an infinite loop.

```

### Fileshed as Research Journal (Working Memory)

Fileshed is **not** a final-step report dump. It is the pipeline's **active working memory** — a persistent research journal that accumulates findings throughout the entire process. This solves two problems:

1. **Context window overflow** — Instead of growing an in-memory context across iterations, each iteration's findings are written to disk. The LLM reads back only what it needs.
2. **Resumability and auditability** — The user (and the LLM) can review the full chain of reasoning at any point. If a chat session is lost, the research state survives on disk.

#### Journal Structure

Each research session creates a directory under the user's Fileshed Storage zone:

```

{STORAGE_BASE_PATH}/users/{user_id}/Storage/data/deep-research/
└── {timestamp}-{slug}/
├── 00-prompt.md ← Original user query + goal context
├── 01-collections.md ← Selected collections + LLM ranking rationale
├── 02-iteration-1.md ← Search terms, retrieved chunks, LLM summary
├── 03-iteration-2.md ← Expanded terms, new chunks, LLM summary
├── 04-iteration-3.md ← (if continue-decision = YES)
├── 05-synthesis.md ← Final chain-of-thought synthesis
└── manifest.json ← Machine-readable index of all files

````

#### What Gets Written at Each Step

| Step                 | File                            | Contents                                                                                                                 |
| -------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Activation           | `00-prompt.md`                  | Original query, timestamp, selected model                                                                                |
| Collection Discovery | `01-collections.md`             | All available collections, LLM's ranking + rationale for selections                                                      |
| Iteration N          | `0{N+1}-iteration-{N}.md`       | Search terms used, collections queried, retrieved chunks (full text), LLM's summary of findings, new concepts identified |
| Continue Decision    | appended to last iteration file | LLM's YES/NO rationale                                                                                                   |
| Synthesis            | `05-synthesis.md`               | Chain-of-thought reasoning over all iteration summaries, final answer, source citations                                  |
| Index                | `manifest.json`                 | `{session_id, query, iterations: [{file, terms, collections, chunk_count}], status}`                                     |

#### How the LLM Uses the Journal

At each iteration, the LLM does **not** receive the full accumulated raw chunks. Instead:

1. The pipeline reads back the **summaries** from previous iteration files (`0{N}-iteration-{N}.md` → extract the `## Summary` section).
2. These summaries + the original prompt (`00-prompt.md`) form the context for the next LLM call.
3. For **final synthesis**, the pipeline reads all iteration files and feeds the LLM:
   - The original prompt
   - Each iteration's summary (compact)
   - The top-scoring raw chunks across all iterations (selected by relevance score, capped to fit context)
   - Instruction: "Reason step-by-step through the collected evidence, then compose a comprehensive answer."

This produces a genuine **chain-of-thought** synthesis grounded in the accumulated evidence, not a single-shot answer from a bloated context window.

#### Fileshed File Operations

The pipeline writes to Fileshed using direct file I/O (same `_resolve_path` pattern as Superpowers):

```python
import os

def _write_journal_entry(self, session_dir: str, filename: str, content: str):
    """Write a research journal entry to Fileshed storage."""
    path = os.path.join(session_dir, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def _read_journal_entry(self, session_dir: str, filename: str) -> str:
    """Read back a journal entry for context building."""
    path = os.path.join(session_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def _resolve_session_dir(self, user_id: str, slug: str) -> str:
    """Resolve Fileshed-compatible path for this research session."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_name = f"{timestamp}-{slug}"
    if self.valves.fileshed_compatible and user_id:
        return os.path.join(
            self.valves.storage_base_path,
            "users", user_id, "Storage", "data",
            "deep-research", session_name
        )
    return os.path.join(
        self.valves.storage_base_path,
        "deep-research", session_name
    )
````

#### User Visibility

Because findings are written to the Fileshed Storage zone, the user can:

- Browse the research journal in Fileshed at any time during or after the research.
- Re-read iteration summaries to understand _why_ the LLM expanded in a particular direction.
- Use the journal as input for a Superpowers brainstorm session.
- Share the research directory with collaborators via Fileshed's group features.

### Integration with Superpowers

When the user is in a Superpowers brainstorm or spec phase:

- Superpowers can call deep research as a "gather prior art" step — the brainstorm tool can trigger the deep research pipeline to find relevant context from existing knowledge before generating a spec.
- The research journal in Fileshed serves as the shared artifact: Superpowers reads `deep-research/{session}/` to ground its spec in collected evidence.
- This is a future integration; v1 operates independently.

### Deduplication Strategy

Across iterations, the same chunks may surface under different search terms. The pipeline maintains a `seen_chunks: set[str]` keyed on `(collection_id, chunk_hash)` to avoid feeding duplicates into the journal. The `manifest.json` also tracks seen chunk hashes for cross-session deduplication.

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
├── smolcrawl_pipeline.py          ← existing crawl Pipeline (unchanged)
└── deep_research_function.py      ← NEW: deep research Function (class Tools)

src/smolcrawl/
├── crawl.py                       ← modified: LLM link evaluation hook
└── frontier/
    └── llm_evaluator.py           ← NEW: LLM-based link scoring
```

## Implementation Phases

### Phase 1: Deep Research Pipeline (OWUI)

1. Scaffold `deep_research_function.py` as `class Tools` with Valves
2. Implement `deep_research()` tool method with `__event_emitter__` streaming
3. Implement `_run_sub_agent()` for internal LLM calls (reuse Superpowers pattern)
4. Implement Fileshed journal initialization (`_resolve_session_dir`, `_write_journal_entry`)
5. Implement collection listing + LLM ranking → write `01-collections.md`
6. Implement RAG query loop with term expansion → write iteration files
7. Implement continue-decision logic with journal read-back
8. Implement chain-of-thought synthesis from journal entries → write `05-synthesis.md`
9. Streaming status via `__event_emitter__` + final return to outer LLM
10. Docker integration (add to existing `docker-compose.yml`)

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
