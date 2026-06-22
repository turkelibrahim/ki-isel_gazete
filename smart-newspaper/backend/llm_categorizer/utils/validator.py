"""Validation and parsing helpers for LLM categorization output."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from backend.llm_categorizer.models import ALLOWED_CATEGORY_NAMES, LLMOutputSchema


def parse_and_validate_response(raw_response: str, retry_count: int = 0) -> LLMOutputSchema | None:
    """Parse JSON-like provider output and validate it against allowed categories."""
    raw = (raw_response or "").strip()
    raw = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    try:
        validated = LLMOutputSchema(**data)
    except ValidationError:
        return None
    allowed_confidences = {key: value for key, value in validated.confidences.items() if key in validated.categories}
    return LLMOutputSchema(categories=validated.categories, confidences=allowed_confidences, reasoning=validated.reasoning)


def validate_categories(categories: list[str]) -> bool:
    """Return True only when every category is in the allowed list."""
    return all(category in ALLOWED_CATEGORY_NAMES for category in categories)
