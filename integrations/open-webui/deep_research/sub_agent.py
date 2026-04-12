"""
Sub-agent for internal LLM calls within the Deep Research pipeline.

Single Responsibility: Only handles invoking the host LLM for sub-tasks.
Dependency Inversion: Depends on OWUI's generate_chat_completion abstraction.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("deep_research.sub_agent")


class SubAgent:
    """Executes internal LLM calls using OWUI's generate_chat_completion.

    Uses bypass_filter=True to prevent recursive function invocation.
    Reuses the user's selected model for all sub-agent calls.
    """

    def __init__(self, model_id: str):
        self._model_id = model_id

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        request: Any,
        user: Dict,
        metadata: Optional[Dict] = None,
        enable_web_search: bool = False,
        json_mode: bool = False,
    ) -> str:
        """Execute a sub-agent LLM call.

        Args:
            system_prompt: System-level instructions for the sub-agent.
            user_prompt: The user-facing query for this sub-task.
            request: The OWUI __request__ object for auth context.
            user: The OWUI __user__ dict.
            metadata: Optional metadata to forward.
            enable_web_search: Whether to enable web search for this call.
            json_mode: Whether to enforce JSON-only output framing.

        Returns:
            The LLM's response content as a string.
        """
        from open_webui.utils.chat import generate_chat_completion
        from open_webui.models.users import UserModel

        # OWUI injects its own system prompt into generate_chat_completion.
        # We still send a short system message to set the "role" — OWUI's
        # system prompt is prepended but ours is appended, so the model
        # still sees it.  For JSON calls we make the role unmistakable.
        if json_mode:
            sys_msg = ("You are a JSON data extraction API. "
                       "Respond with ONLY valid JSON. "
                       "No explanations, no markdown fences, no commentary.")
        else:
            sys_msg = "Follow the user's instructions precisely."

        # For web-search calls the search query must appear first so
        # OWUI's search-extraction picks it up.  We bracket the query
        # with strong JSON-mode framing so the LLM can't miss it.
        if enable_web_search:
            combined = (
                f"[JSON-ONLY MODE — respond with a JSON array, nothing else]\n\n"
                f"{user_prompt}\n\n"
                f"---\nINSTRUCTIONS (follow these exactly):\n{system_prompt}\n\n"
                f"REMINDER: Output ONLY a valid JSON array. No text before or after."
            )
        else:
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
            "metadata": {
                "task": "deep_research_sub_agent",
                **(
                    {"features": {"web_search": True}}
                    if enable_web_search
                    else {}
                ),
            },
        }

        response = await generate_chat_completion(
            request=request,
            form_data=form_data,
            user=UserModel(**user),
            bypass_filter=True,
        )

        content = response["choices"][0]["message"]["content"]
        logger.debug("Sub-agent response length: %d chars", len(content))
        return content

    async def run_json(
        self,
        system_prompt: str,
        user_prompt: str,
        request: Any,
        user: Dict,
        metadata: Optional[Dict] = None,
        enable_web_search: bool = False,
    ) -> Any:
        """Execute a sub-agent call and parse the response as JSON.

        Falls back to extracting JSON from markdown code blocks if the
        response isn't pure JSON.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The query for this sub-task.
            request: OWUI __request__ object.
            user: OWUI __user__ dict.
            metadata: Optional metadata.
            enable_web_search: Whether to enable web search.

        Returns:
            Parsed JSON object (dict or list).

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        raw = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            request=request,
            user=user,
            metadata=metadata,
            enable_web_search=enable_web_search,
            json_mode=True,
        )
        try:
            return self._parse_json_response(raw)
        except ValueError:
            logger.warning("JSON parse failed. Raw response (first 500 chars): %s",
                           raw[:500] if raw else "<empty>")
            raise

    @staticmethod
    def _parse_json_response(text: str) -> Any:
        """Extract and parse JSON from an LLM response.

        Handles pure JSON, JSON in markdown code blocks, and JSON
        embedded in surrounding commentary text.
        """
        text = text.strip()

        # Attempt 1: Pure JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Attempt 2: Markdown code blocks
        import re

        pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Attempt 3: Find first JSON array or object in raw text
        for pat in [r'(\[\s*\{.*\}\s*\])', r'(\{.*\})']:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass

        raise ValueError(
            f"Could not parse JSON from LLM response: {text[:300]}..."
        )

    @staticmethod
    def resolve_model_id(
        metadata: Optional[Dict],
        model: Optional[Dict],
    ) -> str:
        """Extract the active model ID from OWUI context objects.

        Args:
            metadata: The __metadata__ dict from OWUI.
            model: The __model__ dict from OWUI.

        Returns:
            Model ID string, or empty string if not found.
        """
        model_id = (
            ((metadata or {}).get("model") or {}).get("id", "")
            or (model or {}).get("id", "")
        )
        return model_id


# ---- Anchor extraction ----

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


async def extract_anchor(sa: SubAgent, query: str, request: Any, user: Dict) -> str:
    """Run one LLM call to distil the query into a reusable anchor block.

    Args:
        sa: SubAgent for LLM calls.
        query: Raw user query.
        request: OWUI __request__ object.
        user: OWUI __user__ dict.

    Returns:
        Multi-line anchor string to prepend to every prompt.
    """
    try:
        r = await sa.run_json(_ANCHOR_PROMPT, query, request, user)
    except Exception:
        return f"RESEARCH ANCHOR\nQuery: {query}\nKey concepts: (extraction failed \u2014 use query as-is)"
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
