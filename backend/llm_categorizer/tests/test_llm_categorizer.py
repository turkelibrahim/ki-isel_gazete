"""Main LLM categorizer orchestration tests."""
from __future__ import annotations

import asyncio
import json

from backend.llm_categorizer.llm_categorizer import LLMCategorizer, build_request_from_article, should_use_llm
from backend.llm_categorizer.models import LLMCategorizationRequest, ProviderResult


def _request(title: str = "OpenAI yeni yapay zeka çipini duyurdu", trigger: str = "low_confidence") -> LLMCategorizationRequest:
    return LLMCategorizationRequest(
        article_id="a1",
        cluster_id=None,
        title=title,
        content="Yapay zeka, GPU, çip, yazılım ve API alanında yeni teknoloji duyuruldu.",
        summary="Teknoloji haberi",
        language="tr",
        source_name="Test",
        source_url="https://example.com",
        trigger_reason=trigger,
        ml_prediction={"category": "Teknoloji", "confidence": 0.7},
        multilabel_prediction={"labels": [], "no_label_detected": True},
        category_prediction={"category": "Teknoloji", "category_confidence": 0.7},
    )


def test_should_use_llm_low_confidence() -> None:
    use, reason = should_use_llm({}, {"category": "Teknoloji", "category_confidence": 0.6}, {"labels": ["Teknoloji"], "no_label_detected": False})
    assert use is True
    assert reason == "low_confidence"


def test_should_use_llm_model_conflict() -> None:
    use, reason = should_use_llm({}, {"category": "Ekonomi", "category_confidence": 0.92}, {"labels": ["Teknoloji"], "no_label_detected": False})
    assert use is True
    assert reason == "model_conflict"


def test_claude_single_call_success() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x", openai_api_key=None)

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        return ProviderResult(
            raw_response=json.dumps({"categories": ["Teknoloji"], "confidences": {"Teknoloji": 0.97}, "reasoning": "AI çipi"}, ensure_ascii=False),
            prompt_tokens=100,
            completion_tokens=20,
            response_time_ms=12.5,
            provider="claude",
            model_name="claude-3-5-sonnet-20241022",
        )

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request()))
    assert response.predicted_labels == ["Teknoloji"]
    assert response.provider == "claude"
    assert response.retry_count == 0
    assert response.estimated_cost_usd > 0


def test_multi_category_health_technology() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x")

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        return ProviderResult(
            raw_response='{"categories":["Sağlık","Teknoloji"],"confidences":{"Sağlık":0.94,"Teknoloji":0.87},"reasoning":"Teşhis sistemi"}',
            prompt_tokens=110,
            completion_tokens=30,
            response_time_ms=10,
            provider="claude",
            model_name="claude-3-5-sonnet-20241022",
        )

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request("Sağlık Bakanlığı yapay zeka teşhis sistemini tanıttı")))
    assert response.predicted_labels == ["Sağlık", "Teknoloji"]


def test_invalid_category_retry_then_success() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x")
    calls: list[int] = []

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        calls.append(retry_count)
        raw = '{"categories":["Gündem"],"confidences":{"Gündem":0.99},"reasoning":"invalid"}' if retry_count == 0 else '{"categories":["Siyaset"],"confidences":{"Siyaset":0.86},"reasoning":"politics"}'
        return ProviderResult(raw, 100, 20, 8, "claude", "claude-3-5-sonnet-20241022")

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request("Bakan mecliste yasa teklifini açıkladı")))
    assert response.predicted_labels == ["Siyaset"]
    assert response.retry_count == 1
    assert categorizer.get_usage_stats().invalid_category_rejections == 1


def test_non_json_retry_then_valid_json() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x")

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        raw = "Bu haber teknoloji" if retry_count == 0 else '{"categories":["Teknoloji"],"confidences":{"Teknoloji":0.9},"reasoning":"AI"}'
        return ProviderResult(raw, 50, 10, 3, "claude", "claude-3-5-sonnet-20241022")

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request()))
    assert response.predicted_labels == ["Teknoloji"]
    assert response.retry_count == 1


def test_claude_failure_openai_fallback() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x", openai_api_key="y")

    async def broken_claude(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        raise RuntimeError("rate limit")

    async def fake_gpt(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        return ProviderResult('{"categories":["Ekonomi"],"confidences":{"Ekonomi":0.91},"reasoning":"Faiz"}', 80, 20, 4, "gpt4", "gpt-4o-mini")

    categorizer.call_claude = broken_claude  # type: ignore[method-assign]
    categorizer.call_gpt4 = fake_gpt  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request("Merkez Bankası faiz kararını açıkladı")))
    assert response.provider == "gpt4"
    assert response.predicted_labels == ["Ekonomi"]


def test_all_providers_down_uses_fallback() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x", openai_api_key="y")

    async def broken(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        raise RuntimeError("down")

    categorizer.call_claude = broken  # type: ignore[method-assign]
    categorizer.call_gpt4 = broken  # type: ignore[method-assign]
    response = asyncio.run(categorizer.categorize(_request("Futbol maçında iki gol ve transfer gündemi")))
    assert response.provider == "fallback"
    assert "Spor" in response.predicted_labels


def test_empty_content_does_not_call_api() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x")
    called = False

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        nonlocal called
        called = True
        return ProviderResult("{}", 1, 1, 1, "claude", "x")

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    request = LLMCategorizationRequest(
        article_id="empty",
        cluster_id=None,
        title="",
        content="",
        summary=None,
        language="tr",
        source_name=None,
        source_url=None,
        trigger_reason="no_label",
        ml_prediction={},
        multilabel_prediction=None,
        category_prediction=None,
    )
    response = asyncio.run(categorizer.categorize(request))
    assert called is False
    assert response.predicted_labels == []


def test_cache_hit_avoids_second_provider_call() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x")
    call_count = 0

    async def fake_call(request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        nonlocal call_count
        call_count += 1
        return ProviderResult('{"categories":["Teknoloji"],"confidences":{"Teknoloji":0.9},"reasoning":"AI"}', 50, 10, 2, "claude", "model")

    categorizer.call_claude = fake_call  # type: ignore[method-assign]
    request = _request()
    first = asyncio.run(categorizer.categorize(request))
    second = asyncio.run(categorizer.categorize(request))
    assert first.predicted_labels == second.predicted_labels
    assert call_count == 1


def test_batch_10_respects_results() -> None:
    categorizer = LLMCategorizer(enabled=False)
    requests = [_request(f"OpenAI yapay zeka çip haber {index}") for index in range(10)]
    results = asyncio.run(categorizer.categorize_batch(requests, max_concurrent=5))
    assert len(results) == 10
    assert all(result.provider == "fallback" for result in results)


def test_cost_limit_forces_fallback() -> None:
    categorizer = LLMCategorizer(enabled=True, anthropic_api_key="x", daily_cost_limit_usd=0.0)
    response = asyncio.run(categorizer.categorize(_request()))
    assert response.provider == "fallback"


def test_build_request_from_article_payload() -> None:
    request = build_request_from_article({"id": "1", "title": "OpenAI haberi", "category": "Teknoloji", "labels": []}, "manual")
    assert request.article_id == "1"
    assert request.trigger_reason == "manual"
    assert request.category_prediction is not None
