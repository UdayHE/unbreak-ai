import asyncio
from datetime import timedelta

import pytest

from tests.fakes import NOW, FakeClock, FakeLogsProvider, FakeLogsSettings
from unbreak_ai.config.schema import DEFAULT_REDACTION_PATTERNS
from unbreak_ai.models.common import Scope, TimeWindow
from unbreak_ai.models.logs import LogOverview, LogQuery, LogRecord, Page
from unbreak_ai.providers.base import NotSupported, ProviderError, ProviderUnavailable
from unbreak_ai.providers.middleware.breaker import CircuitBreaker
from unbreak_ai.providers.middleware.redact import Redactor
from unbreak_ai.providers.middleware.state import InMemoryState, MiddlewareState
from unbreak_ai.providers.middleware.wrap import wrap_provider

SCOPE = Scope()
WINDOW = TimeWindow(start=NOW, end=NOW + timedelta(minutes=5))


class ScriptedLogs(FakeLogsProvider):
    """Counts calls; raises ``fail`` while set; returns ``message`` as the record text."""

    def __init__(self, message: str = "ok") -> None:
        super().__init__(FakeLogsSettings(type="fake", greeting=message))
        self.calls = 0
        self.fail: Exception | None = None
        self.delay = 0.0

    async def get(self, ref: str) -> LogRecord:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise self.fail
        return await super().get(ref)

    async def overview(self, scope: Scope, window: TimeWindow) -> LogOverview:
        self.calls += 1
        return await super().overview(scope, window)


def make(
    provider: ScriptedLogs,
    clock: FakeClock,
    max_qps: float = 5,
    patterns: list[str] | None = None,
) -> ScriptedLogs:
    return wrap_provider(
        provider,
        max_qps,
        DEFAULT_REDACTION_PATTERNS if patterns is None else patterns,
        InMemoryState(clock),
        clock,
        clock.sleep,
    )


def window(start_s: int, end_s: int) -> TimeWindow:
    base = NOW.replace(second=0)
    return TimeWindow(start=base + timedelta(seconds=start_s), end=base + timedelta(seconds=end_s))


async def fail_n(wrapped: ScriptedLogs, n: int) -> None:
    for i in range(n):
        with pytest.raises(ProviderError):
            await wrapped.get(f"ref-{i}")  # distinct refs: no cache hits


def test_in_memory_state_satisfies_the_interface() -> None:
    state: MiddlewareState = InMemoryState()
    assert state is not None


# --- circuit breaker (REQ-PRV-07) ---


@pytest.mark.req("REQ-PRV-07")
async def test_breaker_opens_after_five_failures_and_fails_fast() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = ProviderError("boom")
    wrapped = make(provider, clock, max_qps=100)
    await fail_n(wrapped, 5)
    assert provider.calls == 5
    with pytest.raises(ProviderUnavailable):
        await wrapped.get("another")
    assert provider.calls == 5  # not queried while open


@pytest.mark.req("REQ-PRV-07")
async def test_failures_spread_over_more_than_60s_do_not_open() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = ProviderError("boom")
    wrapped = make(provider, clock, max_qps=100)
    for i in range(6):
        with pytest.raises(ProviderError):
            await wrapped.get(f"r{i}")
        clock.advance(15)  # 6 failures over 75 s: never 5 inside one 60 s window
    provider.fail = None
    assert (await wrapped.get("fine")).message == "ok"


@pytest.mark.req("REQ-PRV-07")
async def test_breaker_half_opens_after_30s_and_closes_on_success() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = ProviderError("boom")
    wrapped = make(provider, clock, max_qps=100)
    await fail_n(wrapped, 5)
    clock.advance(29)
    with pytest.raises(ProviderUnavailable):
        await wrapped.get("x")
    clock.advance(1)  # 30 s: half-open
    provider.fail = None
    assert (await wrapped.get("probe")).message == "ok"
    assert (await wrapped.get("after")).message == "ok"  # closed again
    provider.fail = ProviderError("boom")
    await fail_n(wrapped, 4)  # the failure count restarted: 4 more do not open it
    provider.fail = None
    assert (await wrapped.get("still-closed")).message == "ok"


@pytest.mark.req("REQ-PRV-07")
async def test_failed_probe_reopens_the_breaker() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = ProviderError("boom")
    wrapped = make(provider, clock, max_qps=100)
    await fail_n(wrapped, 5)
    clock.advance(30)
    with pytest.raises(ProviderError):
        await wrapped.get("probe")  # half-open probe reaches the provider and fails
    calls = provider.calls
    with pytest.raises(ProviderUnavailable):
        await wrapped.get("x")
    assert provider.calls == calls
    clock.advance(30)  # another cooldown: half-open again
    provider.fail = None
    assert (await wrapped.get("probe2")).message == "ok"


@pytest.mark.req("REQ-PRV-07")
async def test_only_one_probe_is_allowed_while_half_open() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("p", InMemoryState(clock), clock)

    async def boom() -> None:
        raise ProviderError("boom")

    for _ in range(5):
        with pytest.raises(ProviderError):
            await breaker.call(boom)
    clock.advance(30)
    release = asyncio.Event()

    async def slow_ok() -> str:
        await release.wait()
        return "ok"

    probe = asyncio.create_task(breaker.call(slow_ok))
    await asyncio.sleep(0)
    with pytest.raises(ProviderUnavailable):
        await breaker.call(slow_ok)
    release.set()
    assert await probe == "ok"


@pytest.mark.req("REQ-PRV-07")
async def test_not_supported_is_not_a_breaker_failure() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = NotSupported("fake", "traces")
    wrapped = make(provider, clock, max_qps=100)
    for i in range(10):
        with pytest.raises(NotSupported):
            await wrapped.get(f"r{i}")
    assert provider.calls == 10  # never opened


# --- cache (REQ-PRV-08) ---


@pytest.mark.req("REQ-PRV-08")
async def test_identical_query_is_a_cache_hit_until_60s() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock)
    await wrapped.overview(SCOPE, WINDOW)
    await wrapped.overview(SCOPE, WINDOW)
    assert provider.calls == 1
    clock.advance(59)
    await wrapped.overview(SCOPE, WINDOW)
    assert provider.calls == 1
    clock.advance(1)
    await wrapped.overview(SCOPE, WINDOW)
    assert provider.calls == 2


@pytest.mark.req("REQ-PRV-08")
async def test_windows_in_the_same_30s_boundaries_share_an_entry() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock)
    await wrapped.overview(SCOPE, window(3, 100))
    await wrapped.overview(SCOPE, window(25, 118))
    assert provider.calls == 1  # both round to [0, 120]
    await wrapped.overview(SCOPE, window(35, 118))
    assert provider.calls == 2  # start rounds to 30: a different key


@pytest.mark.req("REQ-PRV-08")
async def test_different_arguments_are_different_entries() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock)
    await wrapped.get("a")
    await wrapped.get("b")
    assert provider.calls == 2


@pytest.mark.req("REQ-PRV-08")
async def test_concurrent_identical_calls_share_one_query() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.delay = 0.01
    wrapped = make(provider, clock)
    results = await asyncio.gather(*(wrapped.get("same") for _ in range(5)))
    assert provider.calls == 1
    assert all(r.message == "ok" for r in results)


@pytest.mark.req("REQ-PRV-08")
async def test_errors_are_not_cached() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    provider.fail = ProviderError("boom")
    wrapped = make(provider, clock)
    with pytest.raises(ProviderError):
        await wrapped.get("a")
    provider.fail = None
    assert (await wrapped.get("a")).message == "ok"
    assert provider.calls == 2


@pytest.mark.req("REQ-PRV-08")
async def test_cache_hit_is_served_while_the_breaker_is_open() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock, max_qps=100)
    await wrapped.get("cached")
    provider.fail = ProviderError("boom")
    await fail_n(wrapped, 5)
    assert (await wrapped.get("cached")).message == "ok"  # no provider query needed


@pytest.mark.req("REQ-PRV-08")
async def test_wrapper_keeps_name_and_capabilities_and_passes_through_sync_attrs() -> None:
    provider = ScriptedLogs()
    wrapped = make(provider, FakeClock())
    assert wrapped.name == provider.name
    assert wrapped.capabilities == provider.capabilities
    assert wrapped.settings is provider.settings
    page = await wrapped.search(SCOPE, WINDOW, LogQuery())
    assert isinstance(page, Page)


# --- rate limit (REQ-PRV-09) ---


@pytest.mark.req("REQ-PRV-09")
async def test_rate_limit_allows_max_qps_then_waits() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock, max_qps=5)
    for i in range(5):
        await wrapped.get(f"r{i}")
    assert clock.slept == []
    await wrapped.get("r5")
    assert clock.slept == [pytest.approx(0.2)]


@pytest.mark.req("REQ-PRV-09")
async def test_rate_limit_tokens_refill_with_time() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock, max_qps=5)
    for i in range(5):
        await wrapped.get(f"r{i}")
    clock.advance(1)
    for i in range(5, 10):
        await wrapped.get(f"r{i}")
    assert clock.slept == []


@pytest.mark.req("REQ-PRV-09")
async def test_cache_hits_use_no_rate_limit_budget() -> None:
    clock, provider = FakeClock(), ScriptedLogs()
    wrapped = make(provider, clock, max_qps=1)
    for _ in range(10):
        await wrapped.get("same")
    assert clock.slept == []


# --- redaction (NFR-10) ---

SAMPLES = {
    "email": ("contact jane.doe+ops@example.co.uk now", "jane.doe+ops@example.co.uk"),
    "bearer": ("Authorization: Bearer abc.DEF-123_xyz~+/= end", "abc.DEF-123_xyz"),
    "aws-key": ("key=AKIAIOSFODNN7EXAMPLE end", "AKIAIOSFODNN7EXAMPLE"),
}


@pytest.mark.req("NFR-10")
@pytest.mark.parametrize(("sample", "secret"), list(SAMPLES.values()), ids=list(SAMPLES))
def test_each_default_pattern_is_redacted(sample: str, secret: str) -> None:
    out = Redactor(DEFAULT_REDACTION_PATTERNS).redact(sample)
    assert secret not in out
    assert "[REDACTED]" in out


@pytest.mark.req("NFR-10")
def test_redaction_reaches_nested_models_lists_and_dicts() -> None:
    redactor = Redactor(DEFAULT_REDACTION_PATTERNS)
    record = LogRecord(ref="r", timestamp=NOW, level="error", message="mail a@b.io", source="f")
    out = redactor.redact(Page[LogRecord](items=[record]))
    assert out.items[0].message == "mail [REDACTED]"
    assert record.message == "mail a@b.io"  # the original is untouched
    nested = redactor.redact({"k": ["a@b.io", ("AKIAIOSFODNN7EXAMPLE",)], "n": 3})
    assert nested == {"k": ["[REDACTED]", ("[REDACTED]",)], "n": 3}


@pytest.mark.req("NFR-10")
def test_custom_pattern_is_honored_and_clean_text_is_unchanged() -> None:
    redactor = Redactor([r"SSN-\d+"])
    assert redactor.redact("id SSN-123 x") == "id [REDACTED] x"
    assert redactor.redact("nothing here") == "nothing here"


@pytest.mark.req("NFR-10")
async def test_wrapped_provider_redacts_before_caching() -> None:
    clock, provider = FakeClock(), ScriptedLogs(message="mail a@b.io")
    wrapped = make(provider, clock)
    assert (await wrapped.get("x")).message == "mail [REDACTED]"
    assert (await wrapped.get("x")).message == "mail [REDACTED]"  # from the cache
    assert provider.calls == 1
