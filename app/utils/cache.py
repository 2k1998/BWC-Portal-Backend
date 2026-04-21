from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Hashable, Tuple


class TTLCache:
    """Simple process-local in-memory TTL cache."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: Hashable) -> Any:
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl_seconds, value)

