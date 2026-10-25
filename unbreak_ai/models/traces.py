"""Provisional (design.md, Data models): T-21 to T-25 may refine these through spec-fix commits."""

from typing import Literal

from pydantic import Field

from unbreak_ai.models.common import Model, UTCDateTime


class SpanSummary(Model):
    span_id: str
    service: str
    name: str
    duration_ms: float
    status: Literal["ok", "error"]


class TraceSummary(Model):
    trace_id: str
    root_service: str
    duration_ms: float
    spans: list[SpanSummary] = Field(max_length=20)
    source: str
    link: str | None = None


class ErrorGroup(Model):
    group_key: str
    message: str
    count: int
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    sample_trace_id: str | None = None
    source: str
    link: str | None = None
