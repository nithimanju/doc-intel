"""Value objects for evaluation catalog and run tables."""

from __future__ import annotations

from dataclasses import dataclass

from src.vo.catalog_vo import QuestionType, Status
from src.vo.index_vo import IndexVersion


@dataclass
class EvalType:
    name: str
    created_by: str
    description: str | None = None
    eval_type_id: int | None = None


@dataclass
class EvalRecord:
    metric_name: str
    created_by: str
    description: str | None = None
    eval_record_id: int | None = None


@dataclass
class EvalRun:
    index_version: IndexVersion
    eval_record: EvalRecord
    metric_value: float
    question_type: QuestionType
    status: Status
    created_by: str
