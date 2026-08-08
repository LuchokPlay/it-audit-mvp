"""Чистая расчётная логика аудита."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from it_audit.catalog import CATEGORIES, QUESTIONS, QUESTIONS_BY_ID, questions_for_category
from it_audit.models import AuditResult, CompanyProfile, RiskItem, RoadmapItem

SEVERITY_BY_ANSWER = {
    1: ("Высокий", 30),
    2: ("Средний", 60),
    3: ("Низкий", 90),
}

ROADMAP_TITLES = {
    30: "Быстрые победы и снижение рисков",
    60: "Внедрение приоритетных улучшений",
    90: "Закрепление процессов и измерение эффекта",
}

ROADMAP_DEFAULTS = {
    30: "Подтвердить владельцев критичных систем и ближайшие приоритеты.",
    60: "Проверить прогресс и скорректировать план улучшений.",
    90: "Повторно измерить показатели и закрепить рабочие практики.",
}


def maturity_label(score: int) -> str:
    """Возвращает текстовый уровень зрелости для шкалы 0–100."""

    if not 0 <= score <= 100:
        raise ValueError("Оценка должна находиться в диапазоне от 0 до 100")
    if score <= 39:
        return "Критический"
    if score <= 59:
        return "Реактивный"
    if score <= 79:
        return "Стабильный"
    return "Зрелый"


def _validate_answers(answers: dict[str, int]) -> None:
    expected = set(QUESTIONS_BY_ID)
    actual = set(answers)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"не заполнены: {', '.join(missing)}")
        if extra:
            details.append(f"неизвестные вопросы: {', '.join(extra)}")
        raise ValueError("Некорректный набор ответов: " + "; ".join(details))

    invalid = {
        question_id: value
        for question_id, value in answers.items()
        if value not in range(1, 6)
    }
    if invalid:
        raise ValueError("Каждый ответ должен быть целым числом от 1 до 5")


def _category_score(values: list[int]) -> int:
    average = sum(values) / len(values)
    return round((average - 1) / 4 * 100)


def build_risks(answers: dict[str, int]) -> tuple[RiskItem, ...]:
    """Выбирает три наиболее серьёзных риска из ответов со значением 1–3."""

    _validate_answers(answers)
    candidates: list[tuple[int, int, RiskItem]] = []
    for order, question in enumerate(QUESTIONS):
        answer = answers[question.id]
        if answer > 3:
            continue
        severity, horizon = SEVERITY_BY_ANSWER[answer]
        candidates.append(
            (
                answer,
                order,
                RiskItem(
                    question_id=question.id,
                    title=question.risk,
                    severity=severity,
                    horizon_days=horizon,
                    action=question.action,
                ),
            )
        )

    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    return tuple(candidate[2] for candidate in candidates[:3])


def build_roadmap(risks: tuple[RiskItem, ...]) -> tuple[RoadmapItem, ...]:
    """Группирует действия по горизонтам 30, 60 и 90 дней."""

    roadmap = []
    for horizon in (30, 60, 90):
        actions = tuple(risk.action for risk in risks if risk.horizon_days == horizon)
        if not actions:
            actions = (ROADMAP_DEFAULTS[horizon],)
        roadmap.append(
            RoadmapItem(
                horizon_days=horizon,
                title=ROADMAP_TITLES[horizon],
                actions=actions,
            )
        )
    return tuple(roadmap)


def calculate_result(
    profile: CompanyProfile,
    answers: dict[str, int],
    *,
    audit_id: str | None = None,
    created_at: str | None = None,
) -> AuditResult:
    """Рассчитывает полный снимок результата завершённого аудита."""

    _validate_answers(answers)
    scores = {
        category.key: _category_score(
            [answers[question.id] for question in questions_for_category(category.key)]
        )
        for category in CATEGORIES
    }
    overall_score = round(sum(scores.values()) / len(scores))
    risks = build_risks(answers)
    return AuditResult(
        id=audit_id or str(uuid4()),
        created_at=created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        profile=profile,
        answers=dict(answers),
        scores=scores,
        overall_score=overall_score,
        maturity=maturity_label(overall_score),
        risks=risks,
        roadmap=build_roadmap(risks),
    )
