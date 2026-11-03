"""Value objects for shared catalog tables."""

from __future__ import annotations

from dataclasses import dataclass


STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
STATUS_FAILURE = "FAILURE"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"


@dataclass
class Status:
    name: str
    created_by: str
    description: str | None = None
    status_id: int | None = None


@dataclass
class QuestionType:
    type_name: str
    created_by: str
    description: str | None = None
    question_type_id: int | None = None
