"""Query cache: 60 s TTL, time windows rounded to 30 s, single-flight (REQ-PRV-08)."""

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from unbreak_ai.models.common import TimeWindow
from unbreak_ai.providers.middleware.state import MiddlewareState

TTL_S = 60.0
BUCKET_S = 30


def _canonical(value: Any) -> Any:
    """A JSON-friendly form of an argument; windows widen to 30 s boundaries."""
    if isinstance(value, TimeWindow):
        start = math.floor(value.start.timestamp() / BUCKET_S) * BUCKET_S
        end = math.ceil(value.end.timestamp() / BUCKET_S) * BUCKET_S
        return {
            "start": datetime.fromtimestamp(start, UTC).isoformat(),
            "end": datetime.fromtimestamp(end, UTC).isoformat(),
        }
    if isinstance(value, BaseModel):
        return {k: _canonical(getattr(value, k)) for k in type(value).model_fields}
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    return value


def cache_key(provider: str, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    payload = {"a": _canonical(args), "k": _canonical(kwargs)}
    return f"cache:{provider}:{method}:{json.dumps(payload, sort_keys=True, default=str)}"


class QueryCache:
    def __init__(self, state: MiddlewareState) -> None:
        self._state = state
        self._inflight: dict[str, asyncio.Task[Any]] = {}

    async def get_or_call[T](self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        """Return the cached value or run ``fn`` once for all concurrent callers of ``key``."""
        hit = await self._state.cache_get(key)
        if hit is not None:
            return hit  # type: ignore[return-value]
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._fill(key, fn))
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        return await asyncio.shield(task)

    async def _fill[T](self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        value = await fn()  # errors propagate and are not cached
        await self._state.cache_set(key, value, TTL_S)
        return value
