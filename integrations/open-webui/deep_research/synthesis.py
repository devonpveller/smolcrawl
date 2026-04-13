"""
Chain-of-thought synthesis from accumulated research evidence.

Single Responsibility: Only handles final synthesis from journal entries.
"""

import logging
from typing import Any, Dict, List

from .journal import ResearchJournal
from .models import ResearchSession, Valves
from .sub_agent import SubAgent

logger = logging.getLogger("deep_research.synthesis")

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a research synthesizer. Given a research query, iteration summaries, \
and the most relevant retrieved content, produce a comprehensive answer.

CRITICAL: Only cite URLs and sources that appear in the provided iteration data. \
NEVER invent, guess, or hallucinate URLs. If a claim lacks a source in the data, \
state it without a citation or note that the source was not found.

Your response must:
1. Reason step-by-step through the collected evidence (chain of thought).
2. Cite sources when making claims (use collection names and source files).
3. Identify any remaining gaps or uncertainties.
4. Conclude with a clear, well-structured answer to the original query.

Structure your response as:
## Reasoning
(step-by-step analysis of the evidence)

## Answer
(comprehensive answer to the query)

## Sources
(ONLY URLs from the provided data — never fabricated)

## Gaps
(any remaining unknowns or areas for further research)\
"""


class Synthesizer:
    """Produces a chain-of-thought synthesis from accumulated research.

    Reads back journal entries and top-scored chunks, then asks the LLM
    to reason through the evidence and compose a grounded answer.
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

    async def synthesize(
        self,
        session: ResearchSession,
        request: Any,
        user: Dict,
        relevant_sources: List[Dict] = None,
        trail_sources: List[Dict] = None,
    ) -> str:
        """Produce a final synthesis from all research iterations.

        Reads iteration summaries and constructs an LLM prompt that includes:
        - The original research query
        - Summaries from each iteration
        - The most relevant chunks (capped for context window)

        Args:
            session: The research session with completed iterations.
            request: OWUI __request__ object.
            user: OWUI __user__ dict.

        Returns:
            The synthesized answer as markdown text.
        """
        # Build context from journal entries
        prompt_content = self._journal.read_entry(
            session.session_dir, "00-prompt.md"
        )

        iteration_summaries = []
        for iteration in session.iterations:
            file_num = iteration.iteration_number + 2
            filename = f"{file_num:02d}-iteration-{iteration.iteration_number}.md"
            content = self._journal.read_entry(session.session_dir, filename)
            if content:
                iteration_summaries.append(content)

        # Compose the synthesis prompt
        user_prompt = self._build_synthesis_prompt(
            session=session,
            prompt_content=prompt_content,
            iteration_summaries=iteration_summaries,
            relevant_sources=relevant_sources or [],
            trail_sources=trail_sources or [],
        )

        try:
            answer = await self._sub_agent.run(
                system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                request=request,
                user=user,
            )

            # Write synthesis to journal
            self._journal.write_synthesis(session, answer)
            self._journal.write_manifest(session)

            return answer

        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            fallback = self._build_fallback_synthesis(session)
            self._journal.write_synthesis(session, fallback)
            self._journal.write_manifest(session)
            return fallback

    @staticmethod
    def _build_synthesis_prompt(
        session: 'ResearchSession',
        prompt_content: str,
        iteration_summaries: List[str],
        relevant_sources: List[Dict] = None,
        trail_sources: List[Dict] = None,
    ) -> str:
        """Construct the user prompt for synthesis.

        Args:
            session: The research session (for query and anchor).
            prompt_content: Content of 00-prompt.md.
            iteration_summaries: Content of each iteration file.
            relevant_sources: List of relevant source dicts with url/title/summary/domain.
            trail_sources: List of trail source dicts with url/title/summary/domain.

        Returns:
            Formatted prompt string.
        """
        parts = []
        if session.anchor:
            parts.append(f"# Research Anchor\n\n{session.anchor}\n")
        parts.append(f"# Original Research Query\n\n{session.query}\n")

        if prompt_content:
            parts.append(f"# Session Context\n\n{prompt_content}\n")

        for i, summary in enumerate(iteration_summaries, 1):
            parts.append(f"# Iteration {i} Findings\n\n{summary}\n")

        # Include the actual source data so the LLM can cite real URLs
        all_sources = (relevant_sources or []) + (trail_sources or [])
        if all_sources:
            parts.append("# Collected Sources\n")
            parts.append(
                "These are the actual web sources found during research. "
                "Use these URLs in your Sources section.\n"
            )
            for i, s in enumerate(all_sources, 1):
                parts.append(
                    f"{i}. **{s.get('title', 'Untitled')}**\n"
                    f"   - URL: {s.get('url', 'N/A')}\n"
                    f"   - Domain: {s.get('domain', '')}\n"
                    f"   - Summary: {s.get('summary', '')}\n"
                )

        parts.append(
            "\n---\n\n"
            "Produce a comprehensive synthesis that addresses EVERY item in the "
            "Research Anchor's 'must_cover' list.\n"
            "IMPORTANT: In the Sources section, list ONLY URLs from the "
            "'Collected Sources' section above. Do NOT fabricate or guess any URLs."
        )

        return "\n\n".join(parts)

    @staticmethod
    def _build_fallback_synthesis(session: ResearchSession) -> str:
        """Build a minimal synthesis when the LLM call fails."""
        lines = [
            f"# Research Summary (Fallback)\n",
            f"**Query:** {session.query}\n",
            f"**Iterations completed:** {len(session.iterations)}\n",
        ]

        for iteration in session.iterations:
            lines.append(
                f"\n## Iteration {iteration.iteration_number}\n"
                f"- Terms: {', '.join(iteration.search_terms)}\n"
                f"- Chunks found: {iteration.chunks_found} "
                f"(new: {iteration.new_chunks})\n"
            )
            if iteration.summary:
                lines.append(f"\n{iteration.summary}\n")

        lines.append(
            "\n*Note: Full LLM synthesis was unavailable. "
            "Above are the raw iteration summaries.*"
        )

        return "\n".join(lines)
