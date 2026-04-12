"""
Quick web-search-based research (research() method logic).

Single Responsibility: Handles the lightweight research flow that uses
web search + Fileshed instead of crawling + knowledge collections.
"""

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .journal import ResearchJournal
from .models import ResearchPhase, ResearchSession, Valves
from .sub_agent import SubAgent
from .synthesis import Synthesizer

logger = logging.getLogger("deep_research.research")

_WEB_SEARCH_SYSTEM_PROMPT = """\
You are a research assistant. Search the web for authoritative information \
about the given topic. For each relevant result, provide:

Return a JSON array of objects:
[
  {
    "url": "https://...",
    "domain": "docs.example.com",
    "title": "Page Title",
    "summary": "2-3 sentence summary of the key content",
    "relevance": 0.0-1.0
  }
]

Focus on official documentation, technical references, and authoritative \
sources. Return at most {max_results} results.
Respond ONLY with valid JSON.\
"""

_ANALYSIS_SYSTEM_PROMPT = """\
You are a research analyst. Given a collection of web search findings, \
produce a structured analysis including:

1. A 2-3 paragraph summary of key findings
2. Knowledge gaps that remain
3. New concepts or terms discovered

Return a JSON object:
{
  "summary": "overall summary text",
  "gaps": ["gap1", "gap2"],
  "new_terms": ["term1", "term2"],
  "new_concepts": ["concept1", "concept2"]
}\
"""

_FILESHED_EXPANSION_SYSTEM_PROMPT = """\
You are a research assistant reviewing stored findings. Given the original \
query and accumulated sources, suggest new search terms that would surface \
different, relevant information.

Return a JSON object:
{
  "terms": ["term1", "term2", "term3"],
  "rationale": "brief explanation of why these terms would help"
}\
"""


class QuickResearcher:
    """Performs lightweight research using web search and Fileshed storage.

    No crawling, no knowledge collections. Stores web search results
    directly to Fileshed and iterates over the stored content for
    term expansion and synthesis.
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
        """Execute the full quick research pipeline.

        Args:
            query: The research question or topic.
            user_id: OWUI user ID for Fileshed path scoping.
            request: OWUI __request__ object.
            user: OWUI __user__ dict.
            model_id: Active model ID for sub-agent calls.
            event_emitter: Optional OWUI event emitter for status updates.

        Returns:
            Synthesized research answer as markdown.
        """
        # Step 0: Initialize session
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
        await self._emit_status(
            event_emitter, "📋 Research session started"
        )

        # Step 1: Web search + store sources
        session.phase = ResearchPhase.RESEARCHING
        sources = await self._web_search(query, request, user)
        await self._store_sources(session, sources)
        await self._emit_status(
            event_emitter,
            f"🌐 Found {len(sources)} relevant source(s), stored to journal",
        )

        # Step 2: Initial analysis
        analysis = await self._analyze_sources(session, request, user)
        current_terms = [query] + analysis.get("new_terms", [])

        from .models import IterationResult

        iteration = IterationResult(
            iteration_number=1,
            search_terms=[query],
            collections_queried=["web_search"],
            chunks_found=len(sources),
            new_chunks=len(sources),
            summary=analysis.get("summary", ""),
            new_concepts=analysis.get("new_concepts", []),
        )
        session.iterations.append(iteration)
        self._journal.write_iteration(session, iteration)
        await self._emit_status(
            event_emitter,
            f"📚 Initial analysis complete — "
            f"{len(analysis.get('new_concepts', []))} concept(s) identified",
        )

        # Step 3: Term expansion + re-search iterations
        seen_urls = {s.get("url", "") for s in sources}
        for iter_num in range(2, self._valves.max_iterations + 1):
            expanded = await self._expand_search_terms(
                session, current_terms, request, user
            )
            new_terms = [t for t in expanded if t not in current_terms]
            if not new_terms:
                break

            new_sources = await self._web_search_terms(
                new_terms, seen_urls, request, user
            )
            if new_sources:
                await self._store_sources(session, new_sources)
                seen_urls.update(s.get("url", "") for s in new_sources)

            iter_analysis = await self._analyze_sources(
                session, request, user
            )

            iteration = IterationResult(
                iteration_number=iter_num,
                search_terms=new_terms,
                collections_queried=["web_search"],
                chunks_found=len(new_sources),
                new_chunks=len(new_sources),
                summary=iter_analysis.get("summary", ""),
                new_concepts=iter_analysis.get("new_concepts", []),
            )
            session.iterations.append(iteration)
            self._journal.write_iteration(session, iteration)

            current_terms = current_terms + new_terms
            await self._emit_status(
                event_emitter,
                f"🔄 Expanding: {', '.join(new_terms[:3])} — "
                f"{len(new_sources)} new source(s)",
            )

            # Continue decision after fixed iterations
            if iter_num >= self._valves.fixed_iterations:
                should_continue = await self._should_continue(
                    session, request, user
                )
                if not should_continue:
                    break

        # Step 4: Synthesis
        session.phase = ResearchPhase.SYNTHESIZING
        await self._emit_status(event_emitter, "🧠 Synthesizing findings...")

        answer = await self._synthesizer.synthesize(session, request, user)

        session.phase = ResearchPhase.COMPLETE
        await self._emit_status(
            event_emitter,
            f"📁 Full journal: research/{slug}/",
            done=True,
        )

        # Add escalation suggestion if warranted
        if self._should_suggest_escalation(session):
            answer += (
                "\n\n---\n\n"
                "💡 *For a deeper analysis, consider running `deep_research()` "
                "to crawl the most authoritative sources into permanent "
                "knowledge collections.*"
            )

        return answer

    async def _web_search(
        self, query: str, request: Any, user: Dict
    ) -> List[Dict]:
        """Execute web search via sub-agent."""
        system_prompt = _WEB_SEARCH_SYSTEM_PROMPT.format(
            max_results=self._valves.max_web_results,
        )
        try:
            return await self._sub_agent.run_json(
                system_prompt=system_prompt,
                user_prompt=f"Search for: {query}",
                request=request,
                user=user,
                enable_web_search=True,
            )
        except (ValueError, Exception) as e:
            logger.error("Web search failed: %s", e)
            return []

    async def _web_search_terms(
        self,
        terms: List[str],
        seen_urls: set,
        request: Any,
        user: Dict,
    ) -> List[Dict]:
        """Search for multiple terms, deduplicating against seen URLs."""
        combined_query = " OR ".join(f'"{t}"' for t in terms)
        results = await self._web_search(combined_query, request, user)
        return [r for r in results if r.get("url", "") not in seen_urls]

    async def _store_sources(
        self,
        session: ResearchSession,
        sources: List[Dict],
    ) -> None:
        """Write web search results as individual source files."""
        sources_dir = os.path.join(session.session_dir, "sources")

        for i, source in enumerate(sources, 1):
            domain = source.get("domain", "unknown")
            filename = f"{domain}-{i}.md"

            content = (
                f"# {source.get('title', domain)}\n\n"
                f"[Source URL: {source.get('url', '')}]\n"
                f"[Retrieved: {datetime.now().isoformat()}]\n"
                f"[Relevance: {source.get('relevance', 0.0)}]\n\n"
                f"## Content\n\n"
                f"{source.get('summary', 'No content available.')}\n"
            )

            path = os.path.join(sources_dir, filename)
            os.makedirs(sources_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        # Write sources index
        index_lines = ["# Sources Index\n"]
        for i, source in enumerate(sources, 1):
            index_lines.append(
                f"{i}. **{source.get('title', 'Unknown')}** "
                f"({source.get('domain', '')}) — "
                f"relevance: {source.get('relevance', 0.0):.2f}\n"
                f"   {source.get('summary', '')[:100]}...\n"
            )
        self._journal.write_entry(
            session.session_dir, "01-sources.md", "\n".join(index_lines)
        )

    async def _analyze_sources(
        self,
        session: ResearchSession,
        request: Any,
        user: Dict,
    ) -> Dict:
        """Read stored sources and produce an analysis."""
        sources_dir = os.path.join(session.session_dir, "sources")
        source_content = []

        if os.path.isdir(sources_dir):
            for filename in sorted(os.listdir(sources_dir)):
                filepath = os.path.join(sources_dir, filename)
                if os.path.isfile(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        source_content.append(f.read())

        if not source_content:
            return {"summary": "No sources found.", "gaps": [], "new_terms": []}

        try:
            return await self._sub_agent.run_json(
                system_prompt=_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=(
                    f"Original query: {session.query}\n\n"
                    f"Collected sources:\n\n"
                    + "\n\n---\n\n".join(source_content[:15])
                ),
                request=request,
                user=user,
            )
        except (ValueError, Exception) as e:
            logger.warning("Source analysis failed: %s", e)
            return {"summary": f"Found {len(source_content)} sources.", "gaps": [], "new_terms": []}

    async def _expand_search_terms(
        self,
        session: ResearchSession,
        current_terms: List[str],
        request: Any,
        user: Dict,
    ) -> List[str]:
        """Get expanded search terms from LLM."""
        iteration_summaries = "\n".join(
            f"- Iteration {it.iteration_number}: {it.summary[:200]}"
            for it in session.iterations
        )

        try:
            result = await self._sub_agent.run_json(
                system_prompt=_FILESHED_EXPANSION_SYSTEM_PROMPT,
                user_prompt=(
                    f"Query: {session.query}\n"
                    f"Current terms: {', '.join(current_terms)}\n"
                    f"Progress:\n{iteration_summaries}"
                ),
                request=request,
                user=user,
            )
            return result.get("terms", [])
        except (ValueError, Exception) as e:
            logger.warning("Term expansion failed: %s", e)
            return []

    async def _should_continue(
        self,
        session: ResearchSession,
        request: Any,
        user: Dict,
    ) -> bool:
        """Ask LLM whether to continue iterating."""
        from .rag_research import _CONTINUE_SYSTEM_PROMPT

        iteration_text = "\n".join(
            f"Iteration {it.iteration_number}: "
            f"{it.new_chunks} new sources, "
            f"concepts: {', '.join(it.new_concepts[:5])}"
            for it in session.iterations
        )

        try:
            result = await self._sub_agent.run_json(
                system_prompt=_CONTINUE_SYSTEM_PROMPT,
                user_prompt=(
                    f"Query: {session.query}\n\n"
                    f"Iterations:\n{iteration_text}"
                ),
                request=request,
                user=user,
            )
            return result.get("continue", False)
        except (ValueError, Exception) as e:
            logger.warning("Continue decision failed: %s", e)
            return False

    @staticmethod
    def _should_suggest_escalation(session: ResearchSession) -> bool:
        """Determine if the user should be prompted to escalate to deep_research."""
        if len(session.iterations) >= 2:
            total_sources = sum(it.chunks_found for it in session.iterations)
            if total_sources >= 5:
                return True
        return False

    @staticmethod
    async def _emit_status(
        event_emitter: Optional[Callable],
        message: str,
        done: bool = False,
    ) -> None:
        """Emit a status update through OWUI's event emitter."""
        if event_emitter:
            await event_emitter(
                {
                    "type": "status",
                    "data": {"description": message, "done": done},
                }
            )
