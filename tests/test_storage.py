import sqlite3

from it_audit.catalog import QUESTIONS
from it_audit.models import CompanyProfile
from it_audit.scoring import calculate_result
from it_audit.storage import delete_audit, get_audit, init_db, list_audits, save_audit


def make_result():
    profile = CompanyProfile("Альфа Логистика", "Транспорт и логистика", "101–250")
    answers = {question.id: 4 for question in QUESTIONS}
    return calculate_result(
        profile,
        answers,
        audit_id="91d4fbeb-ea7a-4dd0-9461-e67eb7fa65d9",
        created_at="2026-08-08T12:00:00+00:00",
    )


def test_storage_round_trip_and_duplicate_protection(tmp_path) -> None:
    database = tmp_path / "nested" / "audit.db"
    result = make_result()

    assert save_audit(result, database) is True
    assert save_audit(result, database) is False

    summaries = list_audits(database)
    restored = get_audit(result.id, database)

    assert len(summaries) == 1
    assert summaries[0].company_name == "Альфа Логистика"
    assert summaries[0].questionnaire_version == result.questionnaire_version
    assert summaries[0].app_version == result.app_version
    assert restored == result


def test_unknown_audit_returns_none(tmp_path) -> None:
    assert get_audit("missing", tmp_path / "audit.db") is None


def test_delete_audit_removes_only_existing_record(tmp_path) -> None:
    database = tmp_path / "audit.db"
    result = make_result()
    save_audit(result, database)

    assert delete_audit(result.id, database) is True
    assert delete_audit(result.id, database) is False
    assert get_audit(result.id, database) is None
    assert list_audits(database) == []


def test_init_db_adds_questionnaire_version_to_existing_database(tmp_path) -> None:
    database = tmp_path / "audit.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE audits (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                company_name TEXT NOT NULL,
                industry TEXT NOT NULL,
                employee_range TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                maturity TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                scores_json TEXT NOT NULL,
                risks_json TEXT NOT NULL,
                roadmap_json TEXT NOT NULL
            )
            """
        )

    init_db(database)

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(audits)")}
    assert "questionnaire_version" in columns
    assert "app_version" in columns
