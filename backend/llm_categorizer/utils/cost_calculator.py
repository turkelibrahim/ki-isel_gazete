"""Cost calculation helpers for SmartNewspaper LLM calls."""
from __future__ import annotations

PRICING: dict[str, dict[str, float]] = {
    "claude": {"input": 0.000003, "output": 0.000015},
    "gpt4": {"input": 0.00000015, "output": 0.0000006},
    "fallback": {"input": 0.0, "output": 0.0},
}


def calculate_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost in USD for a provider response."""
    pricing = PRICING.get(provider, PRICING["gpt4"])
    return round(prompt_tokens * pricing["input"] + completion_tokens * pricing["output"], 6)
