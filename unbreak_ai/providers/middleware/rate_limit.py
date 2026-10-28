"""Token-bucket rate limit per provider (REQ-PRV-09)."""

import asyncio
from collections.abc import Awaitable, Callable

from unbreak_ai.providers.middleware.state import MiddlewareState

Sleep = Callable[[float], Awaitable[None]]


class RateLimiter:
    def __init__(
        self, key: str, max_qps: float, state: MiddlewareState, sleep: Sleep = asyncio.sleep
    ) -> None:
        self._key = f"ratelimit:{key}"
        self._rate = max_qps
        self._capacity = max(1.0, max_qps)
        self._state = state
        self._sleep = sleep

    async def acquire(self) -> None:
        wait = await self._state.take_token(self._key, self._rate, self._capacity)
        if wait > 0:
            await self._sleep(wait)
