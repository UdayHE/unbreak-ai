from typing import Literal

from unbreak_ai.models.common import Model, Severity, UTCDateTime


class Alert(Model):
    """An alert normalized from an alert source in ``intake/``."""

    id: str
    fingerprint: str
    source: str
    name: str
    severity: Severity
    service: str | None = None
    namespace: str | None = None
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}
    starts_at: UTCDateTime
    ends_at: UTCDateTime | None = None
    status: Literal["firing", "resolved"]
    expr: str | None = None
