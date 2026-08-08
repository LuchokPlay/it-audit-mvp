from it_audit.catalog import QUESTIONS
from it_audit.models import CompanyProfile
from it_audit.scoring import calculate_result
from it_audit.storage import delete_audit, get_audit, list_audits, save_audit


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
