"""Small TTL cache for LLM categorization responses."""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Generic, TypeVar

from backend.llm_categorizer.models import LLMCategorizationRequest

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Dependency-free bounded TTL cache."""

    def __init__(self, ttl_seconds: int = 86400, max_size: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        """Return a cached value if present and not expired."""
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return value

    def set(self, key: str, value: T) -> None:
        """Store a value and evict oldest entries when needed."""
        self._items[key] = (time.time() + self.ttl_seconds, value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached values."""
        self._items.clear()

    @property
    def size(self) -> int:
        """Return number of cached entries."""
        return len(self._items)


def build_cache_key(request: LLMCategorizationRequest) -> str:
    """Create a stable cache key from article identity and text preview."""
    seed = f"{request.title}|{(request.content or '')[:500]}|{request.language}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()
