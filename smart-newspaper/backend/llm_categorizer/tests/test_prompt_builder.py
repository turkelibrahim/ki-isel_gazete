"""Prompt builder tests."""
from __future__ import annotations

from backend.llm_categorizer.models import LLMCategorizationRequest
from backend.llm_categorizer.prompts.system_prompt import build_system_prompt
from backend.llm_categorizer.prompts.user_prompt import build_user_prompt


def _request(content: str = "İçerik") -> LLMCategorizationRequest:
    return LLMCategorizationRequest(
        article_id="1",
        cluster_id=None,
        title="OpenAI yeni yapay zeka çipini duyurdu",
        content=content,
        summary="Teknoloji haberi",
        language="tr",
        source_name="Test",
        source_url="https://example.com",
        trigger_reason="low_confidence",
        ml_prediction={"category": "Teknoloji"},
        multilabel_prediction={"labels": []},
        category_prediction={"category": "Teknoloji", "category_confidence": 0.7},
    )


def test_system_prompt_contains_only_allowed_categories() -> None:
    prompt = build_system_prompt()
    assert "Teknoloji" in prompt
    assert "Siyaset" in prompt
    assert "Diğer" not in prompt
    assert "JSON formatı" in prompt


def test_user_prompt_preserves_context() -> None:
    prompt = build_user_prompt(_request())
    assert "Haber Başlığı" in prompt
    assert "OpenAI" in prompt
    assert "low_confidence" in prompt
    assert "Mevcut ML tahmini" in prompt


def test_user_prompt_truncates_long_content() -> None:
    prompt = build_user_prompt(_request("a" * 3000), max_content_chars=2000)
    assert "[içerik kısaltıldı]" in prompt
    assert len(prompt) < 3500


def test_retry_prompt_contains_warning() -> None:
    prompt = build_user_prompt(_request(), retry_count=1)
    assert "Önceki yanıt geçersiz" in prompt
