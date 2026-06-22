"""Token counting and prompt trimming helpers."""
from __future__ import annotations

import re


def count_tokens(text: str) -> int:
    """Return a conservative token estimate, using tiktoken when available."""
    value = text or ""
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(value))
    except Exception:
        return max(1, int(len(re.findall(r"\w+|[^\w\s]", value, flags=re.UNICODE)) * 1.25))


def trim_prompt_to_token_limit(prompt: str, max_tokens: int) -> str:
    """Trim long prompts while preserving the beginning and model prediction context."""
    if count_tokens(prompt) <= max_tokens:
        return prompt
    marker = "Haber İçeriği:"
    if marker not in prompt:
        return prompt[: max_tokens * 4]
    before, after = prompt.split(marker, 1)
    budget_chars = max(800, max_tokens * 3 - len(before))
    return f"{before}{marker}{after[:budget_chars]}\n... [prompt token limiti nedeniyle kırpıldı]"
