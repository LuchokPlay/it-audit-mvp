"""Чистая расчётная логика аудита."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from it_audit.catalog import (
    CATEGORIES,
    QUESTIONNAIRE_VERSION,
    QUESTIONS,
    QUESTIONS_BY_ID,
    questions_for_category,
)
from it_audit.context import (
    INDUSTRY_ASSETS,
    INDUSTRY_RISK_RULES,
    SIZE_GOVERNANCE,
    SIZE_RISK_RULES,
    CompoundRiskRule,
    calculate_context_score,
    category_weights,
    context_description,
    contextual_action,
    normalize_employee_range,
)
from it_audit.models import AuditResult, CompanyProfile, RiskItem, RoadmapItem
from it_audit.version import __version__

SEVERITY_BY_ANSWER = {
    1: ("Высокий", 30),
    2: ("Средний", 60),
    3: ("Низкий", 90),
}

ROADMAP_TITLES = {
    30: "Стабилизировать критичные зоны",
    60: "Внедрить управляемые процессы",
    90: "Закрепить контроль и измерить эффект",
}

NOT_APPLICABLE = 0
RISK_LIMIT = 5
SEVERITY_RANK = {"Высокий": 0, "Средний": 1, "Низкий": 2}
HORIZON_BY_SEVERITY = {"Высокий": 30, "Средний": 60, "Низкий": 90}


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
        if not isinstance(value, int) or value not in range(NOT_APPLICABLE, 6)
    }
    if invalid:
        raise ValueError(
            "Каждый ответ должен быть целым числом от 1 до 5 или значением «Не применимо»"
        )


def _category_score(values: list[int]) -> int | None:
    values = [value for value in values if value != NOT_APPLICABLE]
    if not values:
        return None
    average = sum(values) / len(values)
    return round((average - 1) / 4 * 100)


def _severity_for(answer: int, weight: float) -> tuple[str, int]:
    severity, _ = SEVERITY_BY_ANSWER[answer]
    if weight >= 1.25 and severity == "Низкий":
        severity = "Средний"
    elif weight >= 1.25 and severity == "Средний":
        severity = "Высокий"
    return severity, HORIZON_BY_SEVERITY[severity]


def _compound_candidate(
    rule: CompoundRiskRule,
    answers: dict[str, int],
    profile: CompanyProfile,
    *,
    source: str,
    order: int,
) -> tuple[int, int, float, int, RiskItem] | None:
    trigger_values = [
        answers[question_id]
        for question_id in rule.trigger_question_ids
        if answers[question_id] != NOT_APPLICABLE
    ]
    weak_values = [value for value in trigger_values if value <= 3]
    if len(weak_values) < 2 and 1 not in weak_values:
        return None

    weights = category_weights(profile)
    relevant_weight = max(
        weights[QUESTIONS_BY_ID[question_id].category] for question_id in rule.trigger_question_ids
    )
    worst_answer = min(weak_values)
    severity, horizon = _severity_for(worst_answer, relevant_weight)
    context = (
        f"Комплексный {source} риск: одновременно ослаблены {len(weak_values)} связанных контроля."
    )
    item = RiskItem(
        question_id=f"context_{source}_{order}",
        title=rule.title,
        severity=severity,
        horizon_days=horizon,
        action=rule.action,
        context=context,
    )
    return SEVERITY_RANK[severity], worst_answer, -relevant_weight, order, item


def build_risks(
    answers: dict[str, int], profile: CompanyProfile | None = None
) -> tuple[RiskItem, ...]:
    """Выбирает до пяти базовых и комплексных контекстных рисков."""

    _validate_answers(answers)
    weights = (
        category_weights(profile) if profile else {category.key: 1.0 for category in CATEGORIES}
    )
    candidates: list[tuple[int, int, float, int, RiskItem]] = []
    for order, question in enumerate(QUESTIONS):
        answer = answers[question.id]
        if answer == NOT_APPLICABLE:
            continue
        if answer > 3:
            continue
        weight = weights[question.category]
        severity, horizon = _severity_for(answer, weight)
        action = question.action
        context = ""
        if profile is not None:
            action = contextual_action(action, question.category, profile)
            context = context_description(question.category, profile, weight)
        candidates.append(
            (
                SEVERITY_RANK[severity],
                answer,
                -weight,
                order,
                RiskItem(
                    question_id=question.id,
                    title=question.risk,
                    severity=severity,
                    horizon_days=horizon,
                    action=action,
                    context=context,
                ),
            )
        )

    if profile is not None:
        industry_rule = INDUSTRY_RISK_RULES.get(profile.industry)
        if industry_rule is not None:
            candidate = _compound_candidate(
                industry_rule,
                answers,
                profile,
                source="отраслевой",
                order=-2,
            )
            if candidate is not None:
                candidates.append(candidate)

        size = normalize_employee_range(profile.employee_range)
        size_rule = SIZE_RISK_RULES.get(size)
        if size_rule is not None:
            candidate = _compound_candidate(
                size_rule,
                answers,
                profile,
                source="масштабный",
                order=-1,
            )
            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(key=lambda candidate: candidate[:4])
    return tuple(candidate[4] for candidate in candidates[:RISK_LIMIT])


def _unique(items: list[str], limit: int) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))[:limit]


def build_roadmap(
    risks: tuple[RiskItem, ...], profile: CompanyProfile | None = None
) -> tuple[RoadmapItem, ...]:
    """Строит связный план: стабилизация, внедрение и контроль эффекта."""

    industry = profile.industry if profile else "Другое"
    size = normalize_employee_range(profile.employee_range) if profile else "101–250"
    assets = INDUSTRY_ASSETS.get(industry, INDUSTRY_ASSETS["Другое"])
    governance = SIZE_GOVERNANCE.get(size, SIZE_GOVERNANCE["101–250"])

    high = [risk for risk in risks if risk.severity == "Высокий"]
    medium = [risk for risk in risks if risk.severity == "Средний"]
    low = [risk for risk in risks if risk.severity == "Низкий"]

    actions_30 = [risk.action for risk in high[:2]]
    if not actions_30:
        actions_30.append(f"Подтвердить владельцев и аварийные контакты для: {assets}.")
    actions_30.append(f"Зафиксировать ожидаемый результат и ответственного. {governance}")

    actions_60 = [risk.action for risk in medium[:2]]
    if high:
        high_titles = "; ".join(risk.title for risk in high[:2])
        actions_60.append(f"Завершить внедрение мер и приёмочные проверки: {high_titles}.")
    if not actions_60:
        actions_60.append(f"Проверить действующие контроли для: {assets}.")

    actions_90 = [risk.action for risk in low[:1]]
    actions_90.append(
        "Утвердить 3–5 измеримых показателей, проверить эффект внедрённых мер и повторить аудит."
    )

    actions_by_horizon = {
        30: _unique(actions_30, 3),
        60: _unique(actions_60, 3),
        90: _unique(actions_90, 2),
    }
    return tuple(
        RoadmapItem(
            horizon_days=horizon,
            title=ROADMAP_TITLES[horizon],
            actions=actions_by_horizon[horizon],
        )
        for horizon in (30, 60, 90)
    )


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
    applicable_scores = [score for score in scores.values() if score is not None]
    if not applicable_scores:
        raise ValueError("Нужен хотя бы один применимый ответ для расчёта результата")
    overall_score = round(sum(applicable_scores) / len(applicable_scores))
    context_score, weights = calculate_context_score(scores, profile)
    risks = build_risks(answers, profile)
    return AuditResult(
        id=audit_id or str(uuid4()),
        created_at=created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        profile=profile,
        answers=dict(answers),
        scores=scores,
        overall_score=overall_score,
        maturity=maturity_label(overall_score),
        risks=risks,
        roadmap=build_roadmap(risks, profile),
        questionnaire_version=QUESTIONNAIRE_VERSION,
        app_version=__version__,
        context_score=context_score,
        category_weights=weights,
    )
