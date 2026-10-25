"""Shared building blocks: UTC datetimes, the strict base model, TimeWindow, Scope, severity."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_to_utc)]

Severity = Literal["critical", "warning", "info"]
SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


class Model(BaseModel):
    """Base for every model: unknown keys are errors and aliases are used when serializing."""

    model_config = ConfigDict(extra="forbid", serialize_by_alias=True, populate_by_name=True)


class TimeWindow(Model):
    start: UTCDateTime
    end: UTCDateTime

    @model_validator(mode="after")
    def _ordered(self) -> "TimeWindow":
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self


class Scope(Model):
    service: str | None = None
    namespace: str | None = None
    region: str | None = None
    environment: str | None = None
