"""Provisional (design.md, Data models): T-21 to T-25 may refine these through spec-fix commits."""

from pydantic import Field

from unbreak_ai.models.common import Model, TimeWindow, UTCDateTime


class Metric(Model):
    name: str
    unit: str | None = None
    value: float | None = None
    baseline: float | None = None
    delta_pct: float | None = None
    source: str


class ServiceHealth(Model):
    service: str
    window: TimeWindow
    baseline_window: TimeWindow
    latency_p95_ms: Metric
    throughput_rpm: Metric
    error_rate: Metric
    extra: list[Metric] = []
    source: str
    link: str | None = None


class Point(Model):
    at: UTCDateTime
    value: float


class Series(Model):
    signal: str
    points: list[Point] = Field(max_length=60)
    threshold: float | None = None
    unit: str | None = None
    source: str
    link: str | None = None


class Mover(Model):
    entity: str
    signal: str
    baseline_value: float
    current_value: float
    change_pct: float
    source: str
    link: str | None = None
