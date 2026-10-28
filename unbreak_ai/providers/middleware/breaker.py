"""Circuit breaker: opens after 5 failures in 60 s, half-opens after 30 s (REQ-PRV-07)."""

from collections.abc import Awaitable, Callable

from unbreak_ai.providers.base import (
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
)
from unbreak_ai.providers.middleware.state import BreakerRecord, Clock, MiddlewareState

FAILURE_THRESHOLD = 5
FAILURE_WINDOW_S = 60.0
COOLDOWN_S = 30.0

_COUNTED = (ProviderTimeout, ProviderError, ProviderUnavailable)


class CircuitBreaker:
    def __init__(self, key: str, state: MiddlewareState, clock: Clock) -> None:
        self._key = f"breaker:{key}"
        self._name = key
        self._state = state
        self._clock = clock

    async def call[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        await self._admit()
        try:
            result = await fn()
        except _COUNTED:
            await self._record_failure()
            raise
        except BaseException:
            await self._release_probe()  # not a provider failure (NotSupported, cancellation)
            raise
        await self._record_success()
        return result

    async def _admit(self) -> None:
        record = await self._state.breaker_get(self._key)
        if record.opened_at is None:
            return
        if self._clock.now() - record.opened_at < COOLDOWN_S or record.probing:
            raise ProviderUnavailable(f"Provider {self._name} unavailable (circuit open)")
        record.probing = True  # half-open: let exactly one probe through
        await self._state.breaker_set(self._key, record)

    async def _record_success(self) -> None:
        await self._state.breaker_set(self._key, BreakerRecord())

    async def _record_failure(self) -> None:
        now = self._clock.now()
        record = await self._state.breaker_get(self._key)
        if record.probing:  # failed probe: reopen for another cooldown
            record.probing = False
            record.opened_at = now
        else:
            record.failures = [t for t in record.failures if now - t < FAILURE_WINDOW_S]
            record.failures.append(now)
            if len(record.failures) >= FAILURE_THRESHOLD:
                record.opened_at = now
        await self._state.breaker_set(self._key, record)

    async def _release_probe(self) -> None:
        record = await self._state.breaker_get(self._key)
        if record.probing:
            record.probing = False
            await self._state.breaker_set(self._key, record)
