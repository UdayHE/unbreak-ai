from pydantic import field_validator

from unbreak_ai.models.common import Model, UTCDateTime

LIST_MESSAGE_LIMIT = 500


def truncate_message(message: str, limit: int = LIST_MESSAGE_LIMIT) -> str:
    """Shorten a message for list output; full records keep their whole message."""
    return message if len(message) <= limit else message[: limit - 1] + "…"


class LogRecord(Model):
    ref: str  # opaque to the agent; round-trips to get / context
    timestamp: UTCDateTime
    level: str
    service: str | None = None
    namespace: str | None = None
    pod: str | None = None
    message: str
    trace_id: str | None = None
    source: str
    link: str | None = None

    @field_validator("level")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        return value.lower()


class Bucket(Model):
    at: UTCDateTime
    count: int


class CountItem(Model):
    name: str
    count: int


class LogOverview(Model):
    histogram: list[Bucket]
    top_levels: list[CountItem]
    top_services: list[CountItem]
    top_pods: list[CountItem]
    total: int
    source: str
    link: str | None = None


class ErrorPattern(Model):
    pattern: str
    count: int
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    services: list[str]
    sample_ref: str
    source: str
    link: str | None = None


class LogQuery(Model):
    level: str | None = None
    text: str | None = None


class Page[T](Model):
    items: list[T]
    next_cursor: str | None = None


__all__ = [
    "Bucket",
    "CountItem",
    "ErrorPattern",
    "LogOverview",
    "LogQuery",
    "LogRecord",
    "Page",
    "truncate_message",
]
