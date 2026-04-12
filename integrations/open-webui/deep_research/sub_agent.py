"""
Sub-agent for internal LLM calls within the Deep Research pipeline.

Single Responsibility: Only handles invoking the host LLM for sub-tasks.
Dependency Inversion: Depends on OWUI's generate_chat_completion abstraction.
"""

import json
import logging
from typing import Any, Dict, Optional

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
    ) -> str:
        """Execute a sub-agent LLM call.

        Args:
            system_prompt: System-level instructions for the sub-agent.
            user_prompt: The user-facing query for this sub-task.
            request: The OWUI __request__ object for auth context.
            user: The OWUI __user__ dict.
            metadata: Optional metadata to forward.
            enable_web_search: Whether to enable web search for this call.

        Returns:
            The LLM's response content as a string.
        """
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
        )
        return self._parse_json_response(raw)

    @staticmethod
    def _parse_json_response(text: str) -> Any:
        """Extract and parse JSON from an LLM response.

        Handles both pure JSON and JSON wrapped in markdown code blocks.
        """
        text = text.strip()

        # Try pure JSON first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        import re

        pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Could not parse JSON from LLM response: {text[:200]}..."
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
