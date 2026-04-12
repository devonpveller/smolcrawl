"""
Goal-driven web-search research (research() method logic).

Single Responsibility: Handles the lightweight research flow that uses
web search + Fileshed. Iterates until min_relevant_sources are
accumulated, using relevance gating and topic extraction to dive deeper.
"""

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .journal import ResearchJournal
from .models import IterationResult, ResearchPhase, ResearchSession, Valves
from .sub_agent import SubAgent, extract_anchor
from .synthesis import Synthesizer

logger = logging.getLogger("deep_research.research")

_WEB_SEARCH_SYSTEM_PROMPT = """\
Search the web for authoritative information about the topic below.

IMPORTANT: Cover ALL specific concepts, terms, and proper nouns mentioned \
in the RESEARCH ANCHOR. If the anchor mentions a specific technique, \
framework, or term, ensure at least some results address that term \
directly \u2014 do not substitute a broader or adjacent topic.

Return JSON array: [{{"url":"...","domain":"...","title":"...","summary":"2-3 sentences","relevance":0.0-1.0}}]
Return at most {max_results} results. Respond ONLY with valid JSON.\
"""

_RELEVANCE_GATE_PROMPT = """\
You are a strict relevance judge. Given a RESEARCH ANCHOR and a list of \
web search results, judge each result.

For EACH result, decide:
- "relevant": directly addresses one or more key concepts / must_cover items from the anchor
- "trail": partially related \u2014 it doesn't answer the query directly but \
could lead to deeper, more relevant sources (e.g. overview pages, indexes, related-topic pages)
- "drop": completely off-topic, about a different subject, or too vague

Return JSON array in the same order as the input:
[{{"index": 0, "verdict": "relevant"|"trail"|"drop", "reason": "one sentence"}}]

Be strict \u2014 'relevant' means the source specifically addresses the user's \
concepts. Broader or adjacent topics are 'trail' at best.
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
Generate completely different search terms to approach the topic from a \
new angle. Think about:
- Different terminology for the same concepts
- The problem the user is trying to solve (search for that instead)
- Specific authors, tools, or projects related to the anchor's must_cover items

Return JSON: {{"terms": ["new_term1", "new_term2", "new_term3"], "strategy": "one sentence explaining the pivot"}}\
"""

_ANALYSIS_SYSTEM_PROMPT = """\
Analyze collected web sources against the RESEARCH ANCHOR.

1. Summarize what the sources cover well.
2. Identify which specific aspects of the anchor are NOT yet \
addressed (gaps). Be precise \u2014 quote the anchor's must_cover items.
3. Suggest search terms that would specifically fill those gaps.

Return JSON:
{{"summary":"2-3 paragraphs","gaps":["specific unaddressed aspects"],"covered_aspects":["aspects well-covered"],"new_terms":["terms targeting the gaps"],"new_concepts":["concepts discovered"]}}\
"""


class QuickResearcher:
    """Goal-driven research: iterate until min_relevant_sources are found.

    Flow per iteration:
    1. Web search with current terms
    2. Relevance gate: classify each result as relevant / trail / drop
    3. If relevant hits found -> extract deeper topics from them
       If no relevant hits -> pivot to completely different search terms
    4. Repeat until enough relevant sources accumulated or max_iterations hit
    5. Synthesize using ALL sources (relevant + trail chain)
    """

    def __init__(
        self,
        valves: Valves,
        sub_agent: SubAgent,
        journal: ResearchJournal,
    ):
        self._valves = valves
        self._sub_agent = sub_agent
        self._journal = journal
        self._synthesizer = Synthesizer(valves, sub_agent, journal)

    async def run(
        self,
        query: str,
        user_id: str,
        request: Any,
        user: Dict,
        model_id: str,
        event_emitter: Optional[Callable] = None,
    ) -> str:
        slug = ResearchJournal.slugify(query)
        session_dir = self._journal.resolve_session_dir(
            user_id, slug, namespace="research"
        )
        session = ResearchSession(
            session_id=f"research-{slug}",
            query=query,
            session_dir=session_dir,
            phase=ResearchPhase.INITIALIZING,
            model_id=model_id,
        )
        self._journal.write_prompt(session, model_id)
        await self._emit_status(event_emitter, "\U0001f4cb Research session started")

        # Extract anchor once -- threads through every subsequent prompt
        session.anchor = await extract_anchor(
            self._sub_agent, query, request, user
        )
        self._journal.write_anchor(session)
        await self._emit_status(event_emitter, "\U0001f3af Research anchor extracted")

        session.phase = ResearchPhase.RESEARCHING
        relevant_sources: List[Dict] = []
        trail_sources: List[Dict] = []
        seen_urls: set = set()
        search_terms = [query]
        tried_terms: set = set()
        target = self._valves.min_relevant_sources
        consecutive_misses = 0

        for n in range(1, self._valves.max_iterations + 1):
            # --- Step 1: Web search ---
            new_terms = [t for t in search_terms if t not in tried_terms]
            if not new_terms and n > 1:
                await self._emit_status(event_emitter, "\u2705 No new terms to explore")
                break
            tried_terms.update(new_terms)

            combined = (
                " OR ".join(f'"{t}"' for t in new_terms)
                if len(new_terms) > 1
                else new_terms[0]
            )
            raw = await self._web_search(session, combined, request, user)
            raw = [r for r in raw if r.get("url", "") not in seen_urls]
            seen_urls.update(r.get("url", "") for r in raw)

            if not raw:
                consecutive_misses += 1
                it = IterationResult(n, new_terms, ["web_search"], 0, 0, "No results returned.", [])
                session.iterations.append(it)
                self._journal.write_iteration(session, it)
                await self._emit_status(
                    event_emitter, f"\U0001f504 Iter {n}: 0 results \u2014 pivoting"
                )
                search_terms = await self._pivot(session, tried_terms, request, user)
                continue

            # --- Step 2: Relevance gate ---
            rel, trail, dropped = await self._relevance_gate(
                session, raw, request, user
            )
            relevant_sources.extend(rel)
            trail_sources.extend(trail)
            all_kept = rel + trail
            await self._store_sources(session, all_kept, n)

            rel_count = len(relevant_sources)
            summary = ""

            # --- Step 3: Branch on relevance ---
            if rel:
                consecutive_misses = 0
                extraction = await self._extract_topics(
                    session, rel, trail, request, user
                )
                deeper = extraction.get("deeper_terms", [])
                adjacent = extraction.get("adjacent_leads", [])
                covered = extraction.get("covered_so_far", [])
                summary = (
                    f"Found {len(rel)} relevant, {len(trail)} trail, dropped {dropped}. "
                    f"Covered: {', '.join(covered[:3])}. Deeper: {', '.join(deeper[:3])}."
                )
                search_terms = deeper + adjacent
                await self._emit_status(
                    event_emitter,
                    f"\U0001f3af Iter {n}: +{len(rel)} relevant ({rel_count} total), "
                    f"+{len(trail)} trail \u2014 diving deeper",
                )
            else:
                consecutive_misses += 1
                summary = f"No relevant hits (kept {len(trail)} trail, dropped {dropped}). Pivoting."
                search_terms = await self._pivot(session, tried_terms, request, user)
                await self._emit_status(
                    event_emitter,
                    f"\U0001f504 Iter {n}: 0 relevant, {len(trail)} trail "
                    f"\u2014 pivoting ({consecutive_misses})",
                )

            it = IterationResult(n, new_terms, ["web_search"], len(raw), len(all_kept), summary, [])
            session.iterations.append(it)
            self._journal.write_iteration(session, it)

            # --- Step 4: Check goal ---
            if rel_count >= target:
                await self._emit_status(
                    event_emitter,
                    f"\u2705 Target reached: {rel_count}/{target} relevant sources",
                )
                break

            if consecutive_misses >= 3:
                await self._emit_status(
                    event_emitter,
                    f"\u26a0\ufe0f 3 consecutive misses \u2014 proceeding with {rel_count} relevant",
                )
                break

        # --- Final analysis ---
        analysis = await self._analyze_sources(session, request, user)
        if analysis.get("gaps"):
            await self._emit_status(
                event_emitter,
                f"\U0001f50d Remaining gaps: {', '.join(analysis['gaps'][:3])}",
            )

        # --- Synthesize ---
        session.phase = ResearchPhase.SYNTHESIZING
        await self._emit_status(
            event_emitter,
            f"\U0001f9e0 Synthesizing ({len(relevant_sources)} relevant "
            f"+ {len(trail_sources)} trail sources)...",
        )
        answer = await self._synthesizer.synthesize(session, request, user)
        session.phase = ResearchPhase.COMPLETE
        await self._emit_status(
            event_emitter, f"\U0001f4c1 Journal: research/{slug}/", done=True
        )

        if len(relevant_sources) < target:
            answer += (
                f"\n\n---\n\n\u26a0\ufe0f *Only {len(relevant_sources)}/{target} "
                f"relevant sources found. Consider `deep_research()` to crawl "
                f"authoritative domains.*"
            )
        return answer

    # --- Search helpers ---

    async def _web_search(
        self, session: ResearchSession, query: str, request: Any, user: Dict
    ) -> List[Dict]:
        system_prompt = _WEB_SEARCH_SYSTEM_PROMPT.format(
            max_results=self._valves.max_web_results,
        )
        try:
            return await self._sub_agent.run_json(
                system_prompt=system_prompt,
                user_prompt=f"{session.anchor}\n\nSearch for: {query}",
                request=request,
                user=user,
                enable_web_search=True,
            )
        except Exception as e:
            logger.error("Web search failed: %s", e)
            return []

    # --- Relevance gate ---

    async def _relevance_gate(
        self,
        session: ResearchSession,
        sources: List[Dict],
        request: Any,
        user: Dict,
    ) -> tuple:
        """Returns (relevant, trail, drop_count)."""
        if not sources:
            return [], [], 0
        summaries = "\n".join(
            f"{i}. [{s.get('domain','')}] {s.get('title','?')}: "
            f"{s.get('summary','')[:150]}"
            for i, s in enumerate(sources)
        )
        try:
            verdicts = await self._sub_agent.run_json(
                system_prompt=_RELEVANCE_GATE_PROMPT,
                user_prompt=f"{session.anchor}\n\nResults to judge:\n{summaries}",
                request=request,
                user=user,
            )
            if not isinstance(verdicts, list):
                return sources, [], 0
            relevant, trail = [], []
            for v in verdicts:
                if not isinstance(v, dict):
                    continue
                idx = v.get("index", -1)
                if 0 <= idx < len(sources):
                    verdict = v.get("verdict", "drop")
                    if verdict == "relevant":
                        relevant.append(sources[idx])
                    elif verdict == "trail":
                        trail.append(sources[idx])
            dropped = len(sources) - len(relevant) - len(trail)
            logger.info(
                "Relevance gate: %d relevant, %d trail, %d dropped",
                len(relevant), len(trail), dropped,
            )
            return relevant, trail, dropped
        except Exception:
            return sources, [], 0

    # --- Extract deeper topics ---

    async def _extract_topics(
        self,
        session: ResearchSession,
        relevant: List[Dict],
        trail: List[Dict],
        request: Any,
        user: Dict,
    ) -> Dict:
        rel_text = "\n\n".join(
            f"**[{s.get('domain','')}] {s.get('title','?')}**\n{s.get('summary','')}"
            for s in relevant[:10]
        )
        trail_text = "\n\n".join(
            f"**[{s.get('domain','')}] {s.get('title','?')}**\n{s.get('summary','')}"
            for s in trail[:5]
        )
        try:
            return await self._sub_agent.run_json(
                system_prompt=_EXTRACT_TOPICS_PROMPT,
                user_prompt=(
                    f"{session.anchor}\n\n"
                    f"## Relevant Sources\n{rel_text}\n\n"
                    f"## Trail Sources\n{trail_text}"
                ),
                request=request,
                user=user,
            )
        except Exception:
            return {"deeper_terms": [], "adjacent_leads": [], "covered_so_far": []}

    # --- Pivot ---

    async def _pivot(
        self,
        session: ResearchSession,
        tried_terms: set,
        request: Any,
        user: Dict,
    ) -> List[str]:
        tried_str = ", ".join(sorted(tried_terms)[:20])
        iters = "\n".join(
            f"- Iter {i.iteration_number}: {i.summary[:150]}"
            for i in session.iterations
        )
        try:
            r = await self._sub_agent.run_json(
                system_prompt=_PIVOT_PROMPT,
                user_prompt=(
                    f"{session.anchor}\n\n"
                    f"Already tried: {tried_str}\n"
                    f"Results so far:\n{iters}"
                ),
                request=request,
                user=user,
            )
            return r.get("terms", [])
        except Exception:
            return []

    # --- Storage ---

    async def _store_sources(
        self,
        session: ResearchSession,
        sources: List[Dict],
        iteration: int = 0,
    ) -> None:
        sources_dir = os.path.join(session.session_dir, "sources")
        os.makedirs(sources_dir, exist_ok=True)
        prefix = f"iter{iteration}-" if iteration else ""

        for i, source in enumerate(sources, 1):
            domain = source.get("domain", "unknown")
            filename = f"{prefix}{domain}-{i}.md"
            content = (
                f"# {source.get('title', domain)}\n\n"
                f"[Source URL: {source.get('url', '')}]\n"
                f"[Retrieved: {datetime.now().isoformat()}]\n"
                f"[Relevance: {source.get('relevance', 0.0)}]\n\n"
                f"## Content\n\n"
                f"{source.get('summary', 'No content available.')}\n"
            )
            path = os.path.join(sources_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        index_lines = ["# Sources\n"] + [
            f"{i}. **{s.get('title', '?')}** ({s.get('domain', '')}) "
            f"\u2014 {s.get('relevance', 0):.2f}\n"
            for i, s in enumerate(sources, 1)
        ]
        self._journal.write_entry(
            session.session_dir,
            f"sources-iter{iteration}.md",
            "\n".join(index_lines),
        )

    # --- Final analysis ---

    async def _analyze_sources(
        self,
        session: ResearchSession,
        request: Any,
        user: Dict,
    ) -> Dict:
        sources_dir = os.path.join(session.session_dir, "sources")
        texts = []
        if os.path.isdir(sources_dir):
            for fn in sorted(os.listdir(sources_dir)):
                fp = os.path.join(sources_dir, fn)
                if os.path.isfile(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        texts.append(f.read())
        if not texts:
            return {
                "summary": "No sources.",
                "gaps": ["entire query uncovered"],
                "new_terms": [],
                "covered_aspects": [],
            }
        try:
            return await self._sub_agent.run_json(
                system_prompt=_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=(
                    f"{session.anchor}\n\n"
                    f"Sources ({len(texts)}):\n\n"
                    + "\n\n---\n\n".join(texts[:15])
                ),
                request=request,
                user=user,
            )
        except Exception:
            return {
                "summary": f"Found {len(texts)} sources.",
                "gaps": [],
                "new_terms": [],
                "covered_aspects": [],
            }

    @staticmethod
    async def _emit_status(
        event_emitter: Optional[Callable],
        message: str,
        done: bool = False,
    ) -> None:
        if event_emitter:
            await event_emitter(
                {
                    "type": "status",
                    "data": {"description": message, "done": done},
                }
            )
