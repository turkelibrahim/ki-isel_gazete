"""Usage statistics for LLM categorization calls."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.llm_categorizer.models import LLMCategorizationResponse, LLMUsageStats


class UsageStatsStore:
    """In-memory daily usage statistics store."""

    def __init__(self) -> None:
        self._stats: dict[str, LLMUsageStats] = {}

    def _key(self, date: datetime | None = None) -> str:
        target = date or datetime.now(timezone.utc)
        return target.date().isoformat()

    def get(self, date: datetime | None = None) -> LLMUsageStats:
        """Get or create stats for a UTC date."""
        key = self._key(date)
        if key not in self._stats:
            self._stats[key] = LLMUsageStats(date=date or datetime.now(timezone.utc))
        return self._stats[key]

    def update(self, response: LLMCategorizationResponse) -> None:
        """Update stats with one categorization response."""
        stats = self.get(response.created_at)
        previous_total_time = stats.avg_response_time_ms * max(stats.total_requests, 0)
        stats.total_requests += 1
        stats.total_tokens += response.total_tokens
        stats.total_cost_usd += response.estimated_cost_usd
        stats.avg_response_time_ms = (previous_total_time + response.response_time_ms) / stats.total_requests
        if response.is_reliable:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1
        if response.provider == "claude":
            stats.claude_requests += 1
        elif response.provider == "gpt4":
            stats.gpt4_requests += 1
        else:
            stats.fallback_requests += 1

    def increment_invalid_category(self) -> None:
        """Track a rejected category or invalid JSON response."""
        self.get().invalid_category_rejections += 1
