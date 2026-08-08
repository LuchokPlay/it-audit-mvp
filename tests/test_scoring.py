import pytest

from it_audit.catalog import CATEGORIES, QUESTIONNAIRE_VERSION, QUESTIONS
from it_audit.models import CompanyProfile
from it_audit.scoring import NOT_APPLICABLE, build_risks, calculate_result, maturity_label
from it_audit.version import __version__

PROFILE = CompanyProfile("Альфа Логистика", "Транспорт и логистика", "101–250")


def answers_with(value: int) -> dict[str, int]:
    return {question.id: value for question in QUESTIONS}


def test_catalog_contains_four_questions_per_category() -> None:
    assert len(QUESTIONS) == 16
    for category in CATEGORIES:
        assert sum(question.category == category.key for question in QUESTIONS) == 4


@pytest.mark.parametrize(
    ("answer", "expected"),
    [(1, 0), (5, 100)],
)
def test_extreme_answers_normalize_to_expected_score(answer: int, expected: int) -> None:
    result = calculate_result(PROFILE, answers_with(answer))

    assert result.overall_score == expected
    assert result.context_score == expected
    assert set(result.scores.values()) == {expected}


def test_mixed_answers_are_scored_per_category() -> None:
    answers = answers_with(5)
    category_values = {
        "infrastructure": 1,
        "security": 2,
        "automation": 3,
        "management": 4,
    }
    for question in QUESTIONS:
        answers[question.id] = category_values[question.category]

    result = calculate_result(PROFILE, answers)

    assert result.scores == {
        "infrastructure": 0,
        "security": 25,
        "automation": 50,
        "management": 75,
    }
    assert result.overall_score == 38
    assert result.context_score == 34
    assert result.maturity == "Критический"
    assert result.questionnaire_version == QUESTIONNAIRE_VERSION
    assert result.app_version == __version__


def test_not_applicable_answers_are_excluded_from_category_average() -> None:
    answers = answers_with(5)
    infrastructure = [question for question in QUESTIONS if question.category == "infrastructure"]
    answers[infrastructure[0].id] = 1
    answers[infrastructure[1].id] = 5
    answers[infrastructure[2].id] = NOT_APPLICABLE
    answers[infrastructure[3].id] = NOT_APPLICABLE

    result = calculate_result(PROFILE, answers)

    assert result.scores["infrastructure"] == 50
    assert result.overall_score == 88


def test_category_with_only_not_applicable_answers_is_not_scored() -> None:
    answers = answers_with(5)
    for question in QUESTIONS:
        if question.category == "infrastructure":
            answers[question.id] = NOT_APPLICABLE

    result = calculate_result(PROFILE, answers)

    assert result.scores["infrastructure"] is None
    assert result.overall_score == 100


def test_audit_requires_at_least_one_applicable_answer() -> None:
    with pytest.raises(ValueError, match="хотя бы один применимый"):
        calculate_result(PROFILE, answers_with(NOT_APPLICABLE))


def test_not_applicable_answer_does_not_create_risk() -> None:
    answers = answers_with(5)
    answers[QUESTIONS[0].id] = NOT_APPLICABLE

    assert build_risks(answers) == ()


def test_context_changes_weighted_score_but_not_base_maturity() -> None:
    answers = answers_with(4)
    for question in QUESTIONS:
        if question.category == "security":
            answers[question.id] = 2
    finance = CompanyProfile("Банк", "Финансы", "101–250")
    manufacturing = CompanyProfile("Завод", "Производство", "101–250")

    first = calculate_result(finance, answers)
    second = calculate_result(manufacturing, answers)

    assert first.scores == second.scores
    assert first.overall_score == second.overall_score
    assert first.overall_score == 62
    assert first.context_score == 59
    assert second.context_score == 62
    assert first.risks != second.risks
    assert first.roadmap != second.roadmap


def test_employee_range_changes_context_weights() -> None:
    answers = answers_with(4)
    for question in QUESTIONS:
        if question.category == "management":
            answers[question.id] = 2

    small = calculate_result(CompanyProfile("А", "Ритейл", "1–50"), answers)
    enterprise = calculate_result(CompanyProfile("Б", "Ритейл", "Более 1000"), answers)

    assert small.overall_score == enterprise.overall_score
    assert small.context_score > enterprise.context_score
    assert small.category_weights != enterprise.category_weights


def test_missing_answer_is_rejected() -> None:
    answers = answers_with(4)
    answers.pop(QUESTIONS[0].id)

    with pytest.raises(ValueError, match="не заполнены"):
        calculate_result(PROFILE, answers)


def test_invalid_answer_is_rejected() -> None:
    answers = answers_with(4)
    answers[QUESTIONS[0].id] = 6

    with pytest.raises(ValueError, match="от 1 до 5"):
        calculate_result(PROFILE, answers)


def test_risks_are_sorted_and_limited_to_five() -> None:
    answers = answers_with(5)
    answers[QUESTIONS[0].id] = 2
    answers[QUESTIONS[1].id] = 1
    answers[QUESTIONS[2].id] = 3
    answers[QUESTIONS[3].id] = 1

    risks = build_risks(answers)

    assert len(risks) == 4
    assert [risk.question_id for risk in risks] == [
        QUESTIONS[1].id,
        QUESTIONS[3].id,
        QUESTIONS[0].id,
        QUESTIONS[2].id,
    ]
    assert [risk.horizon_days for risk in risks] == [30, 30, 60, 90]


def test_finance_profile_adds_compound_industry_risk_and_specific_actions() -> None:
    answers = answers_with(5)
    for question_id in ("security_access", "security_mfa", "security_incidents"):
        answers[question_id] = 2

    result = calculate_result(CompanyProfile("Банк", "Финансы", "251–1000"), answers)

    assert len(result.risks) == 4
    assert any("финансовые операции" in risk.title for risk in result.risks)
    assert all(risk.severity == "Высокий" for risk in result.risks)
    assert any("платёжный контур" in risk.action for risk in result.risks)
    assert any("Комплексный отраслевой риск" in risk.context for risk in result.risks)


def test_large_company_adds_compound_scale_risk() -> None:
    answers = answers_with(5)
    for question_id in ("security_access", "management_vendors", "management_kpi"):
        answers[question_id] = 3

    result = calculate_result(CompanyProfile("Холдинг", "Другое", "Более 1000"), answers)

    scale_risk = next(risk for risk in result.risks if "Децентрализация" in risk.title)
    assert scale_risk.severity == "Средний"
    assert "Комплексный масштабный риск" in scale_risk.context
    assert "бизнес-единицам" in scale_risk.action


def test_roadmap_is_contextual_and_has_actions_for_every_horizon() -> None:
    answers = answers_with(5)
    answers["infra_monitoring"] = 1
    profile = CompanyProfile("Завод", "Производство", "251–1000")

    result = calculate_result(profile, answers)

    assert [item.title for item in result.roadmap] == [
        "Стабилизировать критичные зоны",
        "Внедрить управляемые процессы",
        "Закрепить контроль и измерить эффект",
    ]
    assert all(item.actions for item in result.roadmap)
    assert any("АСУ ТП" in action for item in result.roadmap for action in item.actions)
    assert "повторить аудит" in result.roadmap[-1].actions[-1]


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (0, "Критический"),
        (39, "Критический"),
        (40, "Реактивный"),
        (59, "Реактивный"),
        (60, "Стабильный"),
        (79, "Стабильный"),
        (80, "Зрелый"),
        (100, "Зрелый"),
    ],
)
def test_maturity_thresholds(score: int, label: str) -> None:
    assert maturity_label(score) == label
