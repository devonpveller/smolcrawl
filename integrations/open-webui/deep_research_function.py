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


class _SubAgent:
    def __init__(self, model_id: str):
        self._model_id = model_id

    async def run(self, system_prompt: str, user_prompt: str, request, user: Dict,
                  enable_web_search: bool = False) -> str:
        from open_webui.utils.chat import generate_chat_completion
        from open_webui.models.users import UserModel

        form_data = {
            "model": self._model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "metadata": {
                "task": "deep_research_sub_agent",
                **({"features": {"web_search": True}} if enable_web_search else {}),
            },
        }
        response = await generate_chat_completion(
            request=request, form_data=form_data,
            user=UserModel(**user), bypass_filter=True,
        )
        return response["choices"][0]["message"]["content"]

    async def run_json(self, system_prompt: str, user_prompt: str, request, user: Dict,
                       enable_web_search: bool = False) -> Any:
        raw = await self.run(system_prompt, user_prompt, request, user, enable_web_search)
        return _parse_json(raw)

    @staticmethod
    def resolve_model_id(metadata: Optional[Dict], model: Optional[Dict]) -> str:
        return (((metadata or {}).get("model") or {}).get("id", "")
                or (model or {}).get("id", ""))


def _parse_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}...")


# =============================================================================
#  Domain Discovery
# =============================================================================

_DISCOVERY_PROMPT = """\
You are a research librarian. Given a research topic, search the web to \
identify the most authoritative documentation sources.

Return a JSON array of objects, each with:
- "url": full URL of the documentation root
- "domain": the domain name
- "score": relevance 0.0-1.0
- "rationale": one-sentence explanation

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
        try:
            data = await self._sa.run_json(
                _DISCOVERY_PROMPT.format(max_domains=self._v.max_domains),
                f"Find authoritative web sources for researching: {query}",
                request, user, enable_web_search=True)
        except Exception as e:
            logger.error("Domain discovery failed: %s", e)
            return []
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
You are a research assistant analyzing RAG retrieval results. Given the \
original query and findings so far, identify adjacent concepts and new terms.

Return JSON: {"terms": ["term1","term2"], "concepts": ["c1","c2"], "summary": "2-3 paragraph summary"}\
"""

_CONTINUE_PROMPT = """\
Evaluate whether another research iteration would yield meaningful new info. \
Return JSON: {"continue": true/false, "rationale": "one sentence"}\
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
                    f"Original query: {session.query}\nTerms: {', '.join(terms)}\n\nRetrieved ({len(new_chunks)} chunks):\n\n{ctx}",
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
                f"Query: {session.query}\nPrevious terms: {', '.join(current)}\nFindings:\n{sums}\nSuggest new terms.",
                request, user)
            return r.get("terms", current)
        except Exception:
            return current

    async def should_continue(self, session: ResearchSession, request, user: Dict) -> bool:
        sums = "\n".join(f"Iter {i.iteration_number}: new={i.new_chunks}, concepts={', '.join(i.new_concepts)}" for i in session.iterations)
        try:
            r = await self._sa.run_json(_CONTINUE_PROMPT, f"Query: {session.query}\n\n{sums}", request, user)
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
You are a research synthesizer. Given a research query, iteration summaries, \
and relevant content, produce a comprehensive answer.

Structure:
## Reasoning  (step-by-step chain of thought)
## Answer     (comprehensive answer)
## Sources    (key sources cited)
## Gaps       (remaining unknowns)\
"""


class _Synthesizer:
    def __init__(self, valves, sub_agent: _SubAgent, journal: _Journal):
        self._v = valves
        self._sa = sub_agent
        self._j = journal

    async def synthesize(self, session: ResearchSession, request, user: Dict) -> str:
        prompt_md = self._j.read_entry(session.session_dir, "00-prompt.md")
        iter_mds = []
        for it in session.iterations:
            fn = f"{it.iteration_number + 2:02d}-iteration-{it.iteration_number}.md"
            c = self._j.read_entry(session.session_dir, fn)
            if c:
                iter_mds.append(c)

        parts = [f"# Original Query\n\n{session.query}\n"]
        if prompt_md:
            parts.append(f"# Context\n\n{prompt_md}\n")
        for i, md in enumerate(iter_mds, 1):
            parts.append(f"# Iteration {i}\n\n{md}\n")
        parts.append("\n---\nProduce a comprehensive, well-cited synthesis.")

        try:
            answer = await self._sa.run(_SYNTHESIS_PROMPT, "\n\n".join(parts), request, user)
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

_WEB_SEARCH_PROMPT = """\
Search the web for authoritative information about the topic.
Return JSON array: [{{"url":"...","domain":"...","title":"...","summary":"2-3 sentences","relevance":0.0-1.0}}]
Return at most {max_results} results. Respond ONLY with valid JSON.\
"""

_ANALYSIS_PROMPT = """\
Analyze collected web sources. Return JSON:
{{"summary":"2-3 paragraphs","gaps":["..."],"new_terms":["..."],"new_concepts":["..."]}}\
"""

_EXPAND_PROMPT = """\
Given findings so far, suggest new search terms. Return JSON:
{{"terms":["term1","term2"],"rationale":"explanation"}}\
"""


class _QuickResearcher:
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
        await _emit(emitter, "📋 Research session started")

        session.phase = ResearchPhase.RESEARCHING
        sources = await self._web_search(query, request, user)
        await self._store_sources(session, sources)
        await _emit(emitter, f"🌐 Found {len(sources)} source(s)")

        analysis = await self._analyze(session, request, user)
        terms = [query] + analysis.get("new_terms", [])
        it = IterationResult(1, [query], ["web_search"], len(sources), len(sources),
                             analysis.get("summary", ""), analysis.get("new_concepts", []))
        session.iterations.append(it)
        self._j.write_iteration(session, it)

        seen = {s.get("url", "") for s in sources}
        for n in range(2, self._v.max_iterations + 1):
            expanded = await self._expand(session, terms, request, user)
            new_t = [t for t in expanded if t not in terms]
            if not new_t:
                break
            new_src = await self._search_terms(new_t, seen, request, user)
            if new_src:
                await self._store_sources(session, new_src)
                seen.update(s.get("url", "") for s in new_src)
            analysis2 = await self._analyze(session, request, user)
            it2 = IterationResult(n, new_t, ["web_search"], len(new_src), len(new_src),
                                  analysis2.get("summary", ""), analysis2.get("new_concepts", []))
            session.iterations.append(it2)
            self._j.write_iteration(session, it2)
            terms += new_t
            await _emit(emitter, f"🔄 Expanding: {', '.join(new_t[:3])}")
            if n >= self._v.fixed_iterations:
                try:
                    r = await self._sa.run_json(_CONTINUE_PROMPT, f"Query: {query}\nIters: " +
                        "\n".join(f"Iter {i.iteration_number}: {i.new_chunks} sources" for i in session.iterations), request, user)
                    if not r.get("continue", False):
                        break
                except Exception:
                    break

        session.phase = ResearchPhase.SYNTHESIZING
        await _emit(emitter, "🧠 Synthesizing...")
        answer = await self._synth.synthesize(session, request, user)
        session.phase = ResearchPhase.COMPLETE
        await _emit(emitter, f"📁 Journal: research/{slug}/", done=True)

        if len(session.iterations) >= 2 and sum(i.chunks_found for i in session.iterations) >= 5:
            answer += ("\n\n---\n\n💡 *For deeper analysis, consider `deep_research()` to crawl "
                       "authoritative sources into permanent knowledge collections.*")
        return answer

    async def _web_search(self, query, request, user):
        try:
            return await self._sa.run_json(
                _WEB_SEARCH_PROMPT.format(max_results=self._v.max_web_results),
                f"Search for: {query}", request, user, enable_web_search=True)
        except Exception:
            return []

    async def _search_terms(self, terms, seen, request, user):
        q = " OR ".join(f'"{t}"' for t in terms)
        results = await self._web_search(q, request, user)
        return [r for r in results if r.get("url", "") not in seen]

    async def _store_sources(self, session, sources):
        sdir = os.path.join(session.session_dir, "sources")
        os.makedirs(sdir, exist_ok=True)
        for i, s in enumerate(sources, 1):
            domain = s.get("domain", "unknown")
            with open(os.path.join(sdir, f"{domain}-{i}.md"), "w", encoding="utf-8") as f:
                f.write(f"# {s.get('title', domain)}\n\n[Source: {s.get('url', '')}]\n[Relevance: {s.get('relevance', 0.0)}]\n\n## Content\n\n{s.get('summary', '')}\n")
        idx = ["# Sources\n"] + [f"{i}. **{s.get('title', '?')}** ({s.get('domain', '')}) — {s.get('relevance', 0):.2f}\n" for i, s in enumerate(sources, 1)]
        self._j.write_entry(session.session_dir, "01-sources.md", "\n".join(idx))

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
            return {"summary": "No sources.", "gaps": [], "new_terms": []}
        try:
            return await self._sa.run_json(_ANALYSIS_PROMPT,
                f"Query: {session.query}\n\nSources:\n\n" + "\n\n---\n\n".join(texts[:15]), request, user)
        except Exception:
            return {"summary": f"Found {len(texts)} sources.", "gaps": [], "new_terms": []}

    async def _expand(self, session, terms, request, user):
        sums = "\n".join(f"- Iter {i.iteration_number}: {i.summary[:200]}" for i in session.iterations)
        try:
            r = await self._sa.run_json(_EXPAND_PROMPT,
                f"Query: {session.query}\nCurrent: {', '.join(terms)}\n{sums}", request, user)
            return r.get("terms", [])
        except Exception:
            return []


# =============================================================================
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
        max_iterations: int = Field(default=3, ge=1, le=10, description="Hard cap on research iterations")
        fixed_iterations: int = Field(default=2, ge=1, le=5, description="Guaranteed iterations before continue-decision")
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
