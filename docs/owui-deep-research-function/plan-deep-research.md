# Deep Research Pipeline — Plan

## Problem Statement

When a user queries a RAG-backed knowledge base, the quality of results is bounded by the user's vocabulary. If the user doesn't prompt with the exact term stored in the collection, relevant chunks are missed. An LLM can bridge this gap by propagating adjacent concepts, synonyms, and abstractions to pull a broader set of knowledge — but today there is no mechanism for this iterative expansion within Open WebUI.

Additionally, the crawl process that _builds_ these knowledge collections is currently user-directed. The user must supply seed URLs. An LLM can discover related domains and resources that the user wouldn't think to search for, widening the knowledge base before the iterative RAG loop even begins.

## Solution Overview

A single **Deep Research Function** (`class Tools`) that closes the entire loop:

1. **Domain Discovery** — Uses OWUI's web search tools to find relevant domains for a topic
2. **User Approval** — Presents discovered domains to the user, awaits confirmation, accepts additions
3. **Knowledge Collection Building** — Calls the SmolCrawl pipeline container to crawl approved domains into OWUI knowledge collections
4. **Iterative RAG Research** — Expands search terms across the newly-built (and existing) collections
5. **Chain-of-Thought Synthesis** — Produces a grounded answer from accumulated evidence

All orchestrated by the user's selected LLM through native function calling.

```
User selects real LLM + enables Deep Research function
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  LLM (e.g. llama3:70b)                                         │
│  → calls deep_research(query="how does Blueprint replication    │
│    work in UE5?")                                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Deep Research Function (class Tools)                    │   │
│  │                                                          │   │
│  │  Phase A: Domain Discovery                               │   │
│  │  ├─ Sub-agent uses web search to find relevant domains   │   │
│  │  ├─ Present domains to user for approval                 │   │
│  │  ├─ User approves / adds / skips                         │   │
│  │  └─ Write 01-domains.md to journal                       │   │
│  │                                                          │   │
│  │  Phase B: Knowledge Collection Building                  │   │
│  │  ├─ For each approved domain:                            │   │
│  │  │   POST to SmolCrawl container (9099)                  │   │
│  │  │   → crawl + augment + upload to OWUI KB               │   │
│  │  ├─ Stream crawl progress to user                        │   │
│  │  └─ Write 02-crawl-status.md to journal                  │   │
│  │                                                          │   │
│  │  Phase C: Iterative RAG Research                         │   │
│  │  ├─ Query new + existing collections                     │   │
│  │  ├─ LLM expands terms, re-queries (2+1 iterations)      │   │
│  │  └─ Write iteration files to journal                     │   │
│  │                                                          │   │
│  │  Phase D: Chain-of-Thought Synthesis                     │   │
│  │  ├─ Read journal summaries + top chunks                  │   │
│  │  ├─ CoT reasoning → final answer                         │   │
│  │  └─ Write 0N-synthesis.md to journal                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  LLM presents result (can chain with Fileshed, Superpowers)     │
└─────────────────────────────────────────────────────────────────┘

Infrastructure:
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  SmolCrawl Pipelines        │     │  Open WebUI                 │
│  Container (port 9099)      │     │  (port 3000/8080)           │
│                             │     │                             │
│  • crawl + augment + upload │◄────│  • Knowledge collections    │
│  • Already running          │     │  • RAG retrieval API        │
│  • HTTP API via Pipelines   │     │  • Web search tools         │
└─────────────────────────────┘     └─────────────────────────────┘
```

## Component 1: Deep Research

### LLM Engagement Architecture

Open WebUI has two extension types with fundamentally different LLM access:

| Type              | Class                           | LLM Present?                                 | User Selects As                 | Can Call Tools?              |
| ----------------- | ------------------------------- | -------------------------------------------- | ------------------------------- | ---------------------------- |
| **Pipeline**      | `class Pipeline` with `pipe()`  | **No** — pipeline _replaces_ the model       | A "model" in the model dropdown | No — it IS the model         |
| **Function/Tool** | `class Tools` with tool methods | **Yes** — runs inside a real model's context | Enabled alongside a model       | Yes — LLM calls the function |

The existing SmolCrawl Knowledge Builder is a **Pipeline** — it runs in a Docker container (`smolcrawl-pipelines:9099`) and handles crawl → augment → upload deterministically. No LLM needed.

Deep research needs:

- An LLM for reasoning (term expansion, synthesis)
- Access to OWUI web search tools for domain discovery
- The ability to **call the SmolCrawl container** to build knowledge collections
- Composability with Fileshed and Superpowers

**Therefore: Deep Research is a Function (`class Tools`).**

The SmolCrawl pipeline container remains a Pipeline — the Function calls it over HTTP when it needs to build knowledge collections. This is the key insight: **the Function is the orchestrator, the Pipeline is the worker.**

```
┌─────────────────────────────────────────────────────────┐
│  User's Model Selection: e.g. "llama3:70b"              │
│                                                         │
│  Enabled Functions (class Tools):                       │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────────────┐│
│  │ Deep Research │ │ Fileshed │ │ Superpowers          ││
│  │              │ │          │ │                      ││
│  │ • web search │ │ • store  │ │ • spec/plan          ││
│  │ • crawl via  │ │ • read   │ │ • brainstorm         ││
│  │   SmolCrawl  │ │          │ │                      ││
│  │ • RAG query  │ │          │ │                      ││
│  │ • synthesize │ │          │ │                      ││
│  └──────┬───────┘ └─────┬────┘ └──────────────────────┘│
│         │               │                               │
│         │  ┌────────────┴──────────┐                    │
│         ├─►│ Fileshed Storage Zone │                    │
│         │  │ deep-research/        │                    │
│         │  └───────────────────────┘                    │
│         │                                               │
│         │  HTTP call to SmolCrawl container              │
│         ▼                                               │
│  ┌────────────────────────────────┐                     │
│  │ SmolCrawl Pipelines (9099)    │                     │
│  │ (class Pipeline — no LLM)     │                     │
│  │ crawl → augment → upload KB   │                     │
│  └────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### How the Function Calls SmolCrawl

The SmolCrawl pipeline container runs the OWUI Pipelines server at port 9099. The deep research function triggers crawls by sending messages to it via the Pipelines HTTP API:

```python
async def _trigger_crawl(self, domain: str, kb_name: str) -> dict:
    """Call SmolCrawl pipeline container to crawl a domain into a KB.

    The Pipelines server at smolcrawl_url exposes pipe() over HTTP.
    We send the same message format a user would type in chat.
    """
    async with httpx.AsyncClient(timeout=600) as client:
        response = await client.post(
            f"{self.valves.smolcrawl_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.valves.smolcrawl_api_key}",
            },
            json={
                "model": "smolcrawl-knowledge-builder",  # pipeline ID
                "messages": [
                    {"role": "user", "content": f"crawl {domain} into {kb_name}"}
                ],
                "stream": True,
            },
        )
        # Stream progress back to the user via __event_emitter__
        ...
```

This is the same HTTP interface that OWUI itself uses to talk to the Pipelines server. The function just calls it directly, streaming crawl progress back to the user through `__event_emitter__`.

### Domain Discovery via Web Search

Before crawling, the function needs to find relevant domains. It uses OWUI's built-in web search (configured in Admin → Settings → Web Search) through a sub-agent call:

```python
async def _discover_domains(self, query: str, ...) -> list[dict]:
    """Use LLM + web search to discover relevant domains for a topic.

    The sub-agent is given a system prompt instructing it to:
    1. Search the web for authoritative sources on the topic
    2. Extract domain names from search results
    3. Return a ranked list with rationales
    """
    system_prompt = """You are a research librarian. Given a research topic,
    search the web to identify the most authoritative documentation sources.
    Return a JSON list of domains with relevance scores and rationale.
    Focus on: official docs, API references, tutorials, community wikis.
    Exclude: social media, forums, video-only content."""

    # The sub-agent call with web search enabled
    result = await self._run_sub_agent(
        system_prompt=system_prompt,
        user_prompt=f"Find authoritative web sources for: {query}",
        ...
    )
    return self._parse_domain_list(result)
```

**Note**: For web search to work in sub-agent calls, the sub-agent metadata must include `"features": {"web_search": True}` (or the model must have web search enabled by default in OWUI admin settings). This is a configuration detail to validate during implementation.

### User Approval Flow

After domain discovery, the function **pauses** and presents results to the user. This uses `__event_emitter__` to show the list and `__event_call__` (or a follow-up message pattern) to receive the user's selection:

```
🌐 Found 5 relevant domains for "Blueprint replication in UE5":

 1. [0.95] docs.unrealengine.com
    "Official UE5 documentation — primary source for Blueprint/replication"

 2. [0.88] dev.epicgames.com
    "Epic Games developer portal — API references and technical guides"

 3. [0.82] benui.ca
    "Community UE5 tutorials — covers Blueprint networking patterns"

 4. [0.71] www.tomlooman.com
    "UE5 game dev tutorials — multiplayer/replication focused"

 5. [0.65] forums.unrealengine.com
    "UE forums — noisy but contains solved replication problems"

Reply with numbers to approve (e.g., "1,2,3"), "all", or "skip".
You can also add domains: "1,2 + docs.unity3d.com"
```

The function returns this message and waits for the user's next interaction. The LLM receives the user's reply and calls `deep_research_approve(selection="1,2,3")` to continue.

This means the function exposes **two tool methods**:

1. `deep_research(query)` — starts the process, discovers domains, presents for approval
2. `deep_research_approve(selection, additional_domains?)` — user confirms, triggers crawl + research

### Function Signature

```python
class Tools:
    class Valves(BaseModel):
        # SmolCrawl container connection
        smolcrawl_url: str = "http://smolcrawl-pipelines:9099"
        smolcrawl_api_key: str = "0p3n-w3bu!"

        # OWUI API
        owui_base_url: str = "http://openwebui:8080"
        owui_api_key: str = ""

        # Research settings
        max_iterations: int = 3
        fixed_iterations: int = 2
        top_k_per_collection: int = 5
        max_collections: int = 10
        include_sources: bool = True

        # Fileshed integration
        fileshed_compatible: bool = True
        storage_base_path: str = "/app/backend/data/user_files"
        save_journal: bool = True

    def __init__(self):
        self.valves = self.Valves()
        self._pending_sessions: dict = {}  # chat_id → session state

    async def deep_research(
        self,
        query: str,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__=None,
        __request__=None,
        __model__: dict = None,
        __event_call__=None,
        __chat_id__: str = "",
        __message_id__: str = "",
    ) -> str:
        """
        Start deep research on a topic. Discovers relevant web domains
        using web search, then presents them for approval before crawling.

        Args:
            query: The research question or topic to investigate.
        """
        # 1. Initialize Fileshed journal (00-prompt.md)
        # 2. Check existing knowledge collections for coverage
        # 3. Sub-agent web search → discover domains
        # 4. Write 01-domains.md to journal
        # 5. Present domain list to user, return approval prompt
        # 6. Store session state in _pending_sessions[chat_id]

    async def deep_research_approve(
        self,
        selection: str,
        additional_domains: str = "",
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__=None,
        __request__=None,
        __model__: dict = None,
        __event_call__=None,
        __chat_id__: str = "",
        __message_id__: str = "",
    ) -> str:
        """
        Approve discovered domains and begin deep research.
        Call this after deep_research() presents domain options.

        Args:
            selection: Which domains to crawl — numbers like "1,2,3",
                       "all", or "skip" (research existing collections only).
            additional_domains: Optional extra domains to crawl, space-separated.
        """
        # 1. Retrieve session from _pending_sessions[chat_id]
        # 2. Parse selection, merge additional_domains
        # 3. For each approved domain:
        #    a. POST to SmolCrawl container → crawl into KB
        #    b. Stream crawl progress via __event_emitter__
        #    c. Write 02-crawl-status.md to journal
        # 4. Query new + existing collections (iterative RAG loop)
        # 5. Chain-of-thought synthesis
        # 6. Return final answer
```

#### How the Outer LLM Engages

With native function calling enabled, the conversation flows naturally:

```
User: "I need to deeply research how Blueprint replication works in UE5"

LLM → calls deep_research(query="Blueprint replication in UE5")
Function → discovers domains via web search, returns approval list

LLM → presents domain list to user (from function return value)

User: "approve 1,2,3 and also add docs.redpoint.games"

LLM → calls deep_research_approve(selection="1,2,3",
          additional_domains="docs.redpoint.games")
Function → triggers SmolCrawl for 4 domains
         → streams crawl progress
         → runs iterative RAG
         → returns CoT synthesis

LLM → presents the synthesized research answer to user
```

The LLM mediates the entire conversation. It decides when to call `deep_research()` vs. answering directly, and it naturally handles the approval handoff because it sees both tool descriptions.

### Iteration Model

- **Fixed 2 iterations** by default.
- After iteration 2, the LLM evaluates whether a 3rd iteration would yield meaningful new information. If yes, it continues; if not, it synthesizes.
- A `max_iterations` valve caps the upper bound (default: 3).

### Execution Flow

```
Phase A — Domain Discovery  (deep_research() call)
│
│  Step 0 — Initialize Research Journal
│  │  Create session directory in Fileshed: deep-research/{timestamp}-{slug}/
│  │  Write 00-prompt.md: original query, timestamp, model, goal context
│  │  → Emit: "📋 Research session started — journal: deep-research/{slug}"
│  │
│  Step 1 — Check Existing Knowledge
│  │  GET /api/v1/knowledge/ → list all collections
│  │  Sub-agent: "Which existing collections are relevant to this query?"
│  │  Note which topics are already covered vs. gaps
│  │  → Emit: "📚 Found [N] existing collections, [M] potentially relevant"
│  │
│  Step 2 — Discover Domains via Web Search
│  │  Sub-agent + web search: "Find authoritative docs for this topic"
│  │  Score and rank discovered domains
│  │  Filter out domains already covered by existing collections
│  │  Write 01-domains.md: discovered domains + existing coverage
│  │  → Return: domain list for user approval (function pauses here)
│
│─────── User reviews domains, replies with selection ───────│
│
Phase B — Crawl + Build KBs  (deep_research_approve() call)
│
│  Step 3 — Crawl Approved Domains
│  │  For each approved domain:
│  │    POST to SmolCrawl container → crawl + augment + upload to KB
│  │    Stream crawl progress via __event_emitter__
│  │  For user-added domains: same process
│  │  Write 02-crawl-status.md: which domains succeeded/failed, KB names
│  │  → Emit: "✅ Built [N] knowledge collections from [M] domains"
│  │
Phase C — Iterative RAG Research
│  │
│  Step 4 — Query All Relevant Collections
│  │  Include both existing (from Step 1) and newly-built (from Step 3)
│  │  POST /api/v1/retrieval/query for each collection
│  │  Sub-agent summarizes + identifies new concepts
│  │  Write 03-iteration-1.md: terms, chunks, summary, new concepts
│  │  → Emit: "📚 Found [N] passages across [M] collections"
│  │
│  Step 5 — Term Expansion (Iteration 1)
│  │  Read back: 00-prompt.md + 03-iteration-1.md summary
│  │  Sub-agent: "What adjacent concepts should we search for?"
│  │  Re-query with expanded terms, deduplicate
│  │  Write 04-iteration-2.md: expanded terms, new chunks, summary
│  │  → Emit: "🔄 Expanding: [term1], [term2] — [N] new passages"
│  │
│  Step 6 — Continue Decision
│  │  Sub-agent: "Would a third pass yield meaningful new info? YES/NO"
│  │  If YES → one more iteration (write 05-iteration-3.md)
│  │  → Emit: "🔄 Continuing..." or "✅ Search complete"
│  │
Phase D — Chain-of-Thought Synthesis
│  │
│  Step 7 — Synthesize
│  │  Read back: 00-prompt.md + all iteration summaries + top chunks
│  │  Sub-agent: "Reason step-by-step through the evidence. Cite sources."
│  │  Write 0N-synthesis.md: CoT reasoning + final answer + sources
│  │  Write manifest.json: session index
│  │  → Emit: abbreviated CoT + final answer + source references
│  │  → Emit: "📁 Full research journal: deep-research/{slug}/"
│  │  → Return: synthesized answer to outer LLM
```

### Valve Configuration

No `trigger_prefix` needed — the LLM decides when to call `deep_research()` based on the tool description and native function calling.

| Valve                  | Type | Default                             | Description                                    |
| ---------------------- | ---- | ----------------------------------- | ---------------------------------------------- |
| `smolcrawl_url`        | str  | `"http://smolcrawl-pipelines:9099"` | SmolCrawl pipeline container URL               |
| `smolcrawl_api_key`    | str  | `"0p3n-w3bu!"`                      | Pipelines server API key                       |
| `owui_base_url`        | str  | `"http://openwebui:8080"`           | OWUI API base                                  |
| `owui_api_key`         | str  | `""`                                | Bearer token for OWUI API                      |
| `max_iterations`       | int  | `3`                                 | Hard cap on RAG expansion iterations           |
| `fixed_iterations`     | int  | `2`                                 | Guaranteed iterations before continue-decision |
| `top_k_per_collection` | int  | `5`                                 | Chunks retrieved per collection per query      |
| `max_collections`      | int  | `10`                                | Max collections to search (LLM selects best)   |
| `max_domains`          | int  | `5`                                 | Max domains to discover via web search         |
| `include_sources`      | bool | `True`                              | Append source references to final answer       |
| `fileshed_compatible`  | bool | `True`                              | Write journal to Fileshed Storage zone         |
| `storage_base_path`    | str  | `"/app/backend/data/user_files"`    | Base path for Fileshed-compatible storage      |
| `save_journal`         | bool | `True`                              | Persist research journal to disk               |

### API Endpoints Used

| Endpoint                   | Method   | Service          | Purpose                               |
| -------------------------- | -------- | ---------------- | ------------------------------------- |
| `/api/v1/knowledge/`       | GET      | OWUI             | List all knowledge collections        |
| `/api/v1/knowledge/{id}`   | GET      | OWUI             | Get collection metadata               |
| `/api/v1/retrieval/query`  | POST     | OWUI             | RAG query against a collection        |
| `/v1/chat/completions`     | POST     | SmolCrawl (9099) | Trigger crawl via pipeline            |
| `generate_chat_completion` | internal | OWUI             | Sub-agent LLM calls (with web search) |

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

| Step                 | File                   | Contents                                                                                                                 |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Activation           | `00-prompt.md`         | Original query, timestamp, selected model                                                                                |
| Domain Discovery     | `01-domains.md`        | Web search results, discovered domains with scores, existing collection coverage, user approval status                   |
| Crawl Status         | `02-crawl-status.md`   | Per-domain crawl result (pages crawled, KB name, success/failure), timing                                                |
| Iteration N          | `0{N+2}-iteration-{N}.md` | Search terms used, collections queried, retrieved chunks (full text), LLM's summary of findings, new concepts identified |
| Continue Decision    | appended to last iteration file | LLM's YES/NO rationale                                                                                             |
| Synthesis            | `0N-synthesis.md`      | Chain-of-thought reasoning over all iteration summaries, final answer, source citations                                  |
| Index                | `manifest.json`        | `{session_id, query, domains, crawls, iterations: [{file, terms, collections, chunk_count}], status}`                    |

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

## Component 2: LLM-Guided Crawl Discovery (SmolCrawl Enhancement)

See [plan-llm-crawl-discovery.md](plan-llm-crawl-discovery.md) for the SmolCrawl-side frontier enhancement.

This is a **complementary** feature to the deep research function's domain discovery (Phase A). The difference:

| Feature                                      | Runs When    | Scope                                   | User Interaction                    |
| -------------------------------------------- | ------------ | --------------------------------------- | ----------------------------------- |
| **Deep research domain discovery** (Phase A) | Before crawl | Web search for seed domains             | User approves in chat               |
| **LLM-guided crawl discovery** (frontier)    | During crawl | Evaluates outbound links found in pages | User approves new domains mid-crawl |

Both features present links to the user before any crawl is triggered. They operate at different stages of the pipeline and can work together: domain discovery finds the initial seeds, crawl discovery expands them during crawling.

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

### Phase 1: Core Function Scaffold

1. Scaffold `deep_research_function.py` as `class Tools` with Valves
2. Implement `_run_sub_agent()` for internal LLM calls (reuse Superpowers pattern)
3. Implement Fileshed journal (`_resolve_session_dir`, `_write_journal_entry`, `_read_journal_entry`)
4. Implement `deep_research()` — existing-KB check + return placeholder approval prompt
5. Implement `deep_research_approve()` — skeleton with session state handoff

### Phase 2: Domain Discovery + Crawl Integration

1. Implement web search domain discovery via sub-agent (with `web_search` feature flag)
2. Implement user approval parsing ("1,2,3", "all", "skip", "+ extra.com")
3. Implement `_trigger_crawl()` — HTTP POST to SmolCrawl container, stream progress
4. Handle crawl failures gracefully (skip failed domains, continue with others)
5. Write `01-domains.md` and `02-crawl-status.md` journal entries

### Phase 3: Iterative RAG Research

1. Implement collection listing + LLM ranking (include new + existing KBs)
2. Implement RAG query loop with term expansion → write iteration files
3. Implement continue-decision logic with journal read-back
4. Implement chunk deduplication across iterations

### Phase 4: Synthesis + Polish

1. Implement chain-of-thought synthesis from journal entries
2. Streaming status via `__event_emitter__` at each phase
3. Write `manifest.json` with machine-readable session index
4. Docker integration (function can be installed directly in OWUI or via Pipelines)
5. End-to-end test: discover → approve → crawl → research → synthesize

### Phase 5: Enhanced Crawl Discovery (SmolCrawl Frontier)

1. Create `frontier/llm_evaluator.py` with link scoring
2. Hook into `crawl.py` to collect outbound cross-domain links
3. Implement approval callback (OWUI chat + CLI modes)
4. Tests for LLM evaluator (mocked LLM responses)

### Phase 6: Integration

1. Connect crawl discovery → knowledge collection → deep research loop
2. End-to-end test: full pipeline with mid-crawl domain expansion
3. Superpowers integration (brainstorm → deep research → spec)
