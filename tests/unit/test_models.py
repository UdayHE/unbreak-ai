import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import BaseModel, ValidationError

from unbreak_ai.models.alert import Alert
from unbreak_ai.models.common import Scope, TimeWindow
from unbreak_ai.models.incident import DeliveryRef, Feedback, GroupingReason, Incident
from unbreak_ai.models.logs import (
    ErrorPattern,
    LogOverview,
    LogQuery,
    LogRecord,
    Page,
    truncate_message,
)
from unbreak_ai.models.report import Report, export_report_json_schema

ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def _example_report() -> dict[str, Any]:
    text = (ROOT / "specs" / "overview.md").read_text()
    section = text.split("**Example report.**", 1)[1]
    block = re.search(r"```json\n(.*?)\n```", section, re.S)
    assert block, "overview.md has no example report"
    data: dict[str, Any] = json.loads(block.group(1))
    return data


def _alert(severity: str = "warning", alert_id: str = "a1") -> Alert:
    return Alert(
        id=alert_id,
        fingerprint="fp1",
        source="alertmanager",
        name="HighErrorRate",
        severity=severity,  # type: ignore[arg-type]
        service="checkout",
        namespace="prod",
        labels={"team": "payments"},
        annotations={"summary": "errors"},
        starts_at=T0,
        ends_at=None,
        status="firing",
        expr="rate(errors[5m]) > 0.05",
    )


def _log_record() -> LogRecord:
    return LogRecord(
        ref="r1",
        timestamp=T0,
        level="error",
        service="checkout",
        namespace="prod",
        pod="checkout-1",
        message="connection pool exhausted",
        trace_id="t1",
        source="elasticsearch",
        link="https://kibana.example.com/x",
    )


def _incident(**overrides: Any) -> Incident:
    fields: dict[str, Any] = {
        "id": "inc1",
        "state": "open",
        "severity": "critical",
        "alerts": [_alert("warning", "a1"), _alert("critical", "a2")],
        "grouping_reasons": [GroupingReason(alert_id="a2", rule="fingerprint", detail="same fp")],
        "created_at": T0,
        "updated_at": T0,
    }
    fields.update(overrides)
    return Incident(**fields)


def _roundtrip(model: BaseModel) -> None:
    dumped = model.model_dump(mode="json")
    again = type(model).model_validate(json.loads(json.dumps(dumped)))
    assert again == model


def _models() -> list[BaseModel]:
    window = TimeWindow(start=T0, end=T0 + timedelta(minutes=5))
    record = _log_record()
    return [
        window,
        Scope(service="checkout", region="ap-south-1"),
        _alert(),
        record,
        LogOverview.model_validate(
            {
                "histogram": [{"at": T0, "count": 3}],
                "top_levels": [{"name": "error", "count": 3}],
                "top_services": [{"name": "checkout", "count": 3}],
                "top_pods": [],
                "total": 3,
                "source": "elasticsearch",
                "link": None,
            }
        ),
        ErrorPattern(
            pattern="connection pool exhausted",
            count=4,
            first_seen=T0,
            last_seen=T0 + timedelta(minutes=1),
            services=["checkout"],
            sample_ref="r1",
            source="elasticsearch",
            link=None,
        ),
        LogQuery(level="error", text="pool"),
        Page[LogRecord](items=[record], next_cursor="c2"),
        _incident(
            report=Report.model_validate(_example_report()),
            deliveries=[
                DeliveryRef(
                    notifier="slack",
                    channel="#incidents",
                    message_id="m1",
                    thread_id=None,
                    delivered_at=T0,
                    status="delivered",
                )
            ],
            feedback=[Feedback(verdict="correct", by="oncall", at=T0, comment=None)],
        ),
        Report.model_validate(_example_report()),
    ]


@pytest.mark.req("REQ-PRV-03")
@pytest.mark.parametrize("model", _models(), ids=lambda m: type(m).__name__)
def test_round_trip(model: BaseModel) -> None:
    _roundtrip(model)


@pytest.mark.req("REQ-PRV-03")
def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        TimeWindow(start=datetime(2026, 10, 25, 9, 0), end=T0)
    with pytest.raises(ValidationError, match="timezone"):
        TimeWindow.model_validate({"start": "2026-10-25T09:00:00", "end": "2026-10-25T10:00:00Z"})


@pytest.mark.req("REQ-PRV-03")
def test_offsets_are_normalized_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    window = TimeWindow(
        start=datetime(2026, 10, 25, 14, 30, tzinfo=ist), end=T0 + timedelta(hours=1)
    )
    assert window.start == T0
    assert window.start.utcoffset() == timedelta(0)


@pytest.mark.req("REQ-PRV-03")
def test_window_must_not_end_before_it_starts() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(start=T0, end=T0 - timedelta(seconds=1))


@pytest.mark.req("REQ-PRV-03")
def test_log_level_is_lowercased_and_messages_truncate() -> None:
    record = _log_record().model_copy(update={"level": "ERROR"})
    assert LogRecord.model_validate(record.model_dump()).level == "error"
    assert truncate_message("x" * 600) == "x" * 499 + "…"
    assert truncate_message("short") == "short"
    assert len(_log_record().model_copy(update={"message": "x" * 8000}).message) == 8000


@pytest.mark.req("REQ-PRV-03")
def test_unknown_fields_and_enum_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Scope.model_validate({"service": "a", "bogus": 1})
    with pytest.raises(ValidationError):
        Alert.model_validate({**_alert().model_dump(), "severity": "fatal"})


@pytest.mark.req("REQ-PRV-03")
def test_incident_severity_is_highest_of_its_alerts() -> None:
    assert _incident().severity == "critical"
    with pytest.raises(ValidationError, match="highest"):
        _incident(severity="warning")


@pytest.mark.req("REQ-PRV-03")
def test_incident_report_is_optional_and_rule_is_an_enum() -> None:
    assert _incident().report is None
    with pytest.raises(ValidationError):
        GroupingReason.model_validate({"alert_id": "a", "rule": "magic", "detail": ""})
    for rule in ("fingerprint", "scope", "dependency"):
        GroupingReason.model_validate({"alert_id": "a", "rule": rule, "detail": ""})


# --- Report ---------------------------------------------------------------------------------


@pytest.mark.req("REQ-RPT-01")
def test_example_report_validates_against_exported_schema() -> None:
    jsonschema.validate(_example_report(), export_report_json_schema())


@pytest.mark.req("REQ-RPT-01")
def test_committed_schema_file_matches_the_model() -> None:
    committed = json.loads((ROOT / "specs" / "report.schema.json").read_text())
    assert committed == export_report_json_schema()


@pytest.mark.req("REQ-RPT-01")
def test_example_report_dumps_back_to_the_same_json() -> None:
    report = Report.model_validate(_example_report())
    assert report.model_dump(mode="json") == _example_report()


def _mutated(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    data = _example_report()
    change(data)
    return data


def _drop_summary(d: dict[str, Any]) -> None:
    del d["summary"]


def _bad_confidence(d: dict[str, Any]) -> None:
    d["root_cause"]["confidence"] = "certain"


def _bad_category(d: dict[str, Any]) -> None:
    d["root_cause"]["category"] = "cosmic-rays"


def _bad_evidence_source(d: dict[str, Any]) -> None:
    d["evidence"][0]["source"] = "alert"


def _bad_severity(d: dict[str, Any]) -> None:
    d["impact"]["severity"] = "fatal"


def _extra_field(d: dict[str, Any]) -> None:
    d["surprise"] = 1


@pytest.mark.req("REQ-RPT-01")
@pytest.mark.parametrize(
    "change",
    [
        _drop_summary,
        _bad_confidence,
        _bad_category,
        _bad_evidence_source,
        _bad_severity,
        _extra_field,
    ],
)
def test_invalid_reports_fail_schema_and_model(change: Callable[[dict[str, Any]], None]) -> None:
    data = _mutated(change)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, export_report_json_schema())
    with pytest.raises(ValidationError):
        Report.model_validate(data)


def _low_without_reason(d: dict[str, Any]) -> None:
    d["root_cause"]["confidence"] = "low"
    d["root_cause"]["confidence_reason"] = None


@pytest.mark.req("REQ-RPT-01")
def test_low_confidence_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="confidence_reason"):
        Report.model_validate(_mutated(_low_without_reason))

    data = _mutated(_low_without_reason)
    data["root_cause"]["confidence_reason"] = "insufficient_data"
    assert Report.model_validate(data).root_cause.confidence_reason == "insufficient_data"
    jsonschema.validate(data, export_report_json_schema())


@pytest.mark.req("REQ-RPT-01")
def test_confidence_reason_is_not_needed_above_low() -> None:
    data = _example_report()
    for level in ("high", "medium"):
        data["root_cause"]["confidence"] = level
        assert Report.model_validate(data).root_cause.confidence_reason is None


@pytest.mark.req("REQ-RPT-01")
def test_timeline_must_be_sorted_and_include_the_alert() -> None:
    data = _example_report()
    data["timeline"].reverse()
    with pytest.raises(ValidationError, match="oldest first"):
        Report.model_validate(data)

    data = _example_report()
    data["timeline"] = [e for e in data["timeline"] if e["source"] != "alert"]
    with pytest.raises(ValidationError, match="alert"):
        Report.model_validate(data)


@pytest.mark.req("REQ-RPT-01")
def test_report_timestamps_must_be_utc() -> None:
    data = _example_report()
    data["timing"]["alert_fired_at"] = "2026-10-25T09:14:00"
    with pytest.raises(ValidationError, match="timezone"):
        Report.model_validate(data)
