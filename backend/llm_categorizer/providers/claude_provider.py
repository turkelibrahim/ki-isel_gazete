"""Claude provider wrapper with optional dependency import."""
from __future__ import annotations

import asyncio
import os
import time

from backend.llm_categorizer.models import LLMCategorizationRequest, ProviderResult
from backend.llm_categorizer.prompts.system_prompt import build_system_prompt
from backend.llm_categorizer.prompts.user_prompt import build_user_prompt
from backend.llm_categorizer.utils.token_counter import count_tokens

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


class ClaudeProvider:
    """Thin wrapper around Anthropic Claude messages API."""

    provider = "claude"
    model_name = CLAUDE_MODEL

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 10) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.timeout_seconds = timeout_seconds

    async def categorize(self, request: LLMCategorizationRequest, retry_count: int = 0) -> ProviderResult:
        """Call Claude and return raw JSON text with token metadata."""
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(request, retry_count)
        started = time.perf_counter()

        def _call() -> ProviderResult:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout_seconds)
            response = client.messages.create(
                model=self.model_name,
                max_tokens=512,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
            usage = getattr(response, "usage", None)
            prompt_tokens = int(getattr(usage, "input_tokens", 0) or count_tokens(system_prompt + user_prompt))
            completion_tokens = int(getattr(usage, "output_tokens", 0) or count_tokens(raw))
            return ProviderResult(
                raw_response=raw,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time_ms=(time.perf_counter() - started) * 1000,
                provider=self.provider,
                model_name=self.model_name,
            )

        return await asyncio.to_thread(_call)
