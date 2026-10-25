import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.fakes import FakeLogsProvider
from tests.unit.test_config import ENV, EXAMPLE
from unbreak_ai.config.errors import UnbreakAIConfigError
from unbreak_ai.config.registry import Registries, TypeEntry, TypeRegistry
from unbreak_ai.models.common import Scope, TimeWindow
from unbreak_ai.providers.base import LogsProvider
from unbreak_ai.providers.registry import LOGS_TYPES
from unbreak_ai.startup import build_providers, default_registries, load_app_config


def _data() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(EXAMPLE.read_text())
    return data


def _load(
    tmp_path: Path,
    data: dict[str, Any],
    registries: Registries | None = None,
    env: dict[str, str] | None = None,
) -> Any:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return load_app_config(path, ENV if env is None else env, registries)


def _error(tmp_path: Path, data: dict[str, Any], registries: Registries | None = None) -> str:
    with pytest.raises(UnbreakAIConfigError) as exc:
        _load(tmp_path, data, registries)
    return str(exc.value)


@pytest.mark.req("REQ-PRV-01")
def test_default_registries_are_the_single_list_of_known_types() -> None:
    registries = default_registries()
    assert registries.logs.types == ["elasticsearch"]
    assert registries.metrics.types == ["elastic_apm", "prometheus"]
    assert registries.traces.types == ["elastic_apm"]
    assert registries.changes.types == ["github"]
    assert registries.notifiers.types == ["email", "slack"]


@pytest.mark.req("REQ-PRV-01")
def test_example_config_loads_through_startup_with_typed_settings() -> None:
    app = load_app_config(EXAMPLE, ENV)
    assert app.providers.logs[0].type == "elasticsearch"
    assert [m.type for m in app.providers.metrics] == ["elastic_apm", "prometheus"]
    assert app.providers.changes[0].model_dump()["repos"] == ["org/checkout", "org/payments"]
    assert [n.type for n in app.notifiers] == ["slack", "email"]
    assert app.notifiers[1].routing.min_severity == "critical"


@pytest.mark.req("REQ-PRV-01")
def test_fake_provider_is_built_from_config(tmp_path: Path, fake_registries: Registries) -> None:
    data = _data()
    data["providers"] = {"logs": [{"type": "fake", "greeting": "from-config"}]}
    app = _load(tmp_path, data, fake_registries)
    providers = build_providers(app, fake_registries)
    (provider,) = providers.logs
    assert isinstance(provider, FakeLogsProvider)
    window = TimeWindow.model_validate(
        {"start": "2026-10-25T09:00:00Z", "end": "2026-10-25T09:05:00Z"}
    )
    record = asyncio.run(provider.get("r1"))
    assert record.message == "from-config"
    assert asyncio.run(provider.overview(Scope(), window)).source == "fake"


@pytest.mark.req("REQ-PRV-01")
def test_fake_type_is_unknown_without_the_fixture(tmp_path: Path) -> None:
    data = _data()
    data["providers"]["logs"] = [{"type": "fake"}]
    message = _error(tmp_path, data)
    assert "providers.logs.0.type" in message
    assert "unknown logs provider type 'fake'" in message
    assert "allowed: elasticsearch" in message


@pytest.mark.req("REQ-PRV-01")
def test_unknown_types_fail_at_startup_with_full_key_path(tmp_path: Path) -> None:
    data = _data()
    data["providers"]["metrics"][1]["type"] = "datadog"
    data["notifiers"][1]["type"] = "pagerduty"
    message = _error(tmp_path, data)
    assert "providers.metrics.1.type: unknown metrics provider type 'datadog'" in message
    assert "allowed: elastic_apm, prometheus" in message
    assert "notifiers.1.type: unknown notifier type 'pagerduty'; allowed: email, slack" in message


@pytest.mark.req("REQ-PRV-01")
def test_bad_provider_settings_report_every_problem_with_full_paths(tmp_path: Path) -> None:
    data = _data()
    del data["providers"]["changes"][0]["repos"]
    data["providers"]["logs"][0]["bogus"] = 1
    del data["notifiers"][0]["channel"]
    del data["agent"]["model"]
    message = _error(tmp_path, data)
    assert "providers.changes.0.repos" in message
    assert "providers.logs.0.bogus" in message
    assert "notifiers.0.channel" in message
    assert "agent.model" in message


@pytest.mark.req("REQ-PRV-01")
def test_known_type_without_an_adapter_fails_at_build(tmp_path: Path) -> None:
    app = _load(tmp_path, _data())
    with pytest.raises(UnbreakAIConfigError, match="'elasticsearch' is known but not implemented"):
        build_providers(app)


@pytest.mark.req("REQ-PRV-01")
def test_factory_result_must_match_the_protocol(
    tmp_path: Path, fake_registries: Registries
) -> None:
    registries = Registries(
        logs=TypeRegistry(
            "logs provider",
            {
                **LOGS_TYPES,
                "fake": TypeEntry(
                    fake_registries.logs._entries["fake"].settings, lambda s: object()
                ),
            },
            LogsProvider,
        ),
        metrics=fake_registries.metrics,
        traces=fake_registries.traces,
        changes=fake_registries.changes,
        notifiers=fake_registries.notifiers,
    )
    data = _data()
    data["providers"]["logs"] = [{"type": "fake"}]
    app = _load(tmp_path, data, registries)
    with pytest.raises(UnbreakAIConfigError, match="not a LogsProvider"):
        build_providers(app, registries)


# --- NFR-09: secrets found by type, across provider and notifier settings ---------------------


@pytest.mark.req("NFR-09")
def test_inline_provider_credential_is_rejected_without_leaking(tmp_path: Path) -> None:
    data = _data()
    data["providers"]["changes"][0]["token"] = "ghp_inlineSecretValue123"
    message = _error(tmp_path, data)
    assert "providers.changes.0.token" in message
    assert "ghp_inlineSecretValue123" not in message


@pytest.mark.req("NFR-09")
def test_inline_notifier_credential_is_rejected_without_leaking(tmp_path: Path) -> None:
    data = _data()
    data["notifiers"][0]["bot_token"] = "xoxb-inline-secret"
    message = _error(tmp_path, data)
    assert "notifiers.0.bot_token" in message
    assert "xoxb-inline-secret" not in message


@pytest.mark.req("NFR-09")
def test_defaulted_provider_credential_is_rejected(tmp_path: Path) -> None:
    data = _data()
    data["providers"]["logs"][0]["api_key"] = "${ELASTICSEARCH_API_KEY:-fallback-key-value}"
    message = _error(tmp_path, data)
    assert "providers.logs.0.api_key" in message
    assert "fallback-key-value" not in message


@pytest.mark.req("NFR-09")
def test_secret_in_a_nested_settings_model_is_found_by_type(
    tmp_path: Path, fake_registries: Registries
) -> None:
    env = {**ENV, "NESTED_TOKEN": "nested-token-value"}
    data = _data()
    data["providers"]["logs"] = [
        {"type": "fake", "credentials": {"token": "${NESTED_TOKEN}"}},
    ]
    app = _load(tmp_path, data, fake_registries, env)  # from env: accepted
    assert app.providers.logs[0].model_dump()["credentials"]["token"].get_secret_value() == (
        "nested-token-value"
    )

    data["providers"]["logs"] = [{"type": "fake", "credentials": {"token": "inline-nested-value"}}]
    with pytest.raises(UnbreakAIConfigError) as exc:
        _load(tmp_path, data, fake_registries, env)
    assert "providers.logs.0.credentials.token" in str(exc.value)
    assert "inline-nested-value" not in str(exc.value)


@pytest.mark.req("NFR-09")
def test_secret_inside_a_list_of_nested_models_is_found_by_type(
    tmp_path: Path, fake_registries: Registries
) -> None:
    data = _data()
    data["providers"]["logs"] = [
        {
            "type": "fake",
            "extra_tokens": [{"token": "${ELASTICSEARCH_API_KEY}"}, {"token": "inline-list-value"}],
        }
    ]
    with pytest.raises(UnbreakAIConfigError) as exc:
        _load(tmp_path, data, fake_registries)
    message = str(exc.value)
    assert "providers.logs.0.extra_tokens.1.token" in message
    assert "extra_tokens.0.token" not in message
    assert "inline-list-value" not in message


@pytest.mark.req("NFR-09")
def test_resolved_secrets_do_not_appear_in_repr_or_dump(tmp_path: Path) -> None:
    app = _load(tmp_path, _data())
    text = repr(app) + app.config.model_dump_json()
    non_secret = {"ELASTICSEARCH_URL", "PROMETHEUS_URL"}
    for name, value in ENV.items():
        if name not in non_secret:
            assert value not in text
