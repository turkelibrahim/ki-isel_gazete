"""OpenAI GPT fallback provider wrapper."""
from __future__ import annotations

import os
import time

from backend.llm_categorizer.models import LLMCategorizationRequest, ProviderResult
from backend.llm_categorizer.prompts.system_prompt import build_system_prompt
from backend.llm_categorizer.prompts.user_prompt import build_user_prompt
from backend.llm_categorizer.utils.token_counter import count_tokens

GPT4_MODEL = "gpt-4o-mini"


class GPT4Provider:
    """Thin wrapper around OpenAI chat completions JSON mode."""

    provider = "gpt4"
    model_name = GPT4_MODEL

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 10) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds

    async def categorize(self, request: LLMCategorizationRequest, retry_count: int = 0) -> ProviderResult:
        """Call GPT-4o mini and return raw JSON text with token metadata."""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        import openai  # type: ignore

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(request, retry_count)
        started = time.perf_counter()
        client = openai.AsyncOpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        response = await client.chat.completions.create(
            model=self.model_name,
            max_tokens=512,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or count_tokens(system_prompt + user_prompt))
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or count_tokens(raw))
        return ProviderResult(
            raw_response=raw,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            response_time_ms=(time.perf_counter() - started) * 1000,
            provider=self.provider,
            model_name=self.model_name,
        )
