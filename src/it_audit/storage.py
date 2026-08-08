"""Локальное SQLite-хранилище завершённых аудитов."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from it_audit.models import (
    AuditResult,
    AuditSummary,
    CompanyProfile,
    RiskItem,
    RoadmapItem,
)

DEFAULT_DB_PATH = Path("data") / "it_audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    employee_range TEXT NOT NULL,
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    maturity TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    roadmap_json TEXT NOT NULL
)
"""


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    """Разрешает путь из аргумента, окружения или локального значения по умолчанию."""

    if db_path is not None:
        return Path(db_path)
    return Path(os.environ.get("IT_AUDIT_DB_PATH", DEFAULT_DB_PATH))


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 3000")
    return connection


def init_db(db_path: str | Path | None = None) -> None:
    """Создаёт локальную таблицу при первом запуске."""

    with _connect(db_path) as connection:
        connection.execute(SCHEMA)


def save_audit(result: AuditResult, db_path: str | Path | None = None) -> bool:
    """Сохраняет аудит один раз; возвращает False, если UUID уже существовал."""

    init_db(db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO audits (
                id, created_at, company_name, industry, employee_range,
                overall_score, maturity, answers_json, scores_json,
                risks_json, roadmap_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.id,
                result.created_at,
                result.profile.name,
                result.profile.industry,
                result.profile.employee_range,
                result.overall_score,
                result.maturity,
                json.dumps(result.answers, ensure_ascii=False, sort_keys=True),
                json.dumps(result.scores, ensure_ascii=False, sort_keys=True),
                json.dumps([risk.to_dict() for risk in result.risks], ensure_ascii=False),
                json.dumps([item.to_dict() for item in result.roadmap], ensure_ascii=False),
            ),
        )
        return cursor.rowcount == 1


def list_audits(db_path: str | Path | None = None) -> list[AuditSummary]:
    """Возвращает историю от новых аудитов к старым."""

    init_db(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, company_name, industry, overall_score, maturity
            FROM audits
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [
        AuditSummary(
            id=row["id"],
            created_at=row["created_at"],
            company_name=row["company_name"],
            industry=row["industry"],
            overall_score=row["overall_score"],
            maturity=row["maturity"],
        )
        for row in rows
    ]


def get_audit(audit_id: str, db_path: str | Path | None = None) -> AuditResult | None:
    """Загружает полный неизменяемый снимок результата по UUID."""

    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM audits WHERE id = ?",
            (audit_id,),
        ).fetchone()
    if row is None:
        return None

    return AuditResult(
        id=row["id"],
        created_at=row["created_at"],
        profile=CompanyProfile(
            name=row["company_name"],
            industry=row["industry"],
            employee_range=row["employee_range"],
        ),
        answers={key: int(value) for key, value in json.loads(row["answers_json"]).items()},
        scores={key: int(value) for key, value in json.loads(row["scores_json"]).items()},
        overall_score=row["overall_score"],
        maturity=row["maturity"],
        risks=tuple(RiskItem.from_dict(item) for item in json.loads(row["risks_json"])),
        roadmap=tuple(
            RoadmapItem.from_dict(item) for item in json.loads(row["roadmap_json"])
        ),
    )

