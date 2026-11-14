"""Per-client token bucket (L2 §6). The clock is injected so tests never sleep."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucket:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self.clock = clock
        self._lock = threading.Lock()
        self._state: dict[str, tuple[float, float]] = {}  # client -> (tokens, last time)

    def allow(self, client: str) -> bool:
        with self._lock:
            now = self.clock()
            tokens, last = self._state.get(client, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens < 1.0:
                self._state[client] = (tokens, now)
                return False
            self._state[client] = (tokens - 1.0, now)
            return True
