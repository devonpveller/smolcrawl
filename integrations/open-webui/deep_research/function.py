"""
title: Deep Research
author: smolcrawl
date: 2026-04-12
version: 1.0
license: MIT
description: Iterative RAG research with LLM-guided domain discovery, web search exploration, and chain-of-thought synthesis. Provides research() for quick exploration and deep_research() for full knowledge building.
requirements: httpx, pydantic
"""

import logging
import uuid
from typing import Any, Callable, Dict, Optional

from .crawl_integration import CrawlClient
from .domain_discovery import DomainDiscovery
from .journal import ResearchJournal
from .models import (
    DiscoveredDomain,
    ResearchPhase,
    ResearchSession,
    Valves,
)
from .rag_research import RagResearcher
from .research import QuickResearcher
from .sub_agent import SubAgent, extract_anchor
from .synthesis import Synthesizer

logger = logging.getLogger("deep_research")


class Tools:
    """Deep Research Tools for Open WebUI.

    Two tool methods:
    - research(query): Quick web-search-based exploration
    - deep_research(query): Full pipeline — discover, crawl, RAG, synthesize

    Designed as an OWUI Tool (class Tools) that runs inside the user's
    selected LLM context with native function calling.
    """

    class Valves(Valves):
        """Re-export Valves at the class level for OWUI discovery."""
        pass

    def __init__(self):
        self.valves = self.Valves()

    # --- Public Tool Methods ---

    async def research(
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
        """Quick research on a topic using web search.

        Stores findings to Fileshed and iteratively expands search terms
        to find context you might not know to search for. Faster than
        deep_research — use this to scope a topic before committing to
        a full crawl.

        Args:
            query: The research question or topic to explore.
        """
        model_id = SubAgent.resolve_model_id(__metadata__, __model__)
        user_id = (__user__ or {}).get("id", "")

        sub_agent = SubAgent(model_id)
        journal = ResearchJournal(self.valves)
        researcher = QuickResearcher(self.valves, sub_agent, journal)

        return await researcher.run(
            query=query,
            user_id=user_id,
            request=__request__,
            user=__user__ or {},
            model_id=model_id,
            event_emitter=__event_emitter__,
        )

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
        """Deep research on a topic.

        Discovers relevant domains via web search, crawls them into
        knowledge collections, runs iterative RAG retrieval, and
        synthesizes a comprehensive answer.

        The full pipeline runs automatically: discover → crawl → research → synthesize.

        Args:
            query: The research question or topic to investigate.
        """
        model_id = SubAgent.resolve_model_id(__metadata__, __model__)
        user_id = (__user__ or {}).get("id", "")

        sub_agent = SubAgent(model_id)
        journal = ResearchJournal(self.valves)
        discovery = DomainDiscovery(self.valves, sub_agent)
        rag = RagResearcher(self.valves, sub_agent)
        crawl_client = CrawlClient(self.valves)
        synthesizer = Synthesizer(self.valves, sub_agent, journal)

        # Initialize session
        slug = ResearchJournal.slugify(query)
        session_dir = journal.resolve_session_dir(user_id, slug)
        session = ResearchSession(
            session_id=str(uuid.uuid4()),
            query=query,
            session_dir=session_dir,
            model_id=model_id,
        )
        journal.write_prompt(session, model_id)

        await self._emit_status(
            __event_emitter__, "📋 Deep research started"
        )

        # Extract anchor once — threads through all subsequent prompts
        anchor_result = await extract_anchor(
            sub_agent, query, __request__, __user__ or {}
        )
        session.anchor = anchor_result[0]  # (anchor_string, initial_search_terms)
        journal.write_anchor(session)
        await self._emit_status(
            __event_emitter__, "🎯 Research anchor extracted"
        )

        # --- Phase 1: Discover domains and check existing collections ---
        session.phase = ResearchPhase.DISCOVERING
        all_collections = await rag.list_collections()
        relevant_ids = await discovery.rank_existing_collections(
            query, all_collections, __request__, __user__ or {}
        )
        session.relevant_collection_ids = relevant_ids
        relevant_collections = [
            c for c in all_collections if c["id"] in relevant_ids
        ]

        await self._emit_status(
            __event_emitter__,
            f"📚 {len(all_collections)} collection(s), "
            f"{len(relevant_ids)} relevant",
        )

        domains = await discovery.discover_domains(
            query, __request__, __user__ or {}
        )
        domains = discovery.check_domain_coverage(domains, all_collections)
        session.discovered_domains = domains
        journal.write_domains(session, relevant_collections)

        # --- Phase 2: Auto-approve and crawl new domains ---
        approved_domains = [d for d in domains if not d.already_covered]

        if approved_domains:
            session.phase = ResearchPhase.CRAWLING
            names = ", ".join(d.domain for d in approved_domains[:5])
            await self._emit_status(
                __event_emitter__,
                f"🕷️ Crawling {len(approved_domains)} domain(s): {names}",
            )

            for domain in approved_domains:
                kb_name = f"SmolCrawl - {domain.domain}"
                result = await crawl_client.trigger_crawl_streaming(
                    domain=domain.domain,
                    kb_name=kb_name,
                    event_emitter=__event_emitter__,
                )
                session.crawl_results.append(result)

                if result.success and result.kb_id:
                    session.relevant_collection_ids.append(result.kb_id)

            journal.write_crawl_status(session)

            successful = sum(1 for r in session.crawl_results if r.success)
            await self._emit_status(
                __event_emitter__,
                f"✅ Crawled {successful}/{len(approved_domains)} domain(s)",
            )
        else:
            await self._emit_status(
                __event_emitter__,
                "📚 All domains already in knowledge base",
            )

        # Refresh collection list to pick up newly created KBs
        all_collections = await rag.list_collections()
        collection_map = {c["id"]: c["name"] for c in all_collections}

        for result in session.crawl_results:
            if result.success:
                for col in all_collections:
                    if col["name"] == result.kb_name:
                        if col["id"] not in session.relevant_collection_ids:
                            session.relevant_collection_ids.append(col["id"])
                        result.kb_id = col["id"]
                        break

        # --- Phase 3: Iterative RAG research ---
        session.phase = ResearchPhase.RESEARCHING
        search_terms = [session.query]

        for iter_num in range(1, self.valves.max_iterations + 1):
            await self._emit_status(
                __event_emitter__,
                f"🔍 Research iteration {iter_num}...",
            )

            iteration = await rag.run_iteration(
                session=session,
                search_terms=search_terms,
                collection_ids=session.relevant_collection_ids,
                collection_names=collection_map,
                iteration_number=iter_num,
                request=__request__,
                user=__user__ or {},
            )

            journal.write_iteration(session, iteration)

            await self._emit_status(
                __event_emitter__,
                f"📚 Iter {iter_num}: {iteration.new_chunks} new chunk(s)",
            )

            search_terms = await rag.expand_terms(
                session, search_terms, __request__, __user__ or {}
            )

            if iter_num >= self.valves.fixed_iterations:
                if iter_num >= self.valves.max_iterations:
                    break
                should_continue = await rag.should_continue(
                    session, __request__, __user__ or {}
                )
                if not should_continue:
                    await self._emit_status(
                        __event_emitter__, "✅ Research complete"
                    )
                    break

        # --- Phase 4: Synthesize ---
        session.phase = ResearchPhase.SYNTHESIZING
        await self._emit_status(
            __event_emitter__, "🧠 Synthesizing findings..."
        )

        answer = await synthesizer.synthesize(
            session, __request__, __user__ or {},
            event_emitter=__event_emitter__,
        )

        session.phase = ResearchPhase.COMPLETE
        await self._emit_status(
            __event_emitter__,
            f"📁 Journal: deep-research/{slug}/",
            done=True,
        )

        return answer

    # --- Private Helpers ---

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
