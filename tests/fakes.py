"""Fake providers and settings, reusable by the contract suites (T-07 onward)."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from unbreak_ai.config.schema import NotifierSettings, ProviderSettings, Secret
from unbreak_ai.models.alert import Alert
from unbreak_ai.models.changes import ChangeEvent, DiffSummary
from unbreak_ai.models.common import Scope, TimeWindow
from unbreak_ai.models.logs import ErrorPattern, LogOverview, LogQuery, LogRecord, Page
from unbreak_ai.models.metrics import Metric, Mover, Series, ServiceHealth
from unbreak_ai.models.traces import ErrorGroup, TraceSummary
from unbreak_ai.providers.base import PATTERN_AGGREGATION

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


class FakeCredentials(BaseModel):
    token: Secret


class FakeLogsSettings(ProviderSettings):
    type: Literal["fake"]
    greeting: str = "hi"
    credentials: FakeCredentials | None = None  # nested model holding a secret
    extra_tokens: list[FakeCredentials] = []  # secrets inside a list of nested models


class FakeNotifierSettings(NotifierSettings):
    type: Literal["fake"]


class FakeLogsProvider:
    name = "fake"
    capabilities = frozenset({PATTERN_AGGREGATION})

    def __init__(self, settings: FakeLogsSettings) -> None:
        self.settings = settings

    @classmethod
    def from_settings(cls, settings: FakeLogsSettings) -> "FakeLogsProvider":
        return cls(settings)

    def _record(self) -> LogRecord:
        return LogRecord(
            ref="r1", timestamp=NOW, level="error", message=self.settings.greeting, source=self.name
        )

    async def overview(self, scope: Scope, window: TimeWindow) -> LogOverview:
        return LogOverview(
            histogram=[], top_levels=[], top_services=[], top_pods=[], total=0, source=self.name
        )

    async def error_patterns(
        self, scope: Scope, window: TimeWindow, limit: int = 20
    ) -> list[ErrorPattern]:
        return []

    async def search(
        self,
        scope: Scope,
        window: TimeWindow,
        query: LogQuery,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Page[LogRecord]:
        return Page[LogRecord](items=[self._record()])

    async def get(self, ref: str) -> LogRecord:
        return self._record()

    async def context(self, ref: str, before: int = 20, after: int = 20) -> list[LogRecord]:
        return [self._record()]


class FakeMetricsProvider:
    name = "fake-metrics"
    capabilities = frozenset[str]()

    async def service_health(
        self, service: str, window: TimeWindow, baseline: TimeWindow
    ) -> ServiceHealth:
        metric = Metric(name="x", source=self.name)
        return ServiceHealth(
            service=service,
            window=window,
            baseline_window=baseline,
            latency_p95_ms=metric,
            throughput_rpm=metric,
            error_rate=metric,
            source=self.name,
        )

    async def alert_context(self, alert: Alert, window: TimeWindow) -> Series:
        return Series(signal="x", points=[], source=self.name)

    async def top_movers(
        self, scope: Scope, window: TimeWindow, baseline: TimeWindow, limit: int = 10
    ) -> list[Mover]:
        return []


class FakeTracesProvider:
    name = "fake-traces"
    capabilities = frozenset[str]()

    async def get_trace(self, trace_id: str) -> TraceSummary:
        return TraceSummary(
            trace_id=trace_id, root_service="s", duration_ms=1, spans=[], source=self.name
        )

    async def errors(self, service: str, window: TimeWindow, limit: int = 20) -> list[ErrorGroup]:
        return []


class FakeChangesProvider:
    name = "fake-changes"
    capabilities = frozenset[str]()

    async def recent_deploys(self, service: str | None, window: TimeWindow) -> list[ChangeEvent]:
        return []

    async def diff_summary(self, change_id: str) -> DiffSummary:
        return DiffSummary(change_id=change_id, commits=[], files=[], source=self.name)

    async def config_changes(self, service: str | None, window: TimeWindow) -> list[ChangeEvent]:
        return []
