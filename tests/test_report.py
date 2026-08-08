from it_audit.catalog import QUESTIONS
from it_audit.models import CompanyProfile
from it_audit.report import render_html_report
from it_audit.scoring import calculate_result


def test_report_is_utf8_printable_and_escapes_user_input() -> None:
    profile = CompanyProfile(
        '<script>alert("x")</script> Альфа',
        "Транспорт & логистика",
        "101–250",
    )
    result = calculate_result(
        profile,
        {question.id: 2 for question in QUESTIONS},
        created_at="2026-08-08T12:00:00+00:00",
    )

    report = render_html_report(result)

    assert '<meta charset="utf-8">' in report
    assert "@media print" in report
    assert "&lt;script&gt;" in report
    assert '<script>alert("x")</script>' not in report
    assert "Транспорт &amp; логистика" in report
    assert "План 30 / 60 / 90 дней" in report
    assert f"Версия анкеты: {result.questionnaire_version}" in report
    assert f"Версия приложения: {result.app_version}" in report
