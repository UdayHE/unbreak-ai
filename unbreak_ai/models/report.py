"""The triage report (overview.md, Triage report) and its JSON Schema export."""

from typing import Any, Literal

from pydantic import Field, model_validator

from unbreak_ai.models.common import Model, Severity, UTCDateTime

Category = Literal["deploy", "config", "dependency", "resource", "traffic", "code", "unknown"]
Confidence = Literal["high", "medium", "low"]
ConfidenceReason = Literal["limit_reached", "conflicting_evidence", "insufficient_data"]
EvidenceSource = Literal["logs", "metrics", "traces", "changes"]
TimelineSource = Literal["logs", "metrics", "traces", "changes", "alert"]


class ReportWindow(Model):
    from_: UTCDateTime = Field(alias="from")
    to: UTCDateTime


class Impact(Model):
    services: list[str]
    user_facing: bool
    severity: Severity


class Timing(Model):
    alert_fired_at: UTCDateTime
    impact_started_at: UTCDateTime
    impact_ended_at: UTCDateTime | None
    peak_at: UTCDateTime | None
    detection_lag_s: int = Field(ge=0)
    investigation_window: ReportWindow
    report_generated_at: UTCDateTime


class TimelineEntry(Model):
    at: UTCDateTime
    event: str
    source: TimelineSource
    link: str | None


class RootCause(Model):
    category: Category
    description: str
    confidence: Confidence
    confidence_reason: ConfidenceReason | None = None
    suspected_change_id: str | None = None
    onset_relative_to_change_s: int | None = None

    @model_validator(mode="after")
    def _low_needs_reason(self) -> "RootCause":
        if self.confidence == "low" and self.confidence_reason is None:
            raise ValueError("confidence_reason is required when confidence is low")
        return self


class Evidence(Model):
    source: EvidenceSource
    claim: str
    ref: str
    observed_at: UTCDateTime
    window: ReportWindow
    link: str | None


class RuledOut(Model):
    hypothesis: str
    reason: str


class Stats(Model):
    model: str
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    duration_s: float = Field(ge=0)


class Report(Model):
    schema_version: Literal["1.0"] = "1.0"
    incident_id: str
    alert_ids: list[str]
    summary: str
    impact: Impact
    timing: Timing
    timeline: list[TimelineEntry]
    root_cause: RootCause
    evidence: list[Evidence]
    ruled_out: list[RuledOut]
    suggested_next_steps: list[str]
    stats: Stats

    @model_validator(mode="after")
    def _timeline_rules(self) -> "Report":
        times = [entry.at for entry in self.timeline]
        if times != sorted(times):
            raise ValueError("timeline must be sorted oldest first")
        if not any(entry.source == "alert" for entry in self.timeline):
            raise ValueError("timeline must include the alert itself")
        return self


def export_report_json_schema() -> dict[str, Any]:
    """JSON Schema for ``submit_report`` and for notifiers and evals that consume reports."""
    return Report.model_json_schema()
