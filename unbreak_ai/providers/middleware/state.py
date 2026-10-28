"""Clock and the middleware state interface (REQ-PRV-07..09).

The cache, rate limiter and circuit breaker keep their state behind ``MiddlewareState``. The
in-memory implementation serves one process; T-31 adds a Redis one so all workers share state.
"""

from dataclasses import dataclass, field
from time import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class SystemClock:
    def now(self) -> float:
        return time()


@dataclass
class BreakerRecord:
    failures: list[float] = field(default_factory=list[float])  # timestamps inside the window
    opened_at: float | None = None  # None while closed
    probing: bool = False  # a half-open probe call is in flight


class MiddlewareState(Protocol):
    async def cache_get(self, key: str) -> object | None:
        """The cached value, or None on a miss or after its TTL."""
        ...

    async def cache_set(self, key: str, value: object, ttl: float) -> None: ...

    async def take_token(self, key: str, rate: float, capacity: float) -> float:
        """Reserve one token and return the seconds to wait before using it (0 if available)."""
        ...

    async def breaker_get(self, key: str) -> BreakerRecord: ...

    async def breaker_set(self, key: str, record: BreakerRecord) -> None: ...


class InMemoryState:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._cache: dict[str, tuple[float, object]] = {}
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, updated_at)
        self._breakers: dict[str, BreakerRecord] = {}

    async def cache_get(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock.now() >= expires_at:
            del self._cache[key]
            return None
        return value

    async def cache_set(self, key: str, value: object, ttl: float) -> None:
        self._cache[key] = (self._clock.now() + ttl, value)

    async def take_token(self, key: str, rate: float, capacity: float) -> float:
        now = self._clock.now()
        tokens, updated = self._buckets.get(key, (capacity, now))
        tokens = min(capacity, tokens + (now - updated) * rate)
        tokens -= 1  # may go negative: the caller waits for the deficit to refill
        self._buckets[key] = (tokens, now)
        return max(0.0, -tokens / rate)

    async def breaker_get(self, key: str) -> BreakerRecord:
        return self._breakers.get(key) or BreakerRecord()

    async def breaker_set(self, key: str, record: BreakerRecord) -> None:
        self._breakers[key] = record
