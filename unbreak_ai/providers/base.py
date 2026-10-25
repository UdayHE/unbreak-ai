"""Provider Protocols, errors and capabilities (design.md, Provider interfaces).

Adapters contain only vendor-specific querying and mapping. Every returned model carries
``source`` and ``link``.
"""

from typing import Protocol, runtime_checkable

from unbreak_ai.models.alert import Alert
from unbreak_ai.models.changes import ChangeEvent, DiffSummary
from unbreak_ai.models.common import Scope, TimeWindow
from unbreak_ai.models.logs import ErrorPattern, LogOverview, LogQuery, LogRecord, Page
from unbreak_ai.models.metrics import Mover, Series, ServiceHealth
from unbreak_ai.models.traces import ErrorGroup, TraceSummary

# Well-known capability names; a provider declares the ones it supports (REQ-PRV-04).
PATTERN_AGGREGATION = "pattern_aggregation"
TRACES = "traces"


class UnbreakAIProviderError(Exception):
    """Base class of every error a provider may raise."""


class ProviderTimeout(UnbreakAIProviderError):
    pass


class ProviderUnavailable(UnbreakAIProviderError):
    pass


class ProviderError(UnbreakAIProviderError):
    pass


class NotSupported(UnbreakAIProviderError):
    def __init__(self, provider: str, capability: str) -> None:
        self.provider = provider
        self.capability = capability
        super().__init__(f"Not supported by {provider}")


@runtime_checkable
class Provider(Protocol):
    name: str  # e.g. "elasticsearch", "prometheus"
    capabilities: frozenset[str]  # e.g. {"pattern_aggregation", "traces"}


def require_capability(provider: Provider, capability: str) -> None:
    if capability not in provider.capabilities:
        raise NotSupported(provider.name, capability)


@runtime_checkable
class LogsProvider(Provider, Protocol):
    async def overview(self, scope: Scope, window: TimeWindow) -> LogOverview: ...

    async def error_patterns(
        self, scope: Scope, window: TimeWindow, limit: int = 20
    ) -> list[ErrorPattern]: ...

    async def search(
        self,
        scope: Scope,
        window: TimeWindow,
        query: LogQuery,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Page[LogRecord]: ...

    async def get(self, ref: str) -> LogRecord: ...

    async def context(self, ref: str, before: int = 20, after: int = 20) -> list[LogRecord]: ...


@runtime_checkable
class MetricsProvider(Provider, Protocol):
    async def service_health(
        self, service: str, window: TimeWindow, baseline: TimeWindow
    ) -> ServiceHealth: ...

    async def alert_context(self, alert: Alert, window: TimeWindow) -> Series: ...

    async def top_movers(
        self, scope: Scope, window: TimeWindow, baseline: TimeWindow, limit: int = 10
    ) -> list[Mover]: ...


@runtime_checkable
class TracesProvider(Provider, Protocol):
    async def get_trace(self, trace_id: str) -> TraceSummary: ...

    async def errors(
        self, service: str, window: TimeWindow, limit: int = 20
    ) -> list[ErrorGroup]: ...


@runtime_checkable
class ChangesProvider(Provider, Protocol):
    async def recent_deploys(
        self, service: str | None, window: TimeWindow
    ) -> list[ChangeEvent]: ...

    async def diff_summary(self, change_id: str) -> DiffSummary: ...

    async def config_changes(
        self, service: str | None, window: TimeWindow
    ) -> list[ChangeEvent]: ...
