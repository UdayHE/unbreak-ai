"""Provisional (design.md, Data models): T-21 to T-25 may refine these through spec-fix commits."""

from typing import Literal

from pydantic import Field

from unbreak_ai.models.common import Model, UTCDateTime


class ChangeEvent(Model):
    id: str
    kind: Literal["deploy", "config"]
    service: str | None = None
    at: UTCDateTime
    author: str | None = None
    summary: str
    version: str | None = None
    source: str
    link: str | None = None


class Commit(Model):
    sha: str
    author: str | None = None
    message: str


class FileChange(Model):
    path: str
    additions: int
    deletions: int


class DiffSummary(Model):
    change_id: str
    commits: list[Commit]
    files: list[FileChange] = Field(max_length=30)
    source: str
    link: str | None = None
