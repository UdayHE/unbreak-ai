"""Composition root: loads and validates the config through the registries, then builds providers.

Nothing imports this module; it sits above ``config``, ``providers`` and ``notifiers``.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from unbreak_ai.config.loader import AppConfig, load_config
from unbreak_ai.config.registry import Registries, TypeRegistry
from unbreak_ai.notifiers.registry import NOTIFIER_TYPES
from unbreak_ai.providers.base import (
    ChangesProvider,
    LogsProvider,
    MetricsProvider,
    TracesProvider,
)
from unbreak_ai.providers.registry import CHANGES_TYPES, LOGS_TYPES, METRICS_TYPES, TRACES_TYPES


def default_registries() -> Registries:
    """Fresh registries built from copies of the explicit mappings, so tests cannot leak."""
    return Registries(
        logs=TypeRegistry("logs provider", LOGS_TYPES, LogsProvider),
        metrics=TypeRegistry("metrics provider", METRICS_TYPES, MetricsProvider),
        traces=TypeRegistry("traces provider", TRACES_TYPES, TracesProvider),
        changes=TypeRegistry("changes provider", CHANGES_TYPES, ChangesProvider),
        notifiers=TypeRegistry("notifier", NOTIFIER_TYPES),
    )


def load_app_config(
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    registries: Registries | None = None,
) -> AppConfig:
    """Load the config and validate every entry through the registries, before anything runs.

    Raises one ``UnbreakAIConfigError`` listing every problem with its full key path.
    """
    return load_config(path, os.environ if env is None else env, registries or default_registries())


@dataclass(frozen=True)
class BuiltProviders:
    logs: list[LogsProvider]
    metrics: list[MetricsProvider]
    traces: list[TracesProvider]
    changes: list[ChangesProvider]


def build_providers(app: AppConfig, registries: Registries | None = None) -> BuiltProviders:
    registries = registries or default_registries()
    return BuiltProviders(
        logs=[registries.logs.build(s) for s in app.providers.logs],
        metrics=[registries.metrics.build(s) for s in app.providers.metrics],
        traces=[registries.traces.build(s) for s in app.providers.traces],
        changes=[registries.changes.build(s) for s in app.providers.changes],
    )
