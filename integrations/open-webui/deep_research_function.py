"""
title: Deep Research
author: smolcrawl
date: 2026-04-12
version: 1.0
license: MIT
description: Iterative RAG research with LLM-guided domain discovery, web search exploration, and chain-of-thought synthesis. Provides research() for quick exploration and deep_research() for full knowledge building.
requirements: httpx, pydantic
"""

# =============================================================================
#  Deep Research Function for Open WebUI
#
#  Self-contained single-file deployment. Source modules live in
#  integrations/open-webui/deep_research/ for development.
#
#  Install: OWUI Workspace → Tools → (+) → Paste this file
# =============================================================================

import hashlib
import json
import logging
import os
import re
import time
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("deep_research")


# =============================================================================
#  Models
# =============================================================================


class ResearchPhase(str, Enum):
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    AWAITING_APPROVAL = "awaiting_approval"
    CRAWLING = "crawling"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class DiscoveredDomain:
    url: str
    domain: str
    score: float
    rationale: str
    already_covered: bool = False
    existing_collection_id: Optional[str] = None


@dataclass
class CrawlResult:
    domain: str
    kb_name: str
    kb_id: str = ""
    pages_crawled: int = 0
    success: bool = False
    error: str = ""
    duration_seconds: float = 0.0


@dataclass
class RetrievedChunk:
    content: str
    collection_id: str
    collection_name: str
    source: str = ""
    distance: float = 0.0

    @property
    def chunk_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class IterationResult:
    iteration_number: int
    search_terms: List[str]
    collections_queried: List[str]
    chunks_found: int
    new_chunks: int
    summary: str = ""
    new_concepts: List[str] = field(default_factory=list)


@dataclass
class ResearchSession:
    session_id: str
    query: str
    session_dir: str
    phase: ResearchPhase = ResearchPhase.INITIALIZING
    discovered_domains: List[DiscoveredDomain] = field(default_factory=list)
    crawl_results: List[CrawlResult] = field(default_factory=list)
    iterations: List[IterationResult] = field(default_factory=list)
    relevant_collection_ids: List[str] = field(default_factory=list)
    seen_chunk_keys: set = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    model_id: str = ""
    anchor: str = ""

    def add_seen_chunk(self, collection_id: str, chunk_hash: str) -> bool:
        key = (collection_id, chunk_hash)
        if key in self.seen_chunk_keys:
            return False
        self.seen_chunk_keys.add(key)
        return True


# =============================================================================
#  Journal (Fileshed-compatible storage)
# =============================================================================


class _Journal:
    def __init__(self, valves):
        self._v = valves

    def resolve_session_dir(self, user_id: str, slug: str, namespace: str = "deep-research") -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"{ts}-{slug}"
        if self._v.fileshed_compatible and user_id:
            return os.path.join(self._v.storage_base_path, "users", user_id, "Storage", "data", namespace, name)
        return os.path.join(self._v.storage_base_path, namespace, name)

    def write_entry(self, session_dir: str, filename: str, content: str) -> str:
        if not self._v.save_journal:
            return ""
        path = os.path.join(session_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def read_entry(self, session_dir: str, filename: str) -> str:
        path = os.path.join(session_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def write_prompt(self, session: ResearchSession, model_id: str) -> None:
        self.write_entry(session.session_dir, "00-prompt.md",
            f"# Research Session\n\n**Query:** {session.query}\n"
            f"**Timestamp:** {session.created_at.isoformat()}\n"
            f"**Model:** {model_id}\n**Session ID:** {session.session_id}\n")

    def write_anchor(self, session: ResearchSession) -> None:
        self.write_entry(session.session_dir, "00-anchor.md",
            f"# Research Anchor\n\n```\n{session.anchor}\n```\n\n"
            f"This anchor was extracted at session start and is threaded through "
            f"every search, analysis, and synthesis prompt to prevent drift.\n")

    def write_domains(self, session: ResearchSession, existing: List[Dict]) -> None:
        lines = ["# Domain Discovery\n"]
        if existing:
            lines.append("## Existing Collections\n")
            for c in existing:
                fc = len(c.get("data", {}).get("file_ids", []))
                lines.append(f"- **{c['name']}** ({fc} files): {c.get('description', 'No description')}\n")
            lines.append("")
        lines.append("## Discovered Domains\n")
        for i, d in enumerate(session.discovered_domains, 1):
            st = "✅ Already covered" if d.already_covered else "🆕 New"
            lines.append(f"{i}. [{d.score:.2f}] **{d.domain}**\n   {d.rationale}\n   Status: {st}\n")
        self.write_entry(session.session_dir, "01-domains.md", "\n".join(lines))

    def write_crawl_status(self, session: ResearchSession) -> None:
        lines = ["# Crawl Status\n"]
        for r in session.crawl_results:
            s = "✅" if r.success else "❌"
            lines.append(f"## {s} {r.domain}\n\n- **KB Name:** {r.kb_name}\n- **Pages:** {r.pages_crawled}\n- **Duration:** {r.duration_seconds:.1f}s\n")
            if r.error:
                lines.append(f"- **Error:** {r.error}\n")
        self.write_entry(session.session_dir, "02-crawl-status.md", "\n".join(lines))

    def write_iteration(self, session: ResearchSession, it: IterationResult) -> None:
        fn = f"{it.iteration_number + 2:02d}-iteration-{it.iteration_number}.md"
        lines = [f"# Iteration {it.iteration_number}\n", "## Search Terms\n",
                 ", ".join(f"`{t}`" for t in it.search_terms) + "\n",
                 "\n## Collections Queried\n", ", ".join(it.collections_queried) + "\n",
                 f"\n## Results\n- Chunks found: {it.chunks_found}\n- New: {it.new_chunks}\n",
                 f"\n## Summary\n\n{it.summary}\n"]
        if it.new_concepts:
            lines.append("\n## New Concepts\n\n")
            lines.extend(f"- {c}\n" for c in it.new_concepts)
        self.write_entry(session.session_dir, fn, "\n".join(lines))

    def write_synthesis(self, session: ResearchSession, content: str) -> None:
        fn = f"{len(session.iterations) + 3:02d}-synthesis.md"
        self.write_entry(session.session_dir, fn, f"# Synthesis\n\n{content}\n")

    def write_manifest(self, session: ResearchSession) -> None:
        m = {"session_id": session.session_id, "query": session.query,
             "created_at": session.created_at.isoformat(), "phase": session.phase.value,
             "model_id": session.model_id,
             "domains": [{"domain": d.domain, "url": d.url, "score": d.score} for d in session.discovered_domains],
             "crawls": [{"domain": c.domain, "kb_name": c.kb_name, "pages_crawled": c.pages_crawled, "success": c.success} for c in session.crawl_results],
             "iterations": [{"number": i.iteration_number, "terms": i.search_terms, "chunk_count": i.chunks_found} for i in session.iterations],
             "seen_chunks": len(session.seen_chunk_keys)}
        self.write_entry(session.session_dir, "manifest.json", json.dumps(m, indent=2))

    @staticmethod
    def slugify(text: str, max_length: int = 40) -> str:
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")
        return slug[:max_length]


# =============================================================================
#  Sub-Agent (internal LLM calls)
# =============================================================================


_ANCHOR_PROMPT = """\
Extract a structured research anchor from the user's query.
This anchor will guide all subsequent search, analysis, and synthesis steps.

Return JSON:
{"key_concepts": ["specific concepts/terms the user mentioned"],
 "intent": "one sentence: what the user wants to learn or accomplish",
 "scope_in": ["topics that ARE in scope"],
 "scope_out": ["adjacent topics that are NOT being asked about"],
 "must_cover": ["terms/phrases from the query that MUST appear in results"]}

Be precise — use the user's exact words. Do NOT generalize or broaden.\
"""


async def _extract_anchor(sa: '_SubAgent', query: str, request, user: Dict) -> str:
    """Run one LLM call to distil the query into a reusable anchor block."""
    try:
        r = await sa.run_json(_ANCHOR_PROMPT, query, request, user)
    except Exception:
        # Fallback: just wrap the raw query
        return f"RESEARCH ANCHOR\nQuery: {query}\nKey concepts: (extraction failed — use query as-is)"
    lines = ["RESEARCH ANCHOR", f"Query: {query}"]
    if r.get("key_concepts"):
        lines.append(f"Key concepts: {', '.join(r['key_concepts'])}")
    if r.get("intent"):
        lines.append(f"Intent: {r['intent']}")
    if r.get("must_cover"):
        lines.append(f"Must cover: {', '.join(r['must_cover'])}")
    if r.get("scope_in"):
        lines.append(f"In scope: {', '.join(r['scope_in'])}")
    if r.get("scope_out"):
        lines.append(f"Out of scope: {', '.join(r['scope_out'])}")
    return "\n".join(lines)


# _WEB_SEARCH_LIST_PROMPT removed — we now call search_web() directly


class _SubAgent:
    def __init__(self, model_id: str):
        self._model_id = model_id

    async def run(self, system_prompt: str, user_prompt: str, request, user: Dict,
                  json_mode: bool = False) -> str:
        from open_webui.utils.chat import generate_chat_completion
        from open_webui.models.users import UserModel

        if json_mode:
            sys_msg = ("You are a JSON data extraction API. "
                       "Respond with ONLY valid JSON. "
                       "No explanations, no markdown fences, no commentary.")
        else:
            sys_msg = "Follow the user's instructions precisely."

        combined = (
            f"INSTRUCTIONS (follow these exactly):\n{system_prompt}\n\n"
            f"---\nINPUT:\n{user_prompt}"
        )

        form_data = {
            "model": self._model_id,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": combined},
            ],
            "stream": False,
            "metadata": {"task": "deep_research_sub_agent"},
        }
        response = await generate_chat_completion(
            request=request, form_data=form_data,
            user=UserModel(**user), bypass_filter=True,
        )
        return response["choices"][0]["message"]["content"]

    async def run_json(self, system_prompt: str, user_prompt: str, request, user: Dict) -> Any:
        """Call LLM and parse response as JSON."""
        raw = await self.run(system_prompt, user_prompt, request, user,
                             json_mode=True)
        try:
            return _parse_json(raw)
        except ValueError:
            logger.warning("JSON parse failed. Raw response (first 500 chars): %s",
                           raw[:500] if raw else "<empty>")
            raise

    @staticmethod
    def resolve_model_id(metadata: Optional[Dict], model: Optional[Dict]) -> str:
        return (((metadata or {}).get("model") or {}).get("id", "")
                or (model or {}).get("id", ""))


def _parse_json(text: str) -> Any:
    text = text.strip()
    # Attempt 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Attempt 2: Markdown code fence
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Attempt 3: Find first JSON array or object in the text
    for pattern in [r'(\[\s*\{.*\}\s*\])', r'(\{.*\})']:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}...")


# =============================================================================
#  Domain Discovery
# =============================================================================

_DISCOVERY_PROMPT = """\
You are a research librarian. Given a research topic, search the web to \
identify the most authoritative documentation sources.

IMPORTANT: Cover ALL specific concepts mentioned in the query. If the \
user mentions a specific term, technique, or proper noun, find sources \
that address it directly — do not substitute broader topics.

Return a JSON array of objects, each with:
- "url": full URL of the documentation root
- "domain": the domain name
- "score": relevance 0.0-1.0
- "rationale": one-sentence explanation of how this addresses the query

Focus on: official docs, API references, tutorials, community wikis.
Exclude: social media, forums, video-only, paywalled sites.
Return at most {max_domains} domains, ordered by score descending.
Respond ONLY with valid JSON.\
"""

_RANKING_PROMPT = """\
Given a list of knowledge collections and a research query, return a JSON \
array of collection IDs that are relevant. Respond ONLY with a JSON array.\
"""


class _Discovery:
    def __init__(self, valves, sub_agent: _SubAgent):
        self._v = valves
        self._sa = sub_agent

    async def discover_domains(self, query: str, request, user: Dict) -> List[DiscoveredDomain]:
        """Discover domains via direct web search + LLM ranking."""
        from open_webui.routers.retrieval import search_web
        from starlette.concurrency import run_in_threadpool

        engine = getattr(request.app.state.config, "WEB_SEARCH_ENGINE", "")
        if not engine:
            logger.warning("No WEB_SEARCH_ENGINE configured — skipping domain discovery")
            return []

        try:
            results = await run_in_threadpool(
                search_web, request, engine,
                f"authoritative documentation for {query}")
        except Exception as e:
            logger.error("Domain discovery search failed: %s", e)
            return []

        if not results:
            return []

        # Format search results for LLM ranking
        listing = "\n".join(
            f"- {r.link} | {r.title or '(no title)'} | {r.snippet or '(no snippet)'}"
            for r in results[:20])

        try:
            data = await self._sa.run_json(
                _DISCOVERY_PROMPT.format(max_domains=self._v.max_domains),
                f"Research query: {query}\n\nWeb search results:\n{listing}",
                request, user)
        except Exception as e:
            logger.error("Domain discovery LLM ranking failed: %s", e)
            # Fall back to raw search results as domains
            data = []
            seen = set()
            for r in results[:self._v.max_domains]:
                try:
                    domain = urlparse(r.link).netloc
                except Exception:
                    continue
                if domain not in seen:
                    seen.add(domain)
                    data.append({
                        "url": r.link, "domain": domain,
                        "score": 0.5, "rationale": r.snippet or ""})
        return self._parse(data)

    async def rank_collections(self, query: str, collections: List[Dict], request, user: Dict) -> List[str]:
        if not collections:
            return []
        summaries = "\n".join(
            f"- ID: {c['id']} | Name: {c['name']} | Desc: {c.get('description', 'None')} | Files: {len(c.get('data', {}).get('file_ids', []))}"
            for c in collections)
        try:
            result = await self._sa.run_json(_RANKING_PROMPT,
                f"Query: {query}\n\nAvailable collections:\n{summaries}", request, user)
        except Exception as e:
            logger.error("Collection ranking failed: %s", e)
            return []
        valid = {c["id"] for c in collections}
        return [r for r in (result if isinstance(result, list) else []) if r in valid]

    def check_coverage(self, domains: List[DiscoveredDomain], collections: List[Dict]) -> List[DiscoveredDomain]:
        hints = set()
        for c in collections:
            for t in (c.get("name", "").lower(), c.get("description", "").lower()):
                hints.add(t)
                for w in t.split():
                    if "." in w and len(w) > 4:
                        hints.add(w)
        for d in domains:
            dl = d.domain.lower()
            for h in hints:
                if dl in h or h in dl:
                    d.already_covered = True
                    for c in collections:
                        if dl in c.get("name", "").lower():
                            d.existing_collection_id = c["id"]
                            break
                    break
        return domains

    @staticmethod
    def format_approval(domains: List[DiscoveredDomain], existing: List[Dict]) -> str:
        lines = []
        if existing:
            lines.append(f"📚 Found **{len(existing)}** existing relevant collection(s).\n")
        lines.append(f"🌐 Discovered **{len(domains)}** relevant domain(s):\n")
        for i, d in enumerate(domains, 1):
            cov = " *(already in KB)*" if d.already_covered else ""
            lines.append(f" {i}. **[{d.score:.2f}] {d.domain}**{cov}\n    {d.rationale}\n")
        lines.append('\nReply with numbers to approve (e.g., "1,2,3"), "all", or "skip".\nYou can also add domains: "1,2 + docs.example.com"')
        return "\n".join(lines)

    @staticmethod
    def parse_approval(selection: str, domains: List[DiscoveredDomain], additional: str = "") -> List[DiscoveredDomain]:
        sel = selection.strip().lower()
        approved = []
        if sel == "all":
            approved = [d for d in domains if not d.already_covered]
        elif sel != "skip":
            main = sel.split("+")[0].strip()
            for p in main.replace(" ", ",").split(","):
                p = p.strip()
                if p.isdigit():
                    idx = int(p) - 1
                    if 0 <= idx < len(domains):
                        approved.append(domains[idx])
        if additional:
            for ds in additional.strip().split():
                ds = ds.strip().strip(",")
                if ds and "." in ds:
                    approved.append(DiscoveredDomain(url=f"https://{ds}/", domain=ds, score=0.0, rationale="User-specified"))
        return approved

    @staticmethod
    def _parse(data) -> List[DiscoveredDomain]:
        if not isinstance(data, list):
            return []
        domains = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                url = item.get("url", "")
                domain = item.get("domain", "") or urlparse(url).netloc
                if not url and domain:
                    url = f"https://{domain}/"
                domains.append(DiscoveredDomain(url=url, domain=domain, score=float(item.get("score", 0.5)), rationale=str(item.get("rationale", ""))))
            except (TypeError, ValueError):
                continue
        domains.sort(key=lambda d: d.score, reverse=True)
        return domains


# =============================================================================
#  Crawl Integration (SmolCrawl container HTTP client)
# =============================================================================


class _CrawlClient:
    def __init__(self, valves):
        self._v = valves

    async def trigger_crawl(self, domain: str, kb_name: str, event_emitter=None) -> CrawlResult:
        start = time.monotonic()
        url = domain if domain.startswith("http") else f"https://{domain}/"
        result = CrawlResult(domain=domain, kb_name=kb_name)
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(
                    f"{self._v.smolcrawl_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._v.smolcrawl_api_key}", "Content-Type": "application/json"},
                    json={"model": "smolcrawl-knowledge-builder",
                          "messages": [{"role": "user", "content": f"crawl {url} into {kb_name}"}],
                          "stream": False})
                resp.raise_for_status()
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                result.success = True
                result.pages_crawled = self._extract_pages(content)
                if event_emitter:
                    await event_emitter({"type": "status", "data": {"description": f"✅ Crawled {domain}: {result.pages_crawled} pages", "done": False}})
        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error("Crawl failed for %s: %s", domain, result.error)
        except httpx.RequestError as e:
            result.error = f"Connection error: {e}"
            logger.error("Crawl connection failed for %s: %s", domain, e)
        except Exception as e:
            result.error = str(e)
            logger.error("Crawl error for %s: %s", domain, e)
        result.duration_seconds = time.monotonic() - start
        return result

    @staticmethod
    def _extract_pages(content: str) -> int:
        m = re.search(r"(\d+)\s*pages?\s*crawled", content, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"Crawled\s*\*?\*?(\d+)\*?\*?", content)
        if m:
            return int(m.group(1))
        return 0


# =============================================================================
#  RAG Research (iterative collection queries)
# =============================================================================

_EXPANSION_PROMPT = """\
You are a research assistant analyzing RAG retrieval results.

Compare the retrieved content against the ORIGINAL query. Identify:
1. What aspects of the query these results address well
2. What specific aspects of the original query remain UNCOVERED
3. New search terms that target the uncovered aspects (use the user’s terminology)
4. Adjacent concepts discovered that are still relevant to the original query

Return JSON: {"terms": ["terms targeting gaps"], "concepts": ["relevant concepts found"], "summary": "2-3 paragraph summary", "uncovered": ["aspects of original query not yet addressed"]}\
"""

_CONTINUE_PROMPT = """\
Evaluate whether another research iteration would be valuable.
Continue if: key aspects of the original query remain uncovered, OR \
promising new terms haven’t been explored yet.
Stop if: the original query’s main concepts are well-covered.

Return JSON: {"continue": true/false, "rationale": "one sentence", "uncovered": ["remaining gaps if any"]}\
"""


class _RagResearcher:
    def __init__(self, valves, sub_agent: _SubAgent):
        self._v = valves
        self._sa = sub_agent

    async def list_collections(self) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{self._v.owui_base_url}/api/v1/knowledge/",
                    headers={"Authorization": f"Bearer {self._v.owui_api_key}", "Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
                return data.get("items", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error("Failed to list collections: %s", e)
            return []

    async def query_collection(self, col_id: str, query: str, col_name: str = "") -> List[RetrievedChunk]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self._v.owui_base_url}/api/v1/retrieval/query",
                    headers={"Authorization": f"Bearer {self._v.owui_api_key}", "Content-Type": "application/json"},
                    json={"collection_name": col_id, "query": query, "k": self._v.top_k_per_collection, "r": 0.0})
                resp.raise_for_status()
                return self._parse_retrieval(resp.json(), col_id, col_name)
        except Exception as e:
            logger.error("Query failed for %s: %s", col_id, e)
            return []

    async def run_iteration(self, session: ResearchSession, terms: List[str],
                            col_ids: List[str], col_names: Dict[str, str],
                            iter_num: int, request, user: Dict) -> IterationResult:
        all_chunks, new_chunks = [], []
        for term in terms:
            for cid in col_ids:
                for chunk in await self.query_collection(cid, term, col_names.get(cid, cid)):
                    all_chunks.append(chunk)
                    if session.add_seen_chunk(cid, chunk.chunk_hash):
                        new_chunks.append(chunk)

        summary, concepts = "", []
        if new_chunks:
            ctx = "\n\n---\n\n".join(f"**[{c.collection_name}]** ({c.source})\n{c.content}" for c in new_chunks[:20])
            try:
                r = await self._sa.run_json(_EXPANSION_PROMPT,
                    f"{session.anchor}\n\nSearch terms used: {', '.join(terms)}\n\nRetrieved ({len(new_chunks)} new chunks):\n\n{ctx}",
                    request, user)
                summary = r.get("summary", "")
                concepts = r.get("concepts", [])
            except Exception:
                summary = f"Found {len(new_chunks)} new chunks."

        it = IterationResult(iter_num, terms, [col_names.get(c, c) for c in col_ids],
                             len(all_chunks), len(new_chunks), summary, concepts)
        session.iterations.append(it)
        return it

    async def expand_terms(self, session: ResearchSession, current: List[str], request, user: Dict) -> List[str]:
        sums = "\n".join(f"Iteration {i.iteration_number}: {i.summary}" for i in session.iterations)
        try:
            r = await self._sa.run_json(_EXPANSION_PROMPT,
                f"{session.anchor}\n\nPrevious terms: {', '.join(current)}\nFindings:\n{sums}\n\nSuggest new search terms that address uncovered aspects per the anchor above.",
                request, user)
            return r.get("terms", current)
        except Exception:
            return current

    async def should_continue(self, session: ResearchSession, request, user: Dict) -> bool:
        sums = "\n".join(f"Iter {i.iteration_number}: new={i.new_chunks}, concepts={', '.join(i.new_concepts)}" for i in session.iterations)
        try:
            r = await self._sa.run_json(_CONTINUE_PROMPT, f"{session.anchor}\n\n{sums}", request, user)
            return bool(r.get("continue", False))
        except Exception:
            return False

    @staticmethod
    def _parse_retrieval(data: Dict, col_id: str, col_name: str) -> List[RetrievedChunk]:
        docs = data.get("documents", [[]])
        metas = data.get("metadatas", [[]])
        dists = data.get("distances", [[]])
        if not docs or not docs[0]:
            return []
        return [RetrievedChunk(content=docs[0][i], collection_id=col_id, collection_name=col_name,
                               source=(metas[0][i] if i < len(metas[0]) else {}).get("source", ""),
                               distance=(dists[0][i] if i < len(dists[0]) else 0.0))
                for i in range(len(docs[0]))]


# =============================================================================
#  Synthesis
# =============================================================================

_SYNTHESIS_PROMPT = """\
You are a **source-grounded** research synthesizer. You may ONLY make claims \
that are directly supported by the provided evidence. You are NOT a general \
knowledge assistant — treat this as a courtroom: no evidence, no claim.

## Hard Rules
1. **Source-grounded claims only.** Every factual statement must trace to a \
specific Collected Source by number (e.g. [Source 3]). If no source supports \
a claim, do NOT make it — instead note it as a gap.
2. **ZERO fabricated URLs.** The Sources section must contain ONLY URLs copied \
verbatim from the Collected Sources list. A synthesis with fabricated URLs is \
a failed synthesis.
3. **No gap-filling from training data.** If the collected evidence is \
insufficient to answer part of the query, say so explicitly in the Gaps \
section. Do NOT fill in missing information from your general knowledge.
4. **No generic templates.** Your answer must be specific to the actual \
evidence collected. If sources only cover surface-level information, \
produce a surface-level answer and flag the depth gap.
5. **Verify terminology.** If sources use a specific term for a technology, \
framework, or concept, use that exact term. Do NOT substitute similar-sounding \
technologies.
6. **Confidence tagging.** Mark each major claim: \
[SOURCED] — directly stated in a source, \
[INFERRED] — reasonable inference from multiple sources, \
[UNCERTAIN] — mentioned but not well-supported.
7. **Scope fidelity.** Answer ONLY what the Research Anchor asks. Match the \
requested format and depth.

Structure:
### Reasoning  (step-by-step, reference sources by number)
### Answer     (comprehensive, every claim tagged)
### Confidence Assessment  (evidence quality, source diversity, notable gaps)
### Sources    (ONLY URLs from Collected Sources list)
### Gaps & Limitations  (what evidence does NOT cover)\
"""

_VERIFICATION_PROMPT = """\
You are a factual accuracy reviewer. Given a research synthesis and the \
original source data it was built from, identify problems.

Check for: 1) Fabricated URLs not in Collected Sources, 2) Unsupported claims, \
3) Technology misidentification, 4) Generic template content, 5) Scope mismatch, \
6) Fabricated examples/code/commands.

Return JSON:
{"issues": [{"type": "fabricated_url|unsupported_claim|misidentification|generic_template|scope_mismatch|fabricated_example",
"severity": "critical|warning", "detail": "description", "location": "quote first 100 chars"}],
"url_check": {"urls_in_synthesis": [], "urls_in_sources": [], "fabricated": []},
"overall_credibility": "high|medium|low|very_low",
"recommendation": "pass|revise|flag_for_user"}\
"""


class _Synthesizer:
    def __init__(self, valves, sub_agent: _SubAgent, journal: _Journal):
        self._v = valves
        self._sa = sub_agent
        self._j = journal

    async def synthesize(self, session: ResearchSession, request, user: Dict,
                          relevant_sources: List[Dict] = None,
                          trail_sources: List[Dict] = None) -> str:
        prompt_md = self._j.read_entry(session.session_dir, "00-prompt.md")
        iter_mds = []
        for it in session.iterations:
            fn = f"{it.iteration_number + 2:02d}-iteration-{it.iteration_number}.md"
            c = self._j.read_entry(session.session_dir, fn)
            if c:
                iter_mds.append(c)

        all_sources = (relevant_sources or []) + (trail_sources or [])
        known_urls = self._extract_known_urls(all_sources)

        parts = [f"# Research Anchor\n\n{session.anchor}\n"]
        parts.append(f"# Original Query\n\n{session.query}\n")
        if prompt_md:
            parts.append(f"# Context\n\n{prompt_md}\n")
        for i, md in enumerate(iter_mds, 1):
            parts.append(f"# Iteration {i}\n\n{md}\n")

        # Include the actual source data so the LLM can cite real URLs
        if all_sources:
            parts.append("# Collected Sources (EXHAUSTIVE LIST)\n")
            parts.append("These are the ONLY sources found during research. "
                         "Your answer must be built EXCLUSIVELY from this evidence. "
                         "Reference sources by number [Source N]. "
                         "The Sources section of your answer must ONLY contain URLs "
                         "from this list — copied exactly, character for character.\n")
            for i, s in enumerate(all_sources, 1):
                parts.append(
                    f"[Source {i}] **{s.get('title', 'Untitled')}**\n"
                    f"   - URL: {s.get('url', 'N/A')}\n"
                    f"   - Domain: {s.get('domain', '')}\n"
                    f"   - Summary: {s.get('summary', '')}\n"
                )
        else:
            parts.append("# Collected Sources\n\n"
                         "**NO sources were collected.** Your synthesis must state "
                         "that the research found no relevant sources. Do NOT "
                         "generate an answer from general knowledge.\n")

        source_count = len(all_sources)
        parts.append(
            f"\n---\nYou have {source_count} source(s) to work with.\n"
            "- Address EVERY item in the Research Anchor's 'must_cover' list.\n"
            "- For items NOT covered by any source, list them in Gaps.\n"
            "- In Sources, list ONLY URLs that appear verbatim in Collected Sources.\n"
            "- If evidence is insufficient, produce a SHORTER answer that honestly "
            "reflects what the evidence supports. Do NOT pad with general knowledge.\n"
            "- Tag each factual claim: [SOURCED], [INFERRED], or [UNCERTAIN]."
        )

        try:
            answer = await self._sa.run(_SYNTHESIS_PROMPT, "\n\n".join(parts), request, user)

            # Post-synthesis: programmatic URL scrubbing
            answer, scrubbed = self._scrub_fabricated_urls(answer, known_urls)
            if scrubbed:
                logger.warning("Scrubbed %d fabricated URL(s)", len(scrubbed))

            # Post-synthesis: LLM verification pass
            verification = await self._verify(answer, all_sources, session, request, user)

            # Append credibility report
            report = self._credibility_report(verification, scrubbed, all_sources)
            if report:
                answer += report

            self._j.write_synthesis(session, answer)
            self._j.write_manifest(session)
            return answer
        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            fb = self._fallback(session)
            self._j.write_synthesis(session, fb)
            self._j.write_manifest(session)
            return fb

    @staticmethod
    def _extract_known_urls(sources: List[Dict]) -> set:
        urls = set()
        for s in sources:
            url = s.get("url", "")
            if url and url != "N/A":
                urls.add(url)
                stripped = url.rstrip("/")
                urls.add(stripped)
                urls.add(stripped + "/")
        return urls

    @staticmethod
    def _extract_urls_from_text(text: str) -> List[str]:
        import re as _re
        patterns = [
            r'\[.*?\]\((https?://[^\s\)]+)\)',
            r'(?<!\()(https?://[^\s\)\]>"]+)',
        ]
        found = []
        for pat in patterns:
            for match in _re.finditer(pat, text):
                url = match.group(1) if match.lastindex else match.group(0)
                found.append(url)
        return list(dict.fromkeys(found))

    @staticmethod
    def _scrub_fabricated_urls(text: str, known_urls: set) -> tuple:
        import re as _re
        if not known_urls:
            return text, []
        urls_in_text = _Synthesizer._extract_urls_from_text(text)
        fabricated = []
        for url in urls_in_text:
            url_clean = url.rstrip("/")
            if not (url in known_urls or url_clean in known_urls or url_clean + "/" in known_urls):
                fabricated.append(url)
        if not fabricated:
            return text, []
        cleaned = text
        for url in fabricated:
            cleaned = _re.sub(
                r'\[([^\]]*)\]\(' + _re.escape(url) + r'\)',
                r'[\1] *(URL removed — not found in collected sources)*',
                cleaned,
            )
            cleaned = cleaned.replace(url, f"~~{url}~~ *(fabricated — not in collected sources)*")
        return cleaned, fabricated

    async def _verify(self, synthesis: str, sources: List[Dict],
                       session: ResearchSession, request, user: Dict) -> Dict:
        if not sources:
            return {"issues": [], "overall_credibility": "very_low", "recommendation": "flag_for_user"}
        source_list = "\n".join(
            f"[Source {i}] {s.get('title', '?')} — {s.get('url', 'N/A')}"
            for i, s in enumerate(sources, 1)
        )
        try:
            result = await self._sa.run_json(
                _VERIFICATION_PROMPT,
                f"# Research Anchor\n{session.anchor}\n\n# Collected Sources\n{source_list}\n\n# Synthesis to Verify\n{synthesis}",
                request, user,
            )
            if isinstance(result, dict):
                return result
            return {"issues": [], "overall_credibility": "medium", "recommendation": "pass"}
        except Exception as e:
            logger.warning("Verification failed: %s", e)
            return {"issues": [], "overall_credibility": "unknown", "recommendation": "pass"}

    @staticmethod
    def _credibility_report(verification: Dict, scrubbed: List[str], sources: List[Dict]) -> str:
        parts = []
        credibility = verification.get("overall_credibility", "unknown")
        issues = verification.get("issues", [])
        critical = [i for i in issues if isinstance(i, dict) and i.get("severity") == "critical"]
        warnings = [i for i in issues if isinstance(i, dict) and i.get("severity") == "warning"]

        parts.append("\n\n---\n\n## Research Credibility Report\n")
        source_count = len(sources)
        if source_count == 0:
            parts.append("⚠️ **No sources collected.** This synthesis has no evidentiary basis.\n")
        else:
            domains = len(set(s.get("domain", "") for s in sources if s.get("domain")))
            parts.append(f"- **Evidence basis:** {source_count} source(s) from {domains} domain(s)\n")

        labels = {
            "high": "🟢 High — claims well-supported by diverse sources",
            "medium": "🟡 Medium — some claims supported, gaps remain",
            "low": "🟠 Low — thin evidence, significant gaps",
            "very_low": "🔴 Very Low — insufficient evidence for reliable conclusions",
            "unknown": "⚪ Unknown — verification could not be completed",
        }
        parts.append(f"- **Credibility:** {labels.get(credibility, credibility)}\n")

        if scrubbed:
            parts.append(f"\n### ⚠️ Fabricated URLs Removed ({len(scrubbed)})\n")
            for url in scrubbed:
                parts.append(f"- ~~{url}~~\n")

        if critical:
            parts.append(f"\n### 🔴 Critical Issues ({len(critical)})\n")
            for i in critical:
                parts.append(f"- **{i.get('type', '?')}**: {i.get('detail', '')}\n")

        if warnings:
            parts.append(f"\n### 🟡 Warnings ({len(warnings)})\n")
            for i in warnings:
                parts.append(f"- **{i.get('type', '?')}**: {i.get('detail', '')}\n")

        rec = verification.get("recommendation", "pass")
        if rec == "revise":
            parts.append("\n**⚠️ Recommendation:** Cross-check key claims before relying on them.\n")
        elif rec == "flag_for_user":
            parts.append("\n**🔴 Recommendation:** Evidence insufficient. Consider `deep_research()` or refine query.\n")

        return "".join(parts)

    @staticmethod
    def _fallback(session: ResearchSession) -> str:
        lines = [f"# Research Summary (Fallback)\n\n**Query:** {session.query}\n"]
        for it in session.iterations:
            lines.append(f"\n## Iteration {it.iteration_number}\n- Terms: {', '.join(it.search_terms)}\n- Chunks: {it.chunks_found} (new: {it.new_chunks})\n")
            if it.summary:
                lines.append(f"\n{it.summary}\n")
        lines.append("\n*Full LLM synthesis unavailable — raw summaries above.*")
        return "\n".join(lines)


# =============================================================================
#  Quick Research (web-search only)
# =============================================================================

# _WEB_SEARCH_PROMPT removed — search results now come directly from search_web()

_RELEVANCE_GATE_PROMPT = """\
You are a strict relevance AND credibility judge. Given a RESEARCH ANCHOR \
and a list of web search results, judge each result on TWO axes.

**Axis 1 — Relevance:**
- "relevant": addresses the anchor's topic area, key concepts, or must_cover \
items — even if only partially. Err on the side of inclusion.
- "trail": tangentially related — broader field but not the specific topic.
- "drop": completely off-topic, about a different subject entirely.

**Axis 2 — Source Authority (0.0–1.0):**
- 1.0: Official documentation, primary project source, RFC/spec
- 0.8: Established tech publications (MDN, DigitalOcean, etc.)
- 0.6: Reputable blog posts, Stack Overflow accepted answers
- 0.4: Forum posts, personal blogs, undated content
- 0.2: Content farms, AI-generated summaries, aggregator sites
- 0.0: Obvious spam, placeholder, or fabricated content

Return JSON array in the same order as the input:
[{{"index": 0, "verdict": "relevant"|"trail"|"drop", "authority": 0.0-1.0, \
"reason": "one sentence"}}]

IMPORTANT: You are judging based on short search snippets, not full articles. \
Be generous with relevance — if the title or snippet plausibly relates to the \
anchor, mark it "relevant". Only "drop" truly unrelated results.
Respond ONLY with valid JSON.\
"""

_EXTRACT_TOPICS_PROMPT = """\
You are a research strategist. Given a RESEARCH ANCHOR and a set of \
relevant sources that were just confirmed to match the user's query, \
extract:

1. **Deeper topics**: specific sub-topics, techniques, or terms mentioned \
IN the relevant sources that would yield even more targeted results if \
searched directly.
2. **Adjacent leads**: related topics from 'trail' sources that could \
connect to relevant material if pursued one level deeper.

Return JSON:
{{"deeper_terms": ["specific term from source content to search next"],
  "adjacent_leads": ["terms from trail sources worth pursuing"],
  "covered_so_far": ["anchor concepts now fully covered"]}}

Stay anchored \u2014 only suggest terms that serve the user's original query.\
"""

_PIVOT_PROMPT = """\
The previous web search returned NO results relevant to the RESEARCH ANCHOR.
Generate 3-5 completely different search terms to approach the topic from \
new angles. Strategies:
- Use different terminology or synonyms for the same concepts
- Search for the PROBLEM the user is trying to solve, not the solution
- Try specific authors, tools, frameworks, or competing projects
- Search for academic/research terms instead of marketing terms
- Try contrasting viewpoints: "limitations of X" or "alternatives to X"
- Do NOT just rephrase the same query \u2014 genuinely pivot

Return JSON: {{"terms": ["term1", "term2", "term3"], "strategy": "one sentence"}}\
"""

_ANALYSIS_PROMPT = """\
Analyze collected web sources against the RESEARCH ANCHOR.

1. Summarize what the sources cover well.
2. Identify which specific aspects of the anchor are NOT yet \
addressed (gaps). Be precise \u2014 quote the anchor's must_cover items.
3. Suggest search terms that would specifically fill those gaps.

Return JSON:
{{"summary":"2-3 paragraphs","gaps":["specific unaddressed aspects"],"covered_aspects":["aspects well-covered"],"new_terms":["terms targeting the gaps"],"new_concepts":["concepts discovered"]}}\
"""


class _QuickResearcher:
    """Goal-driven research: iterate until min_relevant_sources are found.

    Flow per iteration:
    1. Web search with current terms
    2. Relevance gate: classify each result as relevant / trail / drop
    3. If relevant hits found -> extract deeper topics from them
       If no relevant hits -> pivot to completely different search terms
    4. Repeat until enough relevant sources accumulated or max_iterations hit
    5. Synthesize using ALL sources (relevant + trail chain)
    """

    def __init__(self, valves, sa: _SubAgent, j: _Journal, synth: _Synthesizer):
        self._v = valves
        self._sa = sa
        self._j = j
        self._synth = synth

    async def run(self, query: str, user_id: str, request, user: Dict, model_id: str, emitter=None) -> str:
        slug = _Journal.slugify(query)
        sdir = self._j.resolve_session_dir(user_id, slug, namespace="research")
        session = ResearchSession(session_id=f"research-{slug}", query=query, session_dir=sdir, model_id=model_id)
        self._j.write_prompt(session, model_id)
        await _emit(emitter, "\U0001f4cb Research session started")

        # Extract anchor once -- threads through every subsequent prompt
        session.anchor = await _extract_anchor(self._sa, query, request, user)
        self._j.write_anchor(session)
        await _emit(emitter, "\U0001f3af Research anchor extracted")

        session.phase = ResearchPhase.RESEARCHING
        relevant_sources: List[Dict] = []       # confirmed anchor-matching
        trail_sources: List[Dict] = []           # led us toward relevant hits
        seen_urls: set = set()
        search_terms = [query]
        tried_terms: set = set()
        target = self._v.min_relevant_sources
        consecutive_misses = 0

        for n in range(1, self._v.max_iterations + 1):
            # --- Step 1: Web search ---
            new_terms = [t for t in search_terms if t not in tried_terms]
            if not new_terms and n > 1:
                await _emit(emitter, "\u2705 No new terms to explore")
                break
            tried_terms.update(new_terms)

            raw = await self._web_search(session, " OR ".join(f'"{t}"' for t in new_terms) if len(new_terms) > 1 else new_terms[0], request, user)
            raw = [r for r in raw if r.get("url", "") not in seen_urls]
            seen_urls.update(r.get("url", "") for r in raw)

            if not raw:
                consecutive_misses += 1
                it = IterationResult(n, new_terms, ["web_search"], 0, 0, "No results returned.", [])
                session.iterations.append(it)
                self._j.write_iteration(session, it)
                await _emit(emitter, f"\U0001f504 Iter {n}: 0 results \u2014 pivoting")
                search_terms = await self._pivot(session, tried_terms, request, user)
                continue

            # --- Step 2: Relevance gate ---
            rel, trail, dropped = await self._relevance_gate(session, raw, request, user)

            relevant_sources.extend(rel)
            trail_sources.extend(trail)
            all_kept = rel + trail
            await self._store_sources(session, all_kept, n)

            rel_count = len(relevant_sources)
            summary = ""

            # --- Step 3: Branch based on whether we got relevant hits ---
            if rel:
                consecutive_misses = 0
                # Extract deeper topics from the relevant sources
                extraction = await self._extract_topics(session, rel, trail, request, user)
                deeper = extraction.get("deeper_terms", [])
                adjacent = extraction.get("adjacent_leads", [])
                covered = extraction.get("covered_so_far", [])
                summary = (f"Found {len(rel)} relevant, {len(trail)} trail, dropped {dropped}. "
                           f"Covered: {', '.join(covered[:3])}. Deeper: {', '.join(deeper[:3])}.")
                search_terms = deeper + adjacent  # dive deeper
                await _emit(emitter, f"\U0001f3af Iter {n}: +{len(rel)} relevant ({rel_count} total), +{len(trail)} trail \u2014 diving deeper")
            else:
                # Trail sources indicate on-topic results — only a full miss
                # when we get zero trail AND zero relevant
                if trail:
                    consecutive_misses = max(0, consecutive_misses)  # don't increment
                    summary = f"No direct hits but {len(trail)} trail, dropped {dropped}. Refining."
                    # Use trail content to inform next search instead of hard pivot
                    extraction = await self._extract_topics(session, [], trail, request, user)
                    search_terms = extraction.get("deeper_terms", []) + extraction.get("adjacent_leads", [])
                    if not search_terms:
                        search_terms = await self._pivot(session, tried_terms, request, user)
                    await _emit(emitter, f"\U0001f504 Iter {n}: 0 relevant, {len(trail)} trail \u2014 refining")
                else:
                    consecutive_misses += 1
                    summary = f"No results relevant to anchor. Pivoting (miss {consecutive_misses})."
                    search_terms = await self._pivot(session, tried_terms, request, user)
                    await _emit(emitter, f"\U0001f504 Iter {n}: 0 results \u2014 pivoting ({consecutive_misses})")

            it = IterationResult(n, new_terms, ["web_search"], len(raw), len(all_kept), summary, [])
            session.iterations.append(it)
            self._j.write_iteration(session, it)

            # --- Step 4: Check goal ---
            if rel_count >= target:
                # Have enough sources, but check for gaps before stopping
                analysis = await self._analyze(session, request, user)
                gaps = analysis.get("gaps", [])
                gap_terms = analysis.get("new_terms", [])
                if gaps and gap_terms and n < self._v.max_iterations:
                    # Gaps remain and we have iterations left — keep going
                    search_terms = gap_terms
                    await _emit(emitter, f"\u2705 {rel_count}/{target} sources but gaps remain: {', '.join(gaps[:2])} \u2014 continuing")
                else:
                    await _emit(emitter, f"\u2705 Target reached: {rel_count}/{target} relevant sources")
                    if gaps:
                        await _emit(emitter, f"\U0001f50d Remaining gaps: {', '.join(gaps[:3])}")
                    break

            if consecutive_misses >= 3:
                await _emit(emitter, f"\u26a0\ufe0f 3 consecutive misses \u2014 proceeding with {rel_count} relevant")
                break

        # --- Final analysis (only if not already done in loop) ---
        if not (rel_count >= target):
            analysis = await self._analyze(session, request, user)
            if analysis.get("gaps"):
                await _emit(emitter, f"\U0001f50d Remaining gaps: {', '.join(analysis['gaps'][:3])}")

        # --- Synthesize ---
        session.phase = ResearchPhase.SYNTHESIZING
        await _emit(emitter, f"\U0001f9e0 Synthesizing ({len(relevant_sources)} relevant + {len(trail_sources)} trail sources)...")
        answer = await self._synth.synthesize(session, request, user,
                                               relevant_sources=relevant_sources,
                                               trail_sources=trail_sources)
        session.phase = ResearchPhase.COMPLETE
        await _emit(emitter, f"\U0001f4c1 Journal: research/{slug}/", done=True)

        if len(relevant_sources) < target:
            answer += (f"\n\n---\n\n\u26a0\ufe0f *Only {len(relevant_sources)}/{target} relevant sources found. "
                       f"Consider `deep_research()` to crawl authoritative domains.*")
        return answer

    # --- Search helpers ---

    async def _web_search(self, session, query, request, user):
        """Call OWUI's search_web() directly — bypasses the LLM entirely."""
        from open_webui.routers.retrieval import search_web
        from starlette.concurrency import run_in_threadpool

        engine = getattr(request.app.state.config, "WEB_SEARCH_ENGINE", "")
        if not engine:
            logger.warning("No WEB_SEARCH_ENGINE configured in OWUI admin settings")
            return []

        try:
            results = await run_in_threadpool(search_web, request, engine, query)
        except Exception as e:
            logger.warning("search_web failed for '%s': %s", query[:80], e)
            return []

        parsed = []
        for r in results[:self._v.max_web_results]:
            domain = ""
            try:
                domain = urlparse(r.link).netloc
            except Exception:
                pass
            parsed.append({
                "url": r.link,
                "title": r.title or "",
                "summary": r.snippet or "",
                "domain": domain,
            })

        logger.info("Direct web search for '%s': %d results", query[:60], len(parsed))
        return parsed

    # --- Relevance gate: returns (relevant, trail, drop_count) ---

    async def _relevance_gate(self, session, sources, request, user):
        if not sources:
            return [], [], 0
        summaries = "\n".join(
            f"{i}. [{s.get('domain','')}] {s.get('title','?')}: {s.get('summary','')[:150]}"
            for i, s in enumerate(sources))
        try:
            verdicts = await self._sa.run_json(_RELEVANCE_GATE_PROMPT,
                f"{session.anchor}\n\nResults to judge:\n{summaries}", request, user)
            if not isinstance(verdicts, list):
                return sources, [], 0  # can't parse -- keep all as relevant
            relevant, trail = [], []
            for v in verdicts:
                if not isinstance(v, dict):
                    continue
                idx = v.get("index", -1)
                if 0 <= idx < len(sources):
                    verdict = v.get("verdict", "drop")
                    authority = v.get("authority", 0.5)
                    sources[idx]["authority"] = authority
                    sources[idx]["gate_reason"] = v.get("reason", "")
                    if verdict == "relevant":
                        relevant.append(sources[idx])
                    elif verdict == "trail":
                        trail.append(sources[idx])
            dropped = len(sources) - len(relevant) - len(trail)
            relevant.sort(key=lambda s: s.get("authority", 0.5), reverse=True)
            logger.info("Relevance gate: %d relevant, %d trail, %d dropped", len(relevant), len(trail), dropped)
            return relevant, trail, dropped
        except Exception:
            return sources, [], 0

    # --- Extract deeper topics from relevant hits ---

    async def _extract_topics(self, session, relevant, trail, request, user):
        rel_text = "\n\n".join(
            f"**[{s.get('domain','')}] {s.get('title','?')}**\n{s.get('summary','')}"
            for s in relevant[:10])
        trail_text = "\n\n".join(
            f"**[{s.get('domain','')}] {s.get('title','?')}**\n{s.get('summary','')}"
            for s in trail[:5])
        try:
            return await self._sa.run_json(_EXTRACT_TOPICS_PROMPT,
                f"{session.anchor}\n\n## Relevant Sources\n{rel_text}\n\n## Trail Sources\n{trail_text}",
                request, user)
        except Exception:
            return {"deeper_terms": [], "adjacent_leads": [], "covered_so_far": []}

    # --- Pivot: generate completely new terms when nothing relevant found ---

    async def _pivot(self, session, tried_terms, request, user):
        tried_str = ", ".join(sorted(tried_terms)[:20])
        iters = "\n".join(f"- Iter {i.iteration_number}: {i.summary[:150]}" for i in session.iterations)
        try:
            r = await self._sa.run_json(_PIVOT_PROMPT,
                f"{session.anchor}\n\nAlready tried: {tried_str}\nResults so far:\n{iters}",
                request, user)
            return r.get("terms", [])
        except Exception:
            return []

    # --- Storage ---

    async def _store_sources(self, session, sources, iteration=0):
        sdir = os.path.join(session.session_dir, "sources")
        os.makedirs(sdir, exist_ok=True)
        prefix = f"iter{iteration}-" if iteration else ""
        for i, s in enumerate(sources, 1):
            domain = s.get("domain", "unknown")
            with open(os.path.join(sdir, f"{prefix}{domain}-{i}.md"), "w", encoding="utf-8") as f:
                f.write(f"# {s.get('title', domain)}\n\n[Source: {s.get('url', '')}]\n[Relevance: {s.get('relevance', 0.0)}]\n\n## Content\n\n{s.get('summary', '')}\n")
        idx = ["# Sources\n"] + [f"{i}. **{s.get('title', '?')}** ({s.get('domain', '')}) \u2014 [{s.get('url', '')}]({s.get('url', '')})\n   {s.get('summary', '')[:200]}\n" for i, s in enumerate(sources, 1)]
        self._j.write_entry(session.session_dir, f"sources-iter{iteration}.md", "\n".join(idx))

    # --- Final analysis ---

    async def _analyze(self, session, request, user):
        sdir = os.path.join(session.session_dir, "sources")
        texts = []
        if os.path.isdir(sdir):
            for fn in sorted(os.listdir(sdir)):
                fp = os.path.join(sdir, fn)
                if os.path.isfile(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        texts.append(f.read())
        if not texts:
            return {"summary": "No sources.", "gaps": ["entire query uncovered"], "new_terms": [], "covered_aspects": []}
        try:
            return await self._sa.run_json(_ANALYSIS_PROMPT,
                f"{session.anchor}\n\nSources ({len(texts)}):\n\n" + "\n\n---\n\n".join(texts[:15]), request, user)
        except Exception:
            return {"summary": f"Found {len(texts)} sources.", "gaps": [], "new_terms": [], "covered_aspects": []}


#  Status emitter helper
# =============================================================================


async def _emit(emitter, msg: str, done: bool = False):
    if emitter:
        await emitter({"type": "status", "data": {"description": msg, "done": done}})


# =============================================================================
#  Tools (main entry point for OWUI)
# =============================================================================


class Tools:
    """Deep Research Tools for Open WebUI.

    Two tool methods:
    - research(query): Quick web-search-based exploration
    - deep_research(query): Full pipeline — discover, crawl, RAG, synthesize
    """

    class Valves(BaseModel):
        smolcrawl_url: str = Field(default="http://smolcrawl-pipelines:9099", description="SmolCrawl pipeline container URL")
        smolcrawl_api_key: str = Field(default="0p3n-w3bu!", description="Pipelines server API key")
        owui_base_url: str = Field(default="http://openwebui:8080", description="Open WebUI API base URL")
        owui_api_key: str = Field(default="", description="Bearer token for OWUI API")
        max_iterations: int = Field(default=5, ge=1, le=15, description="Hard cap on research iterations")
        fixed_iterations: int = Field(default=2, ge=1, le=5, description="Guaranteed iterations before continue-decision")
        min_relevant_sources: int = Field(default=5, ge=1, le=30, description="Target: stop researching once this many anchor-relevant sources are found")
        max_web_results: int = Field(default=10, ge=1, le=50, description="Max web search results per query")
        include_sources: bool = Field(default=True, description="Append source references to answer")
        top_k_per_collection: int = Field(default=5, ge=1, le=20, description="Chunks per collection per query")
        max_collections: int = Field(default=10, ge=1, le=50, description="Max collections to search")
        max_domains: int = Field(default=5, ge=1, le=20, description="Max domains to discover")
        auto_approve_domains: bool = Field(default=True, description="Auto-approve all non-covered domains (skip manual approval)")
        fileshed_compatible: bool = Field(default=True, description="Write journal to Fileshed Storage zone")
        storage_base_path: str = Field(default="/app/backend/data/user_files", description="Fileshed storage base path")
        save_journal: bool = Field(default=True, description="Persist research journal to disk")

    def __init__(self):
        self.valves = self.Valves()

    async def research(
        self, query: str,
        __user__: dict = None, __metadata__: dict = None, __event_emitter__=None,
        __request__=None, __model__: dict = None, __event_call__=None,
        __chat_id__: str = "", __message_id__: str = "",
    ) -> str:
        """Quick research on a topic using web search. Stores findings to
        Fileshed and iteratively expands search terms. Faster than
        deep_research — use this to scope a topic first.

        Args:
            query: The research question or topic to explore.
        """
        mid = _SubAgent.resolve_model_id(__metadata__, __model__)
        sa = _SubAgent(mid)
        j = _Journal(self.valves)
        syn = _Synthesizer(self.valves, sa, j)
        return await _QuickResearcher(self.valves, sa, j, syn).run(
            query, (__user__ or {}).get("id", ""), __request__, __user__ or {}, mid, __event_emitter__)

    async def deep_research(
        self, query: str,
        __user__: dict = None, __metadata__: dict = None, __event_emitter__=None,
        __request__=None, __model__: dict = None, __event_call__=None,
        __chat_id__: str = "", __message_id__: str = "",
    ) -> str:
        """Deep research on a topic. Discovers relevant domains via web
        search, crawls them into knowledge collections, runs iterative
        RAG retrieval, and synthesizes a comprehensive answer.

        The full pipeline runs automatically: discover → crawl → research → synthesize.

        Args:
            query: The research question or topic to investigate.
        """
        mid = _SubAgent.resolve_model_id(__metadata__, __model__)
        sa = _SubAgent(mid)
        j = _Journal(self.valves)
        disc = _Discovery(self.valves, sa)
        rag = _RagResearcher(self.valves, sa)
        crawl = _CrawlClient(self.valves)
        synth = _Synthesizer(self.valves, sa, j)

        slug = _Journal.slugify(query)
        sdir = j.resolve_session_dir((__user__ or {}).get("id", ""), slug)
        session = ResearchSession(session_id=str(_uuid.uuid4()), query=query, session_dir=sdir, model_id=mid)
        j.write_prompt(session, mid)
        await _emit(__event_emitter__, "📋 Deep research started")

        # Extract anchor once — threads through all subsequent prompts
        session.anchor = await _extract_anchor(sa, query, __request__, __user__ or {})
        j.write_anchor(session)
        await _emit(__event_emitter__, "🎯 Research anchor extracted")

        # --- Phase 1: Discover domains and check existing collections ---
        session.phase = ResearchPhase.DISCOVERING
        all_cols = await rag.list_collections()
        rel_ids = await disc.rank_collections(query, all_cols, __request__, __user__ or {})
        session.relevant_collection_ids = rel_ids
        rel_cols = [c for c in all_cols if c["id"] in rel_ids]
        await _emit(__event_emitter__, f"📚 {len(all_cols)} collection(s), {len(rel_ids)} relevant")

        domains = await disc.discover_domains(query, __request__, __user__ or {})
        domains = disc.check_coverage(domains, all_cols)
        session.discovered_domains = domains
        j.write_domains(session, rel_cols)

        # --- Phase 2: Auto-approve and crawl new domains ---
        approved = [d for d in domains if not d.already_covered]
        if approved:
            session.phase = ResearchPhase.CRAWLING
            names = ", ".join(d.domain for d in approved[:5])
            await _emit(__event_emitter__, f"🕷️ Crawling {len(approved)} domain(s): {names}")
            for d in approved:
                kb = f"SmolCrawl - {d.domain}"
                r = await crawl.trigger_crawl(d.domain, kb, __event_emitter__)
                session.crawl_results.append(r)
                if r.success and r.kb_id:
                    session.relevant_collection_ids.append(r.kb_id)
            j.write_crawl_status(session)
            ok = sum(1 for r in session.crawl_results if r.success)
            await _emit(__event_emitter__, f"✅ Crawled {ok}/{len(approved)} domain(s)")
        else:
            await _emit(__event_emitter__, "📚 All domains already in knowledge base")

        # Refresh collections after crawl to pick up new KB IDs
        all_cols = await rag.list_collections()
        col_map = {c["id"]: c["name"] for c in all_cols}
        for cr in session.crawl_results:
            if cr.success:
                for c in all_cols:
                    if c["name"] == cr.kb_name:
                        if c["id"] not in session.relevant_collection_ids:
                            session.relevant_collection_ids.append(c["id"])
                        cr.kb_id = c["id"]
                        break

        # --- Phase 3: Iterative RAG research ---
        session.phase = ResearchPhase.RESEARCHING
        terms = [session.query]
        for n in range(1, self.valves.max_iterations + 1):
            await _emit(__event_emitter__, f"🔍 Research iteration {n}...")
            it = await rag.run_iteration(session, terms, session.relevant_collection_ids, col_map, n, __request__, __user__ or {})
            j.write_iteration(session, it)
            await _emit(__event_emitter__, f"📚 Iter {n}: {it.new_chunks} new chunk(s)")
            terms = await rag.expand_terms(session, terms, __request__, __user__ or {})
            if n >= self.valves.fixed_iterations:
                if n >= self.valves.max_iterations:
                    break
                if not await rag.should_continue(session, __request__, __user__ or {}):
                    await _emit(__event_emitter__, "✅ Research complete")
                    break

        # --- Phase 4: Synthesize ---
        session.phase = ResearchPhase.SYNTHESIZING
        await _emit(__event_emitter__, "🧠 Synthesizing findings...")
        answer = await synth.synthesize(session, __request__, __user__ or {})
        session.phase = ResearchPhase.COMPLETE
        await _emit(__event_emitter__, f"📁 Journal: deep-research/{slug}/", done=True)
        return answer
