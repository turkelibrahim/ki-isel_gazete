"""Rule-based fallback provider tests."""
from __future__ import annotations

import asyncio

from backend.llm_categorizer.providers.fallback_provider import FallbackProvider, rule_based_output


def test_fallback_detects_technology_and_economy() -> None:
    output = rule_based_output(
        "OpenAI yapay zeka yatırımını duyurdu",
        "Yazılım ve çip şirketleri borsa ve yatırım piyasasını etkiledi.",
        "Teknoloji, API, ekonomi, piyasa ve merkez bankası beklentileri öne çıktı.",
    )
    assert "Teknoloji" in output.categories
    assert "Ekonomi" in output.categories
    assert max(output.confidences.values()) <= 0.75


def test_fallback_returns_empty_for_unclear_text() -> None:
    output = rule_based_output("Mahalle duyurusu", "Kısa bir açıklama", "")
    assert output.categories == []
    assert output.confidences == {}


def test_fallback_provider_returns_provider_result() -> None:
    result = asyncio.run(FallbackProvider().categorize("Futbol maçında gol", "Lig ve transfer gündemi", "Spor haberi"))
    assert result.provider == "fallback"
    assert result.prompt_tokens == 0
    assert "Spor" in result.raw_response
