from typing import Literal

from pydantic import model_validator

from unbreak_ai.models.alert import Alert
from unbreak_ai.models.common import SEVERITY_RANK, Model, Severity, UTCDateTime
from unbreak_ai.models.report import Report


class GroupingReason(Model):
    """Why an alert joined an incident."""

    alert_id: str
    rule: Literal["fingerprint", "scope", "dependency"]
    detail: str


class DeliveryRef(Model):
    """Handle to a delivered report, used for follow-up updates."""

    notifier: str
    channel: str
    message_id: str
    thread_id: str | None = None
    delivered_at: UTCDateTime
    status: Literal["delivered", "failed"]


class Feedback(Model):
    verdict: Literal["correct", "incorrect"]
    by: str
    at: UTCDateTime
    comment: str | None = None


class Incident(Model):
    id: str
    state: Literal["open", "investigating", "reported", "resolved"]
    severity: Severity
    alerts: list[Alert]
    grouping_reasons: list[GroupingReason] = []
    created_at: UTCDateTime
    updated_at: UTCDateTime
    report: Report | None = None
    deliveries: list[DeliveryRef] = []
    feedback: list[Feedback] = []

    @model_validator(mode="after")
    def _severity_is_highest(self) -> "Incident":
        if self.alerts:
            highest = max((a.severity for a in self.alerts), key=SEVERITY_RANK.__getitem__)
            if self.severity != highest:
                raise ValueError(f"severity must be the highest of its alerts ({highest})")
        return self
