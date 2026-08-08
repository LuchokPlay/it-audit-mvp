"""Типы данных приложения."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Category:
    key: str
    title: str


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str
    risk: str
    action: str


@dataclass(frozen=True)
class CompanyProfile:
    name: str
    industry: str
    employee_range: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CompanyProfile:
        return cls(
            name=str(value["name"]),
            industry=str(value["industry"]),
            employee_range=str(value["employee_range"]),
        )


@dataclass(frozen=True)
class RiskItem:
    question_id: str
    title: str
    severity: str
    horizon_days: int
    action: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RiskItem:
        return cls(
            question_id=str(value["question_id"]),
            title=str(value["title"]),
            severity=str(value["severity"]),
            horizon_days=int(value["horizon_days"]),
            action=str(value["action"]),
        )


@dataclass(frozen=True)
class RoadmapItem:
    horizon_days: int
    title: str
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, int | str | list[str]]:
        return {
            "horizon_days": self.horizon_days,
            "title": self.title,
            "actions": list(self.actions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RoadmapItem:
        return cls(
            horizon_days=int(value["horizon_days"]),
            title=str(value["title"]),
            actions=tuple(str(action) for action in value["actions"]),
        )


@dataclass(frozen=True)
class AuditResult:
    id: str
    created_at: str
    profile: CompanyProfile
    answers: dict[str, int]
    scores: dict[str, int]
    overall_score: int
    maturity: str
    risks: tuple[RiskItem, ...]
    roadmap: tuple[RoadmapItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "profile": self.profile.to_dict(),
            "answers": self.answers,
            "scores": self.scores,
            "overall_score": self.overall_score,
            "maturity": self.maturity,
            "risks": [risk.to_dict() for risk in self.risks],
            "roadmap": [item.to_dict() for item in self.roadmap],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AuditResult:
        return cls(
            id=str(value["id"]),
            created_at=str(value["created_at"]),
            profile=CompanyProfile.from_dict(value["profile"]),
            answers={str(key): int(score) for key, score in value["answers"].items()},
            scores={str(key): int(score) for key, score in value["scores"].items()},
            overall_score=int(value["overall_score"]),
            maturity=str(value["maturity"]),
            risks=tuple(RiskItem.from_dict(item) for item in value["risks"]),
            roadmap=tuple(RoadmapItem.from_dict(item) for item in value["roadmap"]),
        )


@dataclass(frozen=True)
class AuditSummary:
    id: str
    created_at: str
    company_name: str
    industry: str
    overall_score: int
    maturity: str

