from pathlib import Path
from typing import Any

import pytest
import yaml

from unbreak_ai.config.loader import UnbreakAIConfigError, load_config
from unbreak_ai.config.schema import Severity

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config.example.yaml"

ENV = {
    "ALERTMANAGER_TOKEN": "am-token-value",
    "ELASTICSEARCH_URL": "https://es.example.com",
    "ELASTICSEARCH_API_KEY": "es-key-value",
    "PROMETHEUS_URL": "https://prom.example.com",
    "GITHUB_TOKEN": "gh-token-value",
    "SLACK_BOT_TOKEN": "slack-token-value",
    "SMTP_URL": "smtp://user:smtp-pass-value@mail.example.com",
    "REDIS_URL": "redis://redis:6379/0",
    "DATABASE_URL": "postgresql://u:db-pass-value@db/unbreak",
}


def _base() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(EXAMPLE.read_text())
    return data


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def _error(tmp_path: Path, data: dict[str, Any], env: dict[str, str] | None = None) -> str:
    with pytest.raises(UnbreakAIConfigError) as exc:
        load_config(_write(tmp_path, data), env=ENV if env is None else env)
    return str(exc.value)


@pytest.mark.req("REQ-PRV-01")
def test_example_config_is_valid_with_defaults() -> None:
    cfg = load_config(EXAMPLE, env=ENV)
    assert cfg.providers.logs[0].type == "elasticsearch"
    assert [m.type for m in cfg.providers.metrics] == ["elastic_apm", "prometheus"]
    assert cfg.providers.logs[0].max_qps == 5
    assert cfg.notifiers[0].routing.min_severity is Severity.WARNING
    assert cfg.notifiers[1].routing.min_severity is Severity.CRITICAL
    assert cfg.notifiers[0].display_timezone == "UTC"
    assert cfg.agent.limits.max_tool_calls == 15
    assert cfg.agent.limits.max_input_tokens == 150000
    assert cfg.agent.limits.timeout_s == 240
    assert cfg.agent.daily_budget_usd == 25
    assert cfg.agent.prompt_caching is True
    assert cfg.incidents.grouping_window_s == 300
    assert cfg.incidents.workers == 5
    assert cfg.incidents.dependency_map == "apm"
    assert cfg.incidents.ignore.min_severity is Severity.INFO
    assert cfg.incidents.ignore.flappers == []
    assert len(cfg.redaction.patterns) == 3
    assert cfg.retention_days == 30


@pytest.mark.req("REQ-PRV-01")
def test_dependency_map_defaults_to_none_without_traces_provider(tmp_path: Path) -> None:
    data = _base()
    del data["providers"]["traces"]
    cfg = load_config(_write(tmp_path, data), env=ENV)
    assert cfg.incidents.dependency_map == "none"


@pytest.mark.req("REQ-PRV-01")
def test_unknown_provider_type_fails_and_lists_allowed(tmp_path: Path) -> None:
    data = _base()
    data["providers"]["logs"][0]["type"] = "splunk"
    message = _error(tmp_path, data)
    assert "providers.logs.0" in message
    assert "elasticsearch" in message


@pytest.mark.req("REQ-PRV-01")
def test_unknown_notifier_type_fails(tmp_path: Path) -> None:
    data = _base()
    data["notifiers"][0]["type"] = "pagerduty"
    assert "notifiers.0" in _error(tmp_path, data)


@pytest.mark.req("REQ-PRV-01")
def test_missing_required_setting_fails_with_path(tmp_path: Path) -> None:
    data = _base()
    del data["providers"]["metrics"][1]["url"]
    del data["agent"]["model"]
    message = _error(tmp_path, data)
    assert "providers.metrics.1" in message
    assert "agent.model" in message


@pytest.mark.req("REQ-PRV-01")
def test_logs_provider_and_notifier_are_required(tmp_path: Path) -> None:
    data = _base()
    data["providers"]["logs"] = []
    data["notifiers"] = []
    message = _error(tmp_path, data)
    assert "providers.logs" in message
    assert "notifiers" in message


@pytest.mark.req("REQ-PRV-01")
def test_unknown_key_fails(tmp_path: Path) -> None:
    data = _base()
    data["retention_dayz"] = 3
    assert "retention_dayz" in _error(tmp_path, data)


@pytest.mark.req("REQ-PRV-01")
def test_invalid_timezone_and_regex_fail(tmp_path: Path) -> None:
    data = _base()
    data["notifiers"][0]["display_timezone"] = "Mars/Olympus"
    data["redaction"] = {"patterns": ["(unclosed"]}
    message = _error(tmp_path, data)
    assert "notifiers.0" in message
    assert "redaction.patterns" in message and "item 0" in message


@pytest.mark.req("REQ-PRV-01")
def test_unset_env_var_fails_naming_var_and_path(tmp_path: Path) -> None:
    env = {k: v for k, v in ENV.items() if k != "PROMETHEUS_URL"}
    message = _error(tmp_path, _base(), env=env)
    assert "PROMETHEUS_URL" in message
    assert "providers.metrics.1.url" in message


@pytest.mark.req("REQ-PRV-01")
def test_env_default_allowed_for_non_secret(tmp_path: Path) -> None:
    data = _base()
    data["providers"]["metrics"][1]["url"] = "${PROMETHEUS_URL:-http://localhost:9090}"
    env = {k: v for k, v in ENV.items() if k != "PROMETHEUS_URL"}
    cfg = load_config(_write(tmp_path, data), env=env)
    assert cfg.providers.metrics[1].type == "prometheus"
    assert cfg.providers.metrics[1].url == "http://localhost:9090"


@pytest.mark.req("NFR-09")
def test_secret_is_read_from_env_and_hidden(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, _base()), env=ENV)
    assert cfg.redis_url.get_secret_value() == ENV["REDIS_URL"]
    assert cfg.alert_source.auth.get_secret_value() == "am-token-value"
    assert "am-token-value" not in repr(cfg)
    assert "es-key-value" not in cfg.model_dump_json()


@pytest.mark.req("NFR-09")
def test_inline_secret_is_rejected_without_leaking(tmp_path: Path) -> None:
    data = _base()
    data["redis_url"] = "redis://:inline-secret-value@redis/0"
    message = _error(tmp_path, data)
    assert "redis_url" in message
    assert "inline-secret-value" not in message


@pytest.mark.req("NFR-09")
def test_defaulted_secret_is_rejected_without_leaking(tmp_path: Path) -> None:
    data = _base()
    data["database_url"] = "${DATABASE_URL:-postgresql://u:fallback-secret-value@db/x}"
    message = _error(tmp_path, data)
    assert "database_url" in message
    assert "fallback-secret-value" not in message


@pytest.mark.req("NFR-09")
def test_malformed_secret_value_does_not_appear_in_error(tmp_path: Path) -> None:
    data = _base()
    data["alert_source"]["auth"] = {"token": "malformed-secret-value"}
    message = _error(tmp_path, data)
    assert "alert_source.auth" in message
    assert "malformed-secret-value" not in message


@pytest.mark.req("NFR-09")
def test_secret_from_env_with_bad_value_type_does_not_leak(tmp_path: Path) -> None:
    data = _base()
    data["providers"]["changes"][0]["repos"] = "org/checkout"
    message = _error(tmp_path, data)
    assert "gh-token-value" not in message


@pytest.mark.req("REQ-PRV-01")
def test_config_path_from_env_variable(tmp_path: Path) -> None:
    path = _write(tmp_path, _base())
    cfg = load_config(env={**ENV, "UNBREAK_AI_CONFIG": str(path)})
    assert cfg.retention_days == 30


@pytest.mark.req("REQ-PRV-01")
def test_missing_config_path_fails() -> None:
    with pytest.raises(UnbreakAIConfigError, match="UNBREAK_AI_CONFIG"):
        load_config(env={})


@pytest.mark.req("REQ-PRV-01")
def test_unreadable_or_malformed_file_fails(tmp_path: Path) -> None:
    with pytest.raises(UnbreakAIConfigError, match="cannot read"):
        load_config(tmp_path / "missing.yaml", env=ENV)
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed")
    with pytest.raises(UnbreakAIConfigError, match="not valid YAML"):
        load_config(bad, env=ENV)
    bad.write_text("- just\n- a list\n")
    with pytest.raises(UnbreakAIConfigError, match="mapping"):
        load_config(bad, env=ENV)
