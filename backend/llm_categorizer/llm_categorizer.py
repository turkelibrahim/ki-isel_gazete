"""Main orchestration for SmartNewspaper LLM categorization fallback."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from backend.llm_categorizer.models import (
    ALLOWED_CATEGORIES,
    ALLOWED_CATEGORY_NAMES,
    LLMCategorizationRequest,
    LLMCategorizationResponse,
    LLMOutputSchema,
    LLMUsageStats,
    ProviderResult,
    utc_now,
)
from backend.llm_categorizer.prompts.system_prompt import build_system_prompt
from backend.llm_categorizer.prompts.user_prompt import build_user_prompt
from backend.llm_categorizer.providers.claude_provider import ClaudeProvider
from backend.llm_categorizer.providers.fallback_provider import FallbackProvider, rule_based_output
from backend.llm_categorizer.providers.gpt4_provider import GPT4Provider
from backend.llm_categorizer.utils.cache import TTLCache, build_cache_key
from backend.llm_categorizer.utils.cost_calculator import PRICING, calculate_cost
from backend.llm_categorizer.utils.token_counter import trim_prompt_to_token_limit
from backend.llm_categorizer.utils.usage_stats import UsageStatsStore
from backend.llm_categorizer.utils.validator import parse_and_validate_response, validate_categories

TRIGGER_REASONS = {"low_confidence", "no_label", "model_conflict", "manual", "cluster_conflict"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def should_use_llm(article: Any, category_result: Any, multilabel_result: Any) -> tuple[bool, str]:
    """Decide whether the LLM fallback is necessary for one article."""
    category = getattr(category_result, "category", None) if not isinstance(category_result, dict) else category_result.get("category")
    confidence = _float(
        getattr(category_result, "confidence", None) if not isinstance(category_result, dict)
        else category_result.get("confidence", category_result.get("category_confidence")),
        0.0,
    )
    labels = getattr(multilabel_result, "predicted_labels", None) if not isinstance(multilabel_result, dict) else multilabel_result.get("predicted_labels", multilabel_result.get("labels", []))
    no_label = bool(
        getattr(multilabel_result, "no_label_detected", False) if not isinstance(multilabel_result, dict)
        else multilabel_result.get("no_label_detected", len(labels or []) == 0)
    )
    if confidence < 0.85:
        return True, "low_confidence"
    if no_label:
        return True, "no_label"
    if category in ALLOWED_CATEGORY_NAMES and labels and category not in labels:
        return True, "model_conflict"
    cluster_id = getattr(article, "cluster_id", None) if not isinstance(article, dict) else article.get("cluster_id") or article.get("clusterId")
    if cluster_id and _cluster_has_category_conflict(article):
        return True, "cluster_conflict"
    return False, ""


def _cluster_has_category_conflict(article: Any) -> bool:
    """Return True when source-level categories inside a cluster disagree."""
    sources = [] if not isinstance(article, dict) else article.get("sources") or []
    categories = {source.get("category") for source in sources if isinstance(source, dict) and source.get("category") in ALLOWED_CATEGORY_NAMES}
    return len(categories) > 1


class LLMCategorizer:
    """Constrained, cached, provider-fallback LLM categorizer."""

    ALLOWED_CATEGORIES: dict[int, str] = ALLOWED_CATEGORIES
    MAX_CONTENT_CHARS: int = int(os.getenv("LLM_MAX_CONTENT_CHARS", "2000"))
    MAX_PROMPT_TOKENS: int = int(os.getenv("LLM_MAX_PROMPT_TOKENS", "3000"))
    MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    CACHE_TTL_SECONDS: int = int(os.getenv("LLM_CACHE_TTL_SECONDS", "86400"))
    CACHE_MAX_SIZE: int = int(os.getenv("LLM_CACHE_MAX_SIZE", "1000"))
    DEFAULT_TEMPERATURE: float = 0.0
    PRICING: dict[str, dict[str, float]] = PRICING

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        primary_provider: str = "claude",
        enabled: bool | None = None,
        daily_cost_limit_usd: float | None = None,
    ) -> None:
        self.enabled = enabled if enabled is not None else os.getenv("LLM_CATEGORIZER_ENABLED", "true").lower() != "false"
        self.primary_provider = primary_provider or os.getenv("LLM_PRIMARY_PROVIDER", "claude")
        self.daily_cost_limit_usd = daily_cost_limit_usd if daily_cost_limit_usd is not None else float(os.getenv("LLM_DAILY_COST_LIMIT_USD", "5.00"))
        timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "10"))
        self.claude_provider = ClaudeProvider(anthropic_api_key, timeout_seconds=timeout)
        self.gpt4_provider = GPT4Provider(openai_api_key, timeout_seconds=timeout)
        self.fallback_provider = FallbackProvider()
        self.cache: TTLCache[LLMCategorizationResponse] = TTLCache(self.CACHE_TTL_SECONDS, self.CACHE_MAX_SIZE)
        self.usage_stats = UsageStatsStore()

    def build_system_prompt(self) -> str:
        """Build the constrained system prompt."""
        return build_system_prompt()

    def build_user_prompt(self, request: LLMCategorizationRequest, retry_count: int = 0) -> str:
        """Build a trimmed user prompt for a request."""
        prompt = build_user_prompt(request, retry_count, max_content_chars=self.MAX_CONTENT_CHARS)
        return trim_prompt_to_token_limit(prompt, self.MAX_PROMPT_TOKENS)

    def check_token_limit(self, prompt: str) -> str:
        """Trim prompts over the maximum token limit."""
        return trim_prompt_to_token_limit(prompt, self.MAX_PROMPT_TOKENS)

    async def call_claude(self, request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        """Call Claude provider."""
        return await self.claude_provider.categorize(request, retry_count)

    async def call_gpt4(self, request: LLMCategorizationRequest, retry_count: int) -> ProviderResult:
        """Call OpenAI provider."""
        return await self.gpt4_provider.categorize(request, retry_count)

    def parse_and_validate_response(self, raw: str, retry_count: int) -> LLMOutputSchema | None:
        """Parse and validate provider output."""
        return parse_and_validate_response(raw, retry_count)

    def validate_categories(self, categories: list[str]) -> bool:
        """Validate category names against the fixed allow-list."""
        return validate_categories(categories)

    def rule_based_fallback(self, request: LLMCategorizationRequest) -> LLMOutputSchema:
        """Run the local keyword fallback."""
        return rule_based_output(request.title, request.summary, request.content)

    def check_cache(self, request: LLMCategorizationRequest) -> LLMCategorizationResponse | None:
        """Return cached response if available."""
        return self.cache.get(build_cache_key(request))

    def update_cache(self, request: LLMCategorizationRequest, response: LLMCategorizationResponse) -> None:
        """Cache a categorization response."""
        self.cache.set(build_cache_key(request), response)

    def calculate_cost(self, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate provider cost."""
        return calculate_cost(provider, prompt_tokens, completion_tokens)

    def get_usage_stats(self, date: datetime | None = None) -> LLMUsageStats:
        """Return daily usage statistics."""
        return self.usage_stats.get(date)

    def update_usage_stats(self, response: LLMCategorizationResponse) -> None:
        """Update usage counters."""
        self.usage_stats.update(response)

    def _daily_cost_exceeded(self) -> bool:
        return self.usage_stats.get().total_cost_usd >= self.daily_cost_limit_usd

    def _provider_order(self) -> list[str]:
        providers = ["claude", "gpt4"]
        if self.primary_provider == "gpt4":
            providers = ["gpt4", "claude"]
        return providers

    async def _call_provider_with_validation(
        self,
        provider: str,
        request: LLMCategorizationRequest,
    ) -> tuple[LLMOutputSchema | None, ProviderResult | None, int]:
        """Call one provider with invalid-output retries."""
        last_result: ProviderResult | None = None
        for retry_count in range(self.MAX_RETRIES + 1):
            try:
                result = await (self.call_claude(request, retry_count) if provider == "claude" else self.call_gpt4(request, retry_count))
            except Exception:
                return None, last_result, retry_count
            last_result = result
            validated = self.parse_and_validate_response(result.raw_response, retry_count)
            if validated is not None:
                return validated, result, retry_count
            self.usage_stats.increment_invalid_category()
        return None, last_result, self.MAX_RETRIES

    def _build_response(
        self,
        request: LLMCategorizationRequest,
        validated: LLMOutputSchema,
        provider_result: ProviderResult,
        retry_count: int,
    ) -> LLMCategorizationResponse:
        """Create a normalized response object from validated output."""
        categories = [category for category in validated.categories if category in ALLOWED_CATEGORY_NAMES]
        confidences = {category: round(float(validated.confidences.get(category, 0.0)), 4) for category in categories}
        total_tokens = provider_result.prompt_tokens + provider_result.completion_tokens
        is_reliable = bool(categories) and max(confidences.values() or [0.0]) >= 0.70
        cost = self.calculate_cost(provider_result.provider, provider_result.prompt_tokens, provider_result.completion_tokens)
        return LLMCategorizationResponse(
            article_id=request.article_id,
            cluster_id=request.cluster_id,
            predicted_labels=categories,
            label_confidences=confidences,
            reasoning=validated.reasoning,
            provider=provider_result.provider,
            model_name=provider_result.model_name,
            prompt_tokens=provider_result.prompt_tokens,
            completion_tokens=provider_result.completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            is_reliable=is_reliable,
            no_label_detected=len(categories) == 0,
            retry_count=retry_count,
            response_time_ms=provider_result.response_time_ms,
            raw_response=provider_result.raw_response,
            created_at=utc_now(),
            used=True,
            trigger_reason=request.trigger_reason,
        )

    async def _fallback_response(self, request: LLMCategorizationRequest, retry_count: int = 0) -> LLMCategorizationResponse:
        """Build response via rule-based fallback."""
        result = await self.fallback_provider.categorize(request.title, request.summary, request.content)
        validated = self.parse_and_validate_response(result.raw_response, retry_count) or LLMOutputSchema(categories=[], confidences={}, reasoning="Fallback sonucu doğrulanamadı.")
        return self._build_response(request, validated, result, retry_count)

    async def categorize(self, request: LLMCategorizationRequest) -> LLMCategorizationResponse:
        """Categorize one request with cache, provider fallback and validation."""
        cached = self.check_cache(request)
        if cached:
            return cached

        if not self.enabled or self._daily_cost_exceeded():
            response = await self._fallback_response(request)
            self.update_cache(request, response)
            self.update_usage_stats(response)
            return response

        if not (request.title or request.summary or request.content):
            response = await self._fallback_response(request)
            self.update_cache(request, response)
            self.update_usage_stats(response)
            return response

        for provider in self._provider_order():
            validated, provider_result, retry_count = await self._call_provider_with_validation(provider, request)
            if validated is not None and provider_result is not None:
                response = self._build_response(request, validated, provider_result, retry_count)
                self.update_cache(request, response)
                self.update_usage_stats(response)
                return response

        response = await self._fallback_response(request, retry_count=self.MAX_RETRIES)
        self.update_cache(request, response)
        self.update_usage_stats(response)
        return response

    async def categorize_batch(
        self,
        requests: list[LLMCategorizationRequest],
        max_concurrent: int = 5,
    ) -> list[LLMCategorizationResponse]:
        """Categorize a batch without letting one failed item break the batch."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_categorize(req: LLMCategorizationRequest) -> LLMCategorizationResponse | Exception:
            async with semaphore:
                try:
                    return await self.categorize(req)
                except Exception as exc:
                    return exc

        results = await asyncio.gather(*(limited_categorize(req) for req in requests), return_exceptions=False)
        valid_results: list[LLMCategorizationResponse] = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                fallback_request = requests[index]
                valid_results.append(await self._fallback_response(fallback_request))
            else:
                valid_results.append(result)
        return valid_results


def build_request_from_article(article: dict[str, Any], trigger_reason: str = "manual") -> LLMCategorizationRequest:
    """Convenience helper for API adapters."""
    reason = trigger_reason if trigger_reason in TRIGGER_REASONS else "manual"
    return LLMCategorizationRequest.from_article(article, reason)


async def categorize_article(article: dict[str, Any], trigger_reason: str = "manual") -> dict[str, Any]:
    """Classify a single article and return a dictionary response."""
    categorizer = LLMCategorizer()
    request = build_request_from_article(article, trigger_reason)
    return (await categorizer.categorize(request)).to_dict()


async def categorize_articles(articles: list[dict[str, Any]], trigger_reason: str = "manual") -> list[dict[str, Any]]:
    """Classify multiple articles and return dictionary responses."""
    categorizer = LLMCategorizer()
    requests = [build_request_from_article(article, trigger_reason) for article in articles]
    return [item.to_dict() for item in await categorizer.categorize_batch(requests)]
