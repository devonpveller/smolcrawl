"""
Iterative RAG research with term expansion and deduplication.

Single Responsibility: Only handles querying knowledge collections and expanding terms.
Encapsulation: OWUI API details and chunk deduplication are internal.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .models import IterationResult, RetrievedChunk, ResearchSession, Valves
from .sub_agent import SubAgent

logger = logging.getLogger("deep_research.rag_research")

_EXPANSION_SYSTEM_PROMPT = """\
You are a research assistant analyzing RAG retrieval results. Given the \
original research query and a summary of findings so far, identify \
adjacent concepts, synonyms, and related terms that should be searched \
to find additional relevant information.

Return a JSON object with:
- "terms": array of 3-5 new search terms/phrases
- "concepts": array of new concepts discovered in the findings
- "summary": a 2-3 paragraph summary of what was found so far

Respond ONLY with valid JSON.\
"""

_CONTINUE_SYSTEM_PROMPT = """\
You are evaluating whether another research iteration would yield \
meaningfully new information. Given the original query and summaries \
from previous iterations, decide whether to continue.

Consider:
- Are there clear knowledge gaps remaining?
- Did the last iteration introduce genuinely new concepts?
- Would different search terms likely surface new content?

Respond with a JSON object:
{"continue": true/false, "rationale": "one sentence explanation"}\
"""


class RagResearcher:
    """Performs iterative RAG queries across OWUI knowledge collections.

    Queries multiple collections with expanding search terms, deduplicates
    chunks, and uses an LLM sub-agent for term expansion and continue
    decisions.
    """

    def __init__(self, valves: Valves, sub_agent: SubAgent):
        self._valves = valves
        self._sub_agent = sub_agent

    async def list_collections(self) -> List[Dict]:
        """List all knowledge collections from OWUI.

        Returns:
            List of collection dicts from the OWUI API.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._valves.owui_base_url}/api/v1/knowledge/",
                    headers={
                        "Authorization": f"Bearer {self._valves.owui_api_key}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Handle both list and paginated dict responses
                if isinstance(data, dict):
                    return data.get("items", [])
                return data

        except (httpx.HTTPError, Exception) as e:
            logger.error("Failed to list collections: %s", e)
            return []

    async def query_collection(
        self,
        collection_id: str,
        query: str,
        collection_name: str = "",
    ) -> List[RetrievedChunk]:
        """Query a single knowledge collection via OWUI's retrieval API.

        Args:
            collection_id: UUID of the collection to search.
            query: Natural language query string.
            collection_name: Human-readable name for logging.

        Returns:
            List of RetrievedChunk objects.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._valves.owui_base_url}/api/v1/retrieval/query",
                    headers={
                        "Authorization": f"Bearer {self._valves.owui_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "collection_name": collection_id,
                        "query": query,
                        "k": self._valves.top_k_per_collection,
                        "r": 0.0,
                    },
                )
                response.raise_for_status()
                data = response.json()

            return self._parse_retrieval_response(
                data, collection_id, collection_name
            )

        except (httpx.HTTPError, Exception) as e:
            logger.error(
                "Query failed for collection %s: %s", collection_id, e
            )
            return []

    async def run_iteration(
        self,
        session: ResearchSession,
        search_terms: List[str],
        collection_ids: List[str],
        collection_names: Dict[str, str],
        iteration_number: int,
        request: Any,
        user: Dict,
    ) -> IterationResult:
        """Execute a single research iteration: query + summarize.

        Args:
            session: The active research session (for deduplication state).
            search_terms: Terms to query across collections.
            collection_ids: UUIDs of collections to search.
            collection_names: Mapping of collection ID to human-readable name.
            iteration_number: Current iteration index (1-based).
            request: OWUI __request__ object.
            user: OWUI __user__ dict.

        Returns:
            IterationResult with findings and LLM summary.
        """
        all_chunks: List[RetrievedChunk] = []
        new_chunks: List[RetrievedChunk] = []

        # Query each collection with each term
        for term in search_terms:
            for col_id in collection_ids:
                chunks = await self.query_collection(
                    collection_id=col_id,
                    query=term,
                    collection_name=collection_names.get(col_id, col_id),
                )
                for chunk in chunks:
                    all_chunks.append(chunk)
                    is_new = session.add_seen_chunk(
                        col_id, chunk.chunk_hash
                    )
                    if is_new:
                        new_chunks.append(chunk)

        # Build context for LLM summarization
        chunk_text = "\n\n---\n\n".join(
            f"**[{c.collection_name}]** ({c.source})\n{c.content}"
            for c in new_chunks[:20]  # Cap to avoid context overflow
        )

        # Get LLM summary + new concepts
        summary = ""
        new_concepts: List[str] = []

        if new_chunks:
            try:
                result = await self._sub_agent.run_json(
                    system_prompt=_EXPANSION_SYSTEM_PROMPT,
                    user_prompt=(
                        f"Original query: {session.query}\n\n"
                        f"Search terms used: {', '.join(search_terms)}\n\n"
                        f"Retrieved content ({len(new_chunks)} new chunks):\n\n"
                        f"{chunk_text}"
                    ),
                    request=request,
                    user=user,
                )
                summary = result.get("summary", "")
                new_concepts = result.get("concepts", [])
            except (ValueError, Exception) as e:
                logger.warning("Expansion analysis failed: %s", e)
                summary = f"Found {len(new_chunks)} new chunks across {len(collection_ids)} collections."

        iteration = IterationResult(
            iteration_number=iteration_number,
            search_terms=search_terms,
            collections_queried=[
                collection_names.get(c, c) for c in collection_ids
            ],
            chunks_found=len(all_chunks),
            new_chunks=len(new_chunks),
            summary=summary,
            new_concepts=new_concepts,
        )

        session.iterations.append(iteration)
        return iteration

    async def expand_terms(
        self,
        session: ResearchSession,
        current_terms: List[str],
        request: Any,
        user: Dict,
    ) -> List[str]:
        """Use LLM to generate expanded search terms from accumulated findings.

        Args:
            session: The research session with iteration history.
            current_terms: Current search terms to extend.
            request: OWUI __request__ object.
            user: OWUI __user__ dict.

        Returns:
            List of new search terms for the next iteration.
        """
        iteration_summaries = "\n\n".join(
            f"**Iteration {it.iteration_number}:** {it.summary}"
            for it in session.iterations
        )

        try:
            result = await self._sub_agent.run_json(
                system_prompt=_EXPANSION_SYSTEM_PROMPT,
                user_prompt=(
                    f"Original query: {session.query}\n\n"
                    f"Previous search terms: {', '.join(current_terms)}\n\n"
                    f"Findings so far:\n{iteration_summaries}\n\n"
                    f"Suggest new search terms that would find different, "
                    f"relevant information."
                ),
                request=request,
                user=user,
            )
            return result.get("terms", current_terms)
        except (ValueError, Exception) as e:
            logger.warning("Term expansion failed: %s", e)
            return current_terms

    async def should_continue(
        self,
        session: ResearchSession,
        request: Any,
        user: Dict,
    ) -> bool:
        """Ask LLM whether another iteration would yield meaningful results.

        Args:
            session: The research session with iteration history.
            request: OWUI __request__ object.
            user: OWUI __user__ dict.

        Returns:
            True if the LLM recommends continuing.
        """
        iteration_summaries = "\n\n".join(
            f"**Iteration {it.iteration_number}** "
            f"(terms: {', '.join(it.search_terms)}): {it.summary}\n"
            f"New chunks: {it.new_chunks}, New concepts: {', '.join(it.new_concepts)}"
            for it in session.iterations
        )

        try:
            result = await self._sub_agent.run_json(
                system_prompt=_CONTINUE_SYSTEM_PROMPT,
                user_prompt=(
                    f"Original query: {session.query}\n\n"
                    f"Iteration results:\n{iteration_summaries}"
                ),
                request=request,
                user=user,
            )
            should = result.get("continue", False)
            rationale = result.get("rationale", "")
            logger.info(
                "Continue decision: %s — %s", should, rationale
            )
            return bool(should)
        except (ValueError, Exception) as e:
            logger.warning("Continue decision failed: %s", e)
            return False

    @staticmethod
    def _parse_retrieval_response(
        data: Dict,
        collection_id: str,
        collection_name: str,
    ) -> List[RetrievedChunk]:
        """Parse OWUI retrieval API response into RetrievedChunk objects."""
        chunks = []
        documents = data.get("documents", [[]])
        metadatas = data.get("metadatas", [[]])
        distances = data.get("distances", [[]])

        if not documents or not documents[0]:
            return chunks

        for i, doc_text in enumerate(documents[0]):
            metadata = metadatas[0][i] if i < len(metadatas[0]) else {}
            distance = distances[0][i] if i < len(distances[0]) else 0.0

            chunks.append(
                RetrievedChunk(
                    content=doc_text,
                    collection_id=collection_id,
                    collection_name=collection_name,
                    source=metadata.get("source", ""),
                    distance=distance,
                )
            )

        return chunks
