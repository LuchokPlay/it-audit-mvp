import pytest

from it_audit.catalog import CATEGORIES, QUESTIONS
from it_audit.models import CompanyProfile
from it_audit.scoring import build_risks, calculate_result, maturity_label

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
    assert result.maturity == "Критический"


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


def test_risks_are_sorted_and_limited_to_three() -> None:
    answers = answers_with(5)
    answers[QUESTIONS[0].id] = 2
    answers[QUESTIONS[1].id] = 1
    answers[QUESTIONS[2].id] = 3
    answers[QUESTIONS[3].id] = 1

    risks = build_risks(answers)

    assert len(risks) == 3
    assert [risk.question_id for risk in risks] == [
        QUESTIONS[1].id,
        QUESTIONS[3].id,
        QUESTIONS[0].id,
    ]
    assert [risk.horizon_days for risk in risks] == [30, 30, 60]


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
