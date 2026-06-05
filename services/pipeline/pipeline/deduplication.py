"""Dedupe stores for pipeline ingestion."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class InMemoryDedupeStore:
    ttl_seconds: int = 24 * 60 * 60
    _items: dict[str, float] = field(default_factory=dict)
    _hits: int = 0
    _misses: int = 0

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [key for key, expires_at in self._items.items() if expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    async def remember(self, *keys: str) -> None:
        self._purge()
        expires_at = time.monotonic() + self.ttl_seconds
        for key in keys:
            if key:
                self._items[key] = expires_at

    async def is_seen(self, *keys: str) -> bool:
        self._purge()
        found = any(bool(key) and key in self._items for key in keys)
        if found:
            self._hits += 1
        else:
            self._misses += 1
        return found

    async def stats(self) -> dict[str, int | str]:
        self._purge()
        return {
            "backend": "memory",
            "size": len(self._items),
            "hits": self._hits,
            "misses": self._misses,
        }

