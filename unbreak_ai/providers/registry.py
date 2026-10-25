"""The known provider types per interface: explicit mappings, the single source of truth.

Adding a vendor means one new line here (plus its adapter file); factories are filled in by
the adapter tasks. ``None`` means the type is known but not implemented yet.
"""

from collections.abc import Mapping
from typing import Any

from unbreak_ai.config.registry import TypeEntry
from unbreak_ai.providers.base import (
    ChangesProvider,
    LogsProvider,
    MetricsProvider,
    TracesProvider,
)
from unbreak_ai.providers.changes.github import GitHubChangesSettings
from unbreak_ai.providers.logs.elasticsearch import ElasticsearchLogsSettings
from unbreak_ai.providers.metrics.elastic_apm import ElasticAPMMetricsSettings
from unbreak_ai.providers.metrics.prometheus import PrometheusMetricsSettings
from unbreak_ai.providers.traces.elastic_apm import ElasticAPMTracesSettings

LOGS_TYPES: Mapping[str, TypeEntry[Any, LogsProvider]] = {
    "elasticsearch": TypeEntry(ElasticsearchLogsSettings),
}
METRICS_TYPES: Mapping[str, TypeEntry[Any, MetricsProvider]] = {
    "elastic_apm": TypeEntry(ElasticAPMMetricsSettings),
    "prometheus": TypeEntry(PrometheusMetricsSettings),
}
TRACES_TYPES: Mapping[str, TypeEntry[Any, TracesProvider]] = {
    "elastic_apm": TypeEntry(ElasticAPMTracesSettings),
}
CHANGES_TYPES: Mapping[str, TypeEntry[Any, ChangesProvider]] = {
    "github": TypeEntry(GitHubChangesSettings),
}
