"""Wrap a provider with the middleware stack.

A call goes cache -> circuit breaker -> rate limit -> provider -> redaction. A cache hit uses no
rate-limit budget and does not count as a probe, and nothing unredacted is ever cached.
"""

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

from unbreak_ai.providers.base import Provider
from unbreak_ai.providers.middleware.breaker import CircuitBreaker
from unbreak_ai.providers.middleware.cache import QueryCache, cache_key
from unbreak_ai.providers.middleware.rate_limit import RateLimiter, Sleep
from unbreak_ai.providers.middleware.redact import Redactor
from unbreak_ai.providers.middleware.state import Clock, MiddlewareState, SystemClock


class _WrappedProvider:
    def __init__(
        self,
        provider: Provider,
        max_qps: float,
        redaction_patterns: Sequence[str],
        state: MiddlewareState,
        clock: Clock,
        sleep: Sleep,
    ) -> None:
        self._provider = provider
        self.name = provider.name
        self.capabilities = provider.capabilities
        self._cache = QueryCache(state)
        self._breaker = CircuitBreaker(provider.name, state, clock)
        self._limiter = RateLimiter(provider.name, max_qps, state, sleep)
        self._redactor = Redactor(redaction_patterns)

    def __getattr__(self, attr: str) -> Any:
        target = getattr(self._provider, attr)
        if not inspect.iscoroutinefunction(target):
            return target
        method: Callable[..., Awaitable[Any]] = target

        async def call(*args: Any, **kwargs: Any) -> Any:
            async def query() -> Any:
                await self._limiter.acquire()
                return self._redactor.redact(await method(*args, **kwargs))

            key = cache_key(self.name, attr, args, kwargs)
            return await self._cache.get_or_call(key, lambda: self._breaker.call(query))

        return call


def wrap_provider[P: Provider](
    provider: P,
    max_qps: float,
    redaction_patterns: Sequence[str],
    state: MiddlewareState,
    clock: Clock | None = None,
    sleep: Sleep = asyncio.sleep,
) -> P:
    wrapped = _WrappedProvider(
        provider, max_qps, redaction_patterns, state, clock or SystemClock(), sleep
    )
    return cast(P, wrapped)
