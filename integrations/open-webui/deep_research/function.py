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
from .sub_agent import SubAgent
from .synthesis import Synthesizer

logger = logging.getLogger("deep_research")


class Tools:
    """Deep Research Function for Open WebUI.

    Provides three tool methods:
    - research(query): Quick web-search-based exploration
    - deep_research(query): Full knowledge building with domain discovery
    - deep_research_approve(selection): Approve domains and trigger crawl

    Designed as an OWUI Function (class Tools) that runs inside the user's
    selected LLM context with native function calling.
    """

    class Valves(Valves):
        """Re-export Valves at the class level for OWUI discovery."""
        pass

    def __init__(self):
        self.valves = self.Valves()
        self._pending_sessions: Dict[str, ResearchSession] = {}

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
        """Start deep research on a topic.

        Discovers relevant web domains using web search, checks existing
        knowledge collections, then presents domains for approval before
        crawling.

        Args:
            query: The research question or topic to investigate.
        """
        model_id = SubAgent.resolve_model_id(__metadata__, __model__)
        user_id = (__user__ or {}).get("id", "")

        sub_agent = SubAgent(model_id)
        journal = ResearchJournal(self.valves)
        discovery = DomainDiscovery(self.valves, sub_agent)
        rag = RagResearcher(self.valves, sub_agent)

        # Step 0: Initialize session
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
            __event_emitter__,
            "📋 Research session started",
        )

        # Step 1: Check existing knowledge collections
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
            f"📚 Found {len(all_collections)} collection(s), "
            f"{len(relevant_ids)} potentially relevant",
        )

        # Step 2: Discover domains via web search
        domains = await discovery.discover_domains(
            query, __request__, __user__ or {}
        )
        domains = discovery.check_domain_coverage(domains, all_collections)
        session.discovered_domains = domains

        # Write journal entry
        journal.write_domains(session, relevant_collections)

        session.phase = ResearchPhase.AWAITING_APPROVAL

        # Store session for the approval step
        self._pending_sessions[__chat_id__] = session

        # Return the approval prompt for the LLM to present
        approval_message = DomainDiscovery.format_approval_message(
            domains, relevant_collections
        )

        await self._emit_status(
            __event_emitter__,
            "🌐 Domains discovered — awaiting approval",
        )

        return approval_message

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
        """Approve discovered domains and begin deep research.

        Call this after deep_research() presents domain options.

        Args:
            selection: Which domains to crawl — numbers like "1,2,3",
                       "all", or "skip" (research existing collections only).
            additional_domains: Optional extra domains to crawl, space-separated.
        """
        # Retrieve pending session
        session = self._pending_sessions.pop(__chat_id__, None)
        if not session:
            return (
                "No pending research session found for this chat. "
                "Please start with `deep_research()` first."
            )

        model_id = SubAgent.resolve_model_id(__metadata__, __model__)
        sub_agent = SubAgent(model_id)
        journal = ResearchJournal(self.valves)
        crawl_client = CrawlClient(self.valves)
        rag = RagResearcher(self.valves, sub_agent)
        synthesizer = Synthesizer(self.valves, sub_agent, journal)

        # Parse user selection
        approved_domains = DomainDiscovery.parse_approval(
            selection, session.discovered_domains, additional_domains
        )

        # Phase B: Crawl approved domains
        if approved_domains:
            session.phase = ResearchPhase.CRAWLING
            await self._emit_status(
                __event_emitter__,
                f"🕷️ Crawling {len(approved_domains)} domain(s)...",
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
                f"✅ Built {successful} knowledge collection(s) from "
                f"{len(approved_domains)} domain(s)",
            )

        # Refresh collection list to pick up newly created KBs
        all_collections = await rag.list_collections()
        collection_map = {c["id"]: c["name"] for c in all_collections}

        # Include collections from successful crawls that weren't already tracked
        for result in session.crawl_results:
            if result.success:
                for col in all_collections:
                    if col["name"] == result.kb_name:
                        if col["id"] not in session.relevant_collection_ids:
                            session.relevant_collection_ids.append(col["id"])
                        result.kb_id = col["id"]
                        break

        # Phase C: Iterative RAG research
        session.phase = ResearchPhase.RESEARCHING
        search_terms = [session.query]

        for iter_num in range(1, self.valves.max_iterations + 1):
            await self._emit_status(
                __event_emitter__,
                f"📚 Research iteration {iter_num}...",
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
                f"📚 Iteration {iter_num}: {iteration.new_chunks} new "
                f"chunk(s) across "
                f"{len(session.relevant_collection_ids)} collection(s)",
            )

            # Expand terms for next iteration
            search_terms = await rag.expand_terms(
                session, search_terms, __request__, __user__ or {}
            )

            # Continue decision after fixed iterations
            if iter_num >= self.valves.fixed_iterations:
                if iter_num >= self.valves.max_iterations:
                    break
                should_continue = await rag.should_continue(
                    session, __request__, __user__ or {}
                )
                if not should_continue:
                    await self._emit_status(
                        __event_emitter__, "✅ Search complete"
                    )
                    break
                await self._emit_status(
                    __event_emitter__, "🔄 Continuing research..."
                )

        # Phase D: Synthesis
        session.phase = ResearchPhase.SYNTHESIZING
        await self._emit_status(
            __event_emitter__, "🧠 Synthesizing findings..."
        )

        answer = await synthesizer.synthesize(
            session, __request__, __user__ or {}
        )

        session.phase = ResearchPhase.COMPLETE
        slug = ResearchJournal.slugify(session.query)
        await self._emit_status(
            __event_emitter__,
            f"📁 Full research journal: deep-research/{slug}/",
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
