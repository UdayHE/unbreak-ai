import pytest

from tests.fakes import (
    FakeChangesProvider,
    FakeLogsProvider,
    FakeLogsSettings,
    FakeMetricsProvider,
    FakeTracesProvider,
)
from unbreak_ai.providers.base import (
    PATTERN_AGGREGATION,
    TRACES,
    ChangesProvider,
    LogsProvider,
    MetricsProvider,
    NotSupported,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    TracesProvider,
    UnbreakAIProviderError,
    require_capability,
)


@pytest.mark.req("REQ-PRV-04")
@pytest.mark.parametrize("error", [ProviderTimeout, ProviderUnavailable, ProviderError])
def test_provider_errors_share_one_base(error: type[UnbreakAIProviderError]) -> None:
    assert issubclass(error, UnbreakAIProviderError)


@pytest.mark.req("REQ-PRV-04")
def test_not_supported_names_the_provider() -> None:
    provider = FakeLogsProvider(FakeLogsSettings(type="fake"))
    require_capability(provider, PATTERN_AGGREGATION)  # supported: no error
    with pytest.raises(NotSupported) as exc:
        require_capability(provider, TRACES)
    assert isinstance(exc.value, UnbreakAIProviderError)
    assert str(exc.value) == "Not supported by fake"
    assert exc.value.capability == TRACES


@pytest.mark.req("REQ-PRV-03")
def test_fakes_satisfy_their_protocols() -> None:
    assert isinstance(FakeLogsProvider(FakeLogsSettings(type="fake")), LogsProvider)
    assert isinstance(FakeMetricsProvider(), MetricsProvider)
    assert isinstance(FakeTracesProvider(), TracesProvider)
    assert isinstance(FakeChangesProvider(), ChangesProvider)
    assert not isinstance(FakeMetricsProvider(), LogsProvider)
