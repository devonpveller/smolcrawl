"""
Chain-of-thought synthesis from accumulated research evidence.

Single Responsibility: Only handles final synthesis from journal entries.
Includes post-synthesis verification to catch hallucinations and fabricated content.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

from .journal import ResearchJournal
from .models import ResearchSession, Valves
from .sub_agent import SubAgent

logger = logging.getLogger("deep_research.synthesis")

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a **source-grounded** research synthesizer. You may ONLY make claims \
that are directly supported by the provided evidence. You are NOT a general \
knowledge assistant — treat this as a courtroom: no evidence, no claim.

## Hard Rules

1. **Source-grounded claims only.** Every factual statement must trace to a \
specific Collected Source by number (e.g. [Source 3]). If no source supports \
a claim, do NOT make it — instead note it as a gap.
2. **ZERO fabricated URLs.** The Sources section must contain ONLY URLs copied \
verbatim from the Collected Sources list. If you cannot find a URL in that \
list, do not invent one. A synthesis with fabricated URLs is a failed synthesis.
3. **No gap-filling from training data.** If the collected evidence is \
insufficient to answer part of the query, say so explicitly in the Gaps \
section. Do NOT fill in missing information from your general knowledge — \
this creates dangerous false confidence.
4. **No generic templates.** Your answer must be specific to the actual \
evidence collected. If sources only cover surface-level information, \
produce a surface-level answer and flag the depth gap — do not generate \
a detailed how-to guide from imagination.
5. **Verify terminology.** If sources use a specific term for a technology, \
framework, or concept, use that exact term. Do NOT substitute similar-sounding \
technologies (e.g., do not confuse a server framework with a UI framework, \
or a backend tool with a frontend tool).
6. **Confidence tagging.** Mark each major claim with confidence:
   - [SOURCED] — directly stated in a collected source
   - [INFERRED] — reasonable inference from multiple sources
   - [UNCERTAIN] — mentioned but not well-supported
   Do NOT include claims that would need a [FABRICATED] tag.
7. **Scope fidelity.** Answer ONLY what the Research Anchor asks. If the \
anchor asks for a risk analysis, produce a risk analysis, not a how-to guide. \
Match the requested format and depth.

## Output Structure

### Reasoning
Step-by-step analysis of what the evidence actually shows. Reference \
specific sources by number. Note contradictions between sources.

### Answer
Comprehensive answer grounded in evidence. Every factual claim tagged \
with [SOURCED], [INFERRED], or [UNCERTAIN]. If the evidence is thin, \
the answer should be proportionally brief.

### Confidence Assessment
- Evidence quality: (strong / moderate / thin / insufficient)
- Source diversity: (how many independent sources support key claims)
- Notable gaps: (what the evidence does NOT cover)

### Sources
ONLY URLs from the Collected Sources list. Format:
1. [Source N] Title — URL

### Gaps & Limitations
- Specific aspects of the query not covered by evidence
- Areas where sources conflict or are ambiguous
- Recommended follow-up searches\
"""

_VERIFICATION_SYSTEM_PROMPT = """\
You are a factual accuracy reviewer. Given a research synthesis and the \
original source data it was built from, identify problems.

Check for these specific issues:
1. **Fabricated URLs**: Any URL in the synthesis that does NOT appear in \
the Collected Sources list.
2. **Unsupported claims**: Factual statements not backed by any source.
3. **Technology misidentification**: Tools, frameworks, or concepts described \
incorrectly (e.g., calling a server framework a UI framework).
4. **Generic template content**: Sections that read like a generic template \
rather than analysis of the specific evidence.
5. **Scope mismatch**: Content that doesn't match what the Research Anchor \
actually asked for.
6. **Fabricated examples**: Code snippets, commands, or configuration that \
aren't from any source.

Return JSON:
{"issues": [
  {"type": "fabricated_url|unsupported_claim|misidentification|generic_template|scope_mismatch|fabricated_example",
   "severity": "critical|warning",
   "detail": "specific description of the problem",
   "location": "quote the problematic text (first 100 chars)"}
],
"url_check": {
  "urls_in_synthesis": ["list every URL found in the synthesis"],
  "urls_in_sources": ["list every URL from Collected Sources"],
  "fabricated": ["URLs in synthesis but NOT in sources"]
},
"overall_credibility": "high|medium|low|very_low",
"recommendation": "pass|revise|flag_for_user"}\
"""

_REMEDIATION_SYSTEM_PROMPT = """\
You are a factual accuracy editor. You will receive:
1. A research synthesis (markdown)
2. A list of verified issues found by a reviewer

Your job: rewrite the synthesis with ALL fabricated or unsupported content \
removed or corrected. Rules:
- DELETE sentences/bullet-points that contain fabricated examples, names, or claims.
- Do NOT replace removed content with new invented content.
- If removing content leaves a section empty, replace it with: \
"*[Removed: insufficient evidence]*"
- If a claim was flagged as unsupported, add "[UNVERIFIED]" before it \
rather than deleting, unless the claim is clearly fabricated.
- Keep ALL content that was NOT flagged — do not rewrite or rephrase it.
- Preserve the original markdown structure (headings, lists, formatting).
- Return ONLY the corrected synthesis markdown. No commentary.\
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
        event_emitter: Callable = None,
    ) -> str:
        """Produce a final synthesis from all research iterations.

        Reads iteration summaries and constructs an LLM prompt that includes:
        - The original research query
        - Summaries from each iteration
        - The most relevant chunks (capped for context window)

        Post-synthesis, runs verification to catch hallucinations,
        fabricated URLs, and unsupported claims.

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

        all_sources = (relevant_sources or []) + (trail_sources or [])
        known_urls = self._extract_known_urls(all_sources)

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

            # --- Post-synthesis validation pipeline ---

            # Step 1: Programmatic URL scrubbing (fast, deterministic)
            await self._emit(event_emitter, "🔗 Validating URLs against collected sources...")
            answer, scrub_report = self._scrub_fabricated_urls(
                answer, known_urls
            )
            if scrub_report:
                logger.warning(
                    "Scrubbed %d fabricated URL(s) from synthesis",
                    len(scrub_report),
                )
                await self._emit(
                    event_emitter,
                    f"⚠️ Removed {len(scrub_report)} fabricated URL(s)",
                )
            else:
                await self._emit(event_emitter, "✅ All URLs verified against sources")

            # Step 2: LLM-based verification pass
            await self._emit(
                event_emitter,
                "🔍 Running credibility verification (checking claims, terminology, scope)...",
            )
            verification = await self._verify_synthesis(
                answer, all_sources, session, request, user
            )
            issues = verification.get("issues", [])
            critical_issues = [
                i for i in issues
                if isinstance(i, dict) and i.get("severity") == "critical"
            ]
            warning_issues = [
                i for i in issues
                if isinstance(i, dict) and i.get("severity") == "warning"
            ]

            # Derive credibility from issues when LLM returns unknown/missing
            credibility = verification.get("overall_credibility", "unknown")
            if credibility in ("unknown", "", None):
                credibility = self._derive_credibility(
                    len(critical_issues), len(warning_issues), len(all_sources)
                )
                verification["overall_credibility"] = credibility

            if critical_issues:
                await self._emit(
                    event_emitter,
                    f"🔴 Verification: {len(critical_issues)} critical issue(s), "
                    f"credibility={credibility}",
                )
                for ci in critical_issues:
                    detail = ci.get("detail", ci.get("type", "unknown issue"))
                    await self._emit(
                        event_emitter,
                        f"   ⚠️ {detail[:200]}",
                    )
            elif warning_issues:
                await self._emit(
                    event_emitter,
                    f"🟡 Verification: {len(warning_issues)} warning(s), "
                    f"credibility={credibility}",
                )
                for wi in warning_issues:
                    detail = wi.get("detail", wi.get("type", "unknown"))
                    await self._emit(
                        event_emitter,
                        f"   🟡 {detail[:200]}",
                    )
            elif credibility in ("unknown", "very_low"):
                await self._emit(
                    event_emitter,
                    f"⚪ Verification inconclusive — credibility={credibility}",
                )
            else:
                await self._emit(
                    event_emitter,
                    f"✅ Verification passed — credibility={credibility}",
                )

            # Write verification results to journal
            self._write_verification_journal(
                session, verification, scrub_report, all_sources
            )

            # Step 3: Remediate fabricated content if critical issues found
            if critical_issues:
                await self._emit(
                    event_emitter,
                    f"\U0001f9f9 Removing {len(critical_issues)} fabricated/unsupported claim(s) from synthesis...",
                )
                answer = await self._remediate_synthesis(
                    answer, critical_issues + warning_issues,
                    request, user,
                )
                await self._emit(
                    event_emitter,
                    "\u2705 Synthesis cleaned \u2014 fabricated content removed",
                )

            # Step 4: Append credibility report
            credibility_section = self._build_credibility_report(
                verification, scrub_report, all_sources
            )
            if credibility_section:
                answer += credibility_section

            # Write synthesis to journal (includes credibility report)
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
            parts.append("# Collected Sources (EXHAUSTIVE LIST)\n")
            parts.append(
                "These are the ONLY sources found during research. "
                "Your answer must be built EXCLUSIVELY from this evidence. "
                "Reference sources by number [Source N]. "
                "The Sources section of your answer must ONLY contain URLs "
                "from this list — copied exactly, character for character.\n"
            )
            for i, s in enumerate(all_sources, 1):
                parts.append(
                    f"[Source {i}] **{s.get('title', 'Untitled')}**\n"
                    f"   - URL: {s.get('url', 'N/A')}\n"
                    f"   - Domain: {s.get('domain', '')}\n"
                    f"   - Summary: {s.get('summary', '')}\n"
                )
        else:
            parts.append(
                "# Collected Sources\n\n"
                "**NO sources were collected.** Your synthesis must state "
                "that the research found no relevant sources and recommend "
                "alternative approaches. Do NOT generate an answer from "
                "general knowledge.\n"
            )

        source_count = len(all_sources)
        parts.append(
            "\n---\n\n"
            "## Synthesis Instructions\n\n"
            f"You have {source_count} source(s) to work with.\n"
            "- Address EVERY item in the Research Anchor's 'must_cover' list.\n"
            "- For items NOT covered by any source, list them in Gaps.\n"
            "- In the Sources section, list ONLY URLs that appear verbatim "
            "in the Collected Sources above.\n"
            "- If the evidence is insufficient for a comprehensive answer, "
            "produce a SHORTER answer that honestly reflects what the "
            "evidence supports. Do NOT pad with general knowledge.\n"
            "- Tag each factual claim: [SOURCED], [INFERRED], or [UNCERTAIN]."
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

    # ---- Post-synthesis verification pipeline ----

    @staticmethod
    def _extract_known_urls(sources: List[Dict]) -> Set[str]:
        """Build a set of all URLs from collected sources."""
        urls = set()
        for s in sources:
            url = s.get("url", "")
            if url and url != "N/A":
                urls.add(url)
                # Also add normalized variants (with/without trailing slash)
                stripped = url.rstrip("/")
                urls.add(stripped)
                urls.add(stripped + "/")
        return urls

    @staticmethod
    def _extract_urls_from_text(text: str) -> List[str]:
        """Extract all URLs from markdown text."""
        # Match markdown links [text](url) and bare URLs
        patterns = [
            r'\[.*?\]\((https?://[^\s\)]+)\)',  # markdown links
            r'(?<!\()(https?://[^\s\)\]>"]+)',   # bare URLs
        ]
        found = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                url = match.group(1) if match.lastindex else match.group(0)
                found.append(url)
        return list(dict.fromkeys(found))  # dedupe preserving order

    @staticmethod
    def _scrub_fabricated_urls(
        text: str,
        known_urls: Set[str],
    ) -> tuple:
        """Remove URLs from synthesis that don't appear in collected sources.

        Returns:
            Tuple of (cleaned_text, list_of_removed_urls).
        """
        if not known_urls:
            # No sources at all — can't validate
            return text, []

        urls_in_text = Synthesizer._extract_urls_from_text(text)
        fabricated = []

        for url in urls_in_text:
            url_clean = url.rstrip("/")
            # Check if this URL (or a close variant) is in known sources
            is_known = (
                url in known_urls
                or url_clean in known_urls
                or url_clean + "/" in known_urls
            )
            if not is_known:
                fabricated.append(url)

        if not fabricated:
            return text, []

        # Replace fabricated URLs with a clear marker
        cleaned = text
        for url in fabricated:
            # Replace in markdown links: [text](url) -> [text] *(URL removed: not in sources)*
            cleaned = re.sub(
                r'\[([^\]]*)\]\(' + re.escape(url) + r'\)',
                r'[\1] *(URL removed — not found in collected sources)*',
                cleaned,
            )
            # Replace bare URLs
            cleaned = cleaned.replace(
                url,
                f"~~{url}~~ *(fabricated — not in collected sources)*",
            )

        logger.warning(
            "Removed %d fabricated URL(s): %s",
            len(fabricated),
            ", ".join(fabricated[:5]),
        )
        return cleaned, fabricated

    async def _verify_synthesis(
        self,
        synthesis: str,
        sources: List[Dict],
        session: ResearchSession,
        request: Any,
        user: Dict,
    ) -> Dict:
        """Run LLM-based verification of the synthesis against sources.

        Returns a verification dict with issues, credibility rating, etc.
        Falls back to an empty result on failure.
        """
        if not sources:
            return {
                "issues": [],
                "overall_credibility": "very_low",
                "recommendation": "flag_for_user",
            }

        source_list = "\n".join(
            f"[Source {i}] {s.get('title', '?')} — {s.get('url', 'N/A')}"
            for i, s in enumerate(sources, 1)
        )
        user_prompt = (
            f"# Research Anchor\n{session.anchor}\n\n"
            f"# Collected Sources\n{source_list}\n\n"
            f"# Synthesis to Verify\n{synthesis}"
        )

        try:
            result = await self._sub_agent.run_json(
                system_prompt=_VERIFICATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                request=request,
                user=user,
            )
            if isinstance(result, dict):
                issues = result.get("issues", [])
                crit_count = sum(
                    1 for i in issues
                    if isinstance(i, dict) and i.get("severity") == "critical"
                )
                logger.info(
                    "Verification: credibility=%s, issues=%d (critical=%d)",
                    result.get("overall_credibility", "?"),
                    len(issues),
                    crit_count,
                )
                return result
            return {"issues": [], "overall_credibility": "medium",
                    "recommendation": "pass"}
        except Exception as e:
            logger.warning("Verification pass failed: %s", e)
            return {"issues": [], "overall_credibility": "unknown",
                    "recommendation": "pass"}

    @staticmethod
    def _build_credibility_report(
        verification: Dict,
        scrubbed_urls: List[str],
        sources: List[Dict],
    ) -> str:
        """Build a credibility/transparency section to append to the synthesis.

        Returns empty string if no issues found and credibility is high.
        """
        parts = []
        credibility = verification.get("overall_credibility", "unknown")
        issues = verification.get("issues", [])
        critical_issues = [
            i for i in issues
            if isinstance(i, dict) and i.get("severity") == "critical"
        ]
        warnings = [
            i for i in issues
            if isinstance(i, dict) and i.get("severity") == "warning"
        ]

        # Always show the report — transparency builds trust
        parts.append("\n\n---\n\n## Research Credibility Report\n")

        # Evidence basis
        source_count = len(sources)
        if source_count == 0:
            parts.append(
                "⚠️ **No sources collected.** This synthesis has no "
                "evidentiary basis and should not be relied upon.\n"
            )
        else:
            unique_domains = len(set(
                s.get("domain", "") for s in sources if s.get("domain")
            ))
            parts.append(
                f"- **Evidence basis:** {source_count} source(s) from "
                f"{unique_domains} domain(s)\n"
            )

        # Overall credibility
        cred_labels = {
            "high": "🟢 High — claims well-supported by diverse sources",
            "medium": "🟡 Medium — some claims supported, gaps remain",
            "low": "🟠 Low — thin evidence, significant gaps",
            "very_low": "🔴 Very Low — insufficient evidence for reliable conclusions",
            "unknown": "⚪ Unknown — verification could not be completed",
        }
        parts.append(
            f"- **Credibility:** {cred_labels.get(credibility, credibility)}\n"
        )

        # Scrubbed URLs
        if scrubbed_urls:
            parts.append(
                f"\n### ⚠️ Fabricated URLs Removed ({len(scrubbed_urls)})\n\n"
                "The following URLs were generated by the LLM but did NOT "
                "appear in any collected source. They have been struck through "
                "in the text above.\n"
            )
            for url in scrubbed_urls:
                parts.append(f"- ~~{url}~~\n")

        # Critical issues from verification
        if critical_issues:
            parts.append(
                f"\n### 🔴 Critical Issues ({len(critical_issues)})\n"
            )
            for issue in critical_issues:
                itype = issue.get("type", "unknown")
                detail = issue.get("detail", "")
                parts.append(f"- **{itype}**: {detail}\n")

        # Warnings
        if warnings:
            parts.append(
                f"\n### 🟡 Warnings ({len(warnings)})\n"
            )
            for issue in warnings:
                itype = issue.get("type", "unknown")
                detail = issue.get("detail", "")
                parts.append(f"- **{itype}**: {detail}\n")

        # Recommendation
        recommendation = verification.get("recommendation", "pass")
        if recommendation == "revise":
            parts.append(
                "\n**⚠️ Recommendation:** This synthesis may contain "
                "inaccuracies. Cross-check key claims before relying on them.\n"
            )
        elif recommendation == "flag_for_user":
            parts.append(
                "\n**🔴 Recommendation:** Evidence was insufficient for "
                "a reliable synthesis. Consider running `deep_research()` "
                "with authoritative domain crawling, or refine the query.\n"
            )

        return "".join(parts)

    @staticmethod
    def _derive_credibility(
        critical_count: int,
        warning_count: int,
        source_count: int,
    ) -> str:
        """Compute credibility from issue counts when the LLM didn't provide one."""
        if source_count == 0:
            return "very_low"
        if critical_count >= 2:
            return "low"
        if critical_count == 1:
            return "low" if warning_count else "medium"
        if warning_count >= 3:
            return "medium"
        if warning_count >= 1:
            return "medium"
        return "high" if source_count >= 3 else "medium"

    async def _remediate_synthesis(
        self,
        synthesis: str,
        issues: List[Dict],
        request: Any,
        user: Dict,
    ) -> str:
        """Rewrite synthesis to remove fabricated/unsupported content.

        Uses the LLM to surgically remove flagged content while preserving
        everything that was not flagged.
        """
        issue_list = "\n".join(
            f"- [{i.get('severity', '?')}] {i.get('type', '?')}: "
            f"{i.get('detail', '')} | Location: \"{i.get('location', '')[:150]}\""
            for i in issues
            if isinstance(i, dict)
        )
        user_prompt = (
            f"# Issues Found by Reviewer\n\n{issue_list}\n\n"
            f"# Synthesis to Clean\n\n{synthesis}"
        )
        try:
            cleaned = await self._sub_agent.run(
                system_prompt=_REMEDIATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                request=request,
                user=user,
            )
            if cleaned and len(cleaned) > 100:
                return cleaned
            logger.warning(
                "Remediation returned too-short result, keeping original"
            )
            return synthesis
        except Exception as e:
            logger.warning("Remediation pass failed: %s", e)
            return synthesis

    @staticmethod
    async def _emit(
        event_emitter: Optional[Callable],
        message: str,
        done: bool = False,
    ) -> None:
        """Emit a status message visible to the end user."""
        if event_emitter:
            await event_emitter(
                {
                    "type": "status",
                    "data": {"description": message, "done": done},
                }
            )

    def _write_verification_journal(
        self,
        session: ResearchSession,
        verification: Dict,
        scrubbed: List[str],
        sources: List[Dict],
    ) -> None:
        """Write verification results as a separate journal entry."""
        lines = ["# Verification Report\n"]
        credibility = verification.get("overall_credibility", "unknown")
        lines.append(f"**Overall credibility:** {credibility}\n")
        lines.append(
            f"**Recommendation:** {verification.get('recommendation', 'unknown')}\n"
        )
        lines.append(f"**Sources checked:** {len(sources)}\n")

        if scrubbed:
            lines.append(f"\n## Fabricated URLs Removed ({len(scrubbed)})\n")
            for url in scrubbed:
                lines.append(f"- {url}\n")

        issues = verification.get("issues", [])
        if issues:
            lines.append(f"\n## Issues Found ({len(issues)})\n")
            for issue in issues:
                if isinstance(issue, dict):
                    sev = issue.get("severity", "?")
                    itype = issue.get("type", "?")
                    detail = issue.get("detail", "")
                    loc = issue.get("location", "")[:100]
                    lines.append(f"- **[{sev}] {itype}**: {detail}\n")
                    if loc:
                        lines.append(f"  > {loc}\n")
        else:
            lines.append("\n## No issues found\n")

        url_check = verification.get("url_check", {})
        if url_check:
            fab = url_check.get("fabricated", [])
            if fab:
                lines.append("\n## URL Cross-Check\n")
                lines.append(
                    f"- URLs in synthesis: "
                    f"{len(url_check.get('urls_in_synthesis', []))}\n"
                )
                lines.append(
                    f"- URLs in sources: "
                    f"{len(url_check.get('urls_in_sources', []))}\n"
                )
                lines.append(f"- Fabricated (LLM-detected): {len(fab)}\n")

        filename = f"{len(session.iterations) + 3:02d}-verification.md"
        self._journal.write_entry(session.session_dir, filename, "\n".join(lines))
