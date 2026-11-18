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


class DailyCap:
    """At most `per_day` calls per UTC day, across all clients (L4 §3, threat T-W2): a public link must not
    use up the model provider's free daily quota. The clock is wall time, injected for tests."""

    def __init__(self, per_day: int, clock: Callable[[], float] = time.time) -> None:
        self.per_day = per_day
        self.clock = clock
        self._lock = threading.Lock()
        self._day, self._used = -1, 0

    def allow(self) -> bool:
        with self._lock:
            day = int(self.clock() // 86400)
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.per_day:
                return False
            self._used += 1
            return True
