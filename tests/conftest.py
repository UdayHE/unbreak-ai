from collections.abc import Iterator

import pytest

from tests.fakes import FakeLogsProvider, FakeLogsSettings, FakeNotifierSettings
from unbreak_ai.config.registry import Registries, TypeEntry, TypeRegistry
from unbreak_ai.notifiers.registry import NOTIFIER_TYPES
from unbreak_ai.providers.base import LogsProvider
from unbreak_ai.providers.registry import LOGS_TYPES
from unbreak_ai.startup import default_registries


@pytest.fixture
def fake_registries() -> Iterator[Registries]:
    """Default registries plus a ``fake`` logs provider and notifier, scoped to one test.

    The default mappings are copied into fresh registries, so nothing global is mutated and
    nothing needs cleaning up; the final check proves the real mappings stayed untouched.
    """
    base = default_registries()
    yield Registries(
        logs=TypeRegistry(
            "logs provider",
            {**LOGS_TYPES, "fake": TypeEntry(FakeLogsSettings, FakeLogsProvider.from_settings)},
            LogsProvider,
        ),
        metrics=base.metrics,
        traces=base.traces,
        changes=base.changes,
        notifiers=TypeRegistry(
            "notifier", {**NOTIFIER_TYPES, "fake": TypeEntry(FakeNotifierSettings)}
        ),
    )
    assert "fake" not in LOGS_TYPES
    assert "fake" not in NOTIFIER_TYPES
