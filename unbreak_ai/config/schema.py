"""Settings schema: one Pydantic model for the whole YAML config (design.md, Config schema)."""

import re
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Secret = Annotated[SecretStr, Field(min_length=1)]

DEFAULT_REDACTION_PATTERNS = [
    r"[\w.+-]+@[\w-]+\.[\w.-]+",
    r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+",
    r"AKIA[0-9A-Z]{16}",
]


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlertSourceConfig(_Model):
    type: Literal["alertmanager"] = "alertmanager"
    auth: Secret


class _ProviderBase(_Model):
    max_qps: float = Field(default=5, gt=0)


class ElasticsearchLogsConfig(_ProviderBase):
    type: Literal["elasticsearch"]
    url: str
    api_key: Secret
    regions: list[str] = []


class ElasticAPMMetricsConfig(_ProviderBase):
    type: Literal["elastic_apm"]
    url: str
    api_key: Secret


class PrometheusMetricsConfig(_ProviderBase):
    type: Literal["prometheus"]
    url: str
    auth: Secret | None = None


class ElasticAPMTracesConfig(_ProviderBase):
    type: Literal["elastic_apm"]
    url: str
    api_key: Secret


class GitHubChangesConfig(_ProviderBase):
    type: Literal["github"]
    token: Secret
    repos: list[str] = Field(min_length=1)
    config_paths: list[str] = []


# Single-member families are plain models; widen to a discriminated union when a second type lands.
LogsProviderConfig = ElasticsearchLogsConfig
MetricsProviderConfig = Annotated[
    ElasticAPMMetricsConfig | PrometheusMetricsConfig, Field(discriminator="type")
]
TracesProviderConfig = ElasticAPMTracesConfig
ChangesProviderConfig = GitHubChangesConfig


class ProvidersConfig(_Model):
    logs: list[LogsProviderConfig] = Field(min_length=1)
    metrics: list[MetricsProviderConfig] = []
    traces: list[TracesProviderConfig] = []
    changes: list[ChangesProviderConfig] = []


class Routing(_Model):
    min_severity: Severity = Severity.WARNING
    services: list[str] | None = None  # None means all services


class _NotifierBase(_Model):
    routing: Routing = Routing()
    display_timezone: str = "UTC"

    @field_validator("display_timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (KeyError, ValueError, OSError):
            raise ValueError("must be an IANA time zone name") from None
        return value


class SlackNotifierConfig(_NotifierBase):
    type: Literal["slack"]
    channel: str
    bot_token: Secret


class EmailNotifierConfig(_NotifierBase):
    type: Literal["email"]
    to: list[str] = Field(min_length=1)
    smtp_url: Secret


NotifierConfig = Annotated[SlackNotifierConfig | EmailNotifierConfig, Field(discriminator="type")]


class AgentLimits(_Model):
    max_tool_calls: int = Field(default=15, gt=0)
    max_input_tokens: int = Field(default=150000, gt=0)
    timeout_s: int = Field(default=240, gt=0)


class AgentConfig(_Model):
    model: str
    limits: AgentLimits = AgentLimits()
    daily_budget_usd: float = Field(default=25, ge=0)
    prompt_caching: bool = True


class IgnoreRules(_Model):
    min_severity: Severity = Severity.INFO
    flappers: list[str] = []


class IncidentsConfig(_Model):
    grouping_window_s: int = Field(default=300, gt=0)
    workers: int = Field(default=5, gt=0)
    # None means "apm if a traces provider exists, else none"; resolved by UnbreakAIConfig.
    dependency_map: Literal["apm", "file", "none"] | None = None
    ignore: IgnoreRules = IgnoreRules()


class RedactionConfig(_Model):
    patterns: list[str] = DEFAULT_REDACTION_PATTERNS

    @field_validator("patterns")
    @classmethod
    def _compile(cls, value: list[str]) -> list[str]:
        for index, pattern in enumerate(value):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"item {index} is not a valid regex: {exc.msg}") from None
        return value


class UnbreakAIConfig(_Model):
    alert_source: AlertSourceConfig
    providers: ProvidersConfig
    notifiers: list[NotifierConfig] = Field(min_length=1)
    agent: AgentConfig
    incidents: IncidentsConfig = IncidentsConfig()
    redaction: RedactionConfig = RedactionConfig()
    retention_days: int = Field(default=30, gt=0)
    redis_url: Secret
    database_url: Secret

    @model_validator(mode="after")
    def _resolve_dependency_map(self) -> "UnbreakAIConfig":
        if self.incidents.dependency_map is None:
            self.incidents.dependency_map = "apm" if self.providers.traces else "none"
        return self
