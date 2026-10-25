"""Settings schema: one Pydantic model for the whole YAML config (design.md, Config schema)."""

import re
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from unbreak_ai.models.common import Severity

Secret = Annotated[SecretStr, Field(min_length=1)]

DEFAULT_REDACTION_PATTERNS = [
    r"[\w.+-]+@[\w-]+\.[\w.-]+",
    r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+",
    r"AKIA[0-9A-Z]{16}",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlertSourceConfig(StrictModel):
    type: Literal["alertmanager"] = "alertmanager"
    auth: Secret


class ProviderSettings(StrictModel):
    """Base for every provider's settings model; the concrete model lives next to its adapter."""

    type: str
    max_qps: float = Field(default=5, gt=0)


class Routing(StrictModel):
    min_severity: Severity = "warning"
    services: list[str] | None = None  # None means all services


class NotifierSettings(StrictModel):
    """Base for every notifier's settings model; the concrete model lives next to its adapter."""

    type: str
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


# Provider and notifier entries stay raw here: the registries own the known types and validate
# each entry against its settings model (see config/registry.py and startup.py).
# They hold resolved ${VAR} values as plain strings, so they are hidden from repr and dumps.
RawEntry = dict[str, Any]


class ProvidersConfig(StrictModel):
    logs: list[RawEntry] = Field(min_length=1, repr=False, exclude=True)
    metrics: list[RawEntry] = Field(default=[], repr=False, exclude=True)
    traces: list[RawEntry] = Field(default=[], repr=False, exclude=True)
    changes: list[RawEntry] = Field(default=[], repr=False, exclude=True)


class AgentLimits(StrictModel):
    max_tool_calls: int = Field(default=15, gt=0)
    max_input_tokens: int = Field(default=150000, gt=0)
    timeout_s: int = Field(default=240, gt=0)


class AgentConfig(StrictModel):
    model: str
    limits: AgentLimits = AgentLimits()
    daily_budget_usd: float = Field(default=25, ge=0)
    prompt_caching: bool = True


class IgnoreRules(StrictModel):
    min_severity: Severity = "info"
    flappers: list[str] = []


class IncidentsConfig(StrictModel):
    grouping_window_s: int = Field(default=300, gt=0)
    workers: int = Field(default=5, gt=0)
    # None means "apm if a traces provider exists, else none"; resolved by UnbreakAIConfig.
    dependency_map: Literal["apm", "file", "none"] | None = None
    ignore: IgnoreRules = IgnoreRules()


class RedactionConfig(StrictModel):
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


class UnbreakAIConfig(StrictModel):
    alert_source: AlertSourceConfig
    providers: ProvidersConfig
    notifiers: list[RawEntry] = Field(min_length=1, repr=False, exclude=True)
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
