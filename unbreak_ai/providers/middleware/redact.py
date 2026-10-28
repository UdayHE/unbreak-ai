"""Redaction of configured patterns in provider output (NFR-10)."""

import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

REDACTED = "[REDACTED]"


class Redactor:
    def __init__(self, patterns: Sequence[str]) -> None:
        self._patterns = [re.compile(p) for p in patterns]

    def redact[T](self, value: T) -> T:
        """A copy of ``value`` with every match in any string replaced by ``[REDACTED]``."""
        return self._walk(value)  # type: ignore[no-any-return]

    def _walk(self, value: Any) -> Any:
        if isinstance(value, str):
            for pattern in self._patterns:
                value = pattern.sub(REDACTED, value)
            return value
        if isinstance(value, BaseModel):
            update = {name: self._walk(getattr(value, name)) for name in type(value).model_fields}
            return value.model_copy(update=update)
        if isinstance(value, list):
            return [self._walk(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._walk(v) for v in value)
        if isinstance(value, dict):
            return {k: self._walk(v) for k, v in value.items()}
        return value
