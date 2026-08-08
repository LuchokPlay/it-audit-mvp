"""Страницы и интерактивный сценарий Streamlit."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from html import escape
from typing import Any

import streamlit as st

from it_audit.catalog import CATEGORIES, questions_for_category
from it_audit.context import (
    SUPPORTED_EMPLOYEE_RANGES,
    SUPPORTED_INDUSTRIES,
    normalize_employee_range,
)
from it_audit.models import AuditResult, AuditSummary, CompanyProfile
from it_audit.report import render_html_report
from it_audit.scoring import NOT_APPLICABLE, calculate_result, maturity_label
from it_audit.storage import delete_audit, get_audit, list_audits, save_audit

LOGGER = logging.getLogger(__name__)

INDUSTRIES = SUPPORTED_INDUSTRIES
EMPLOYEE_RANGES = SUPPORTED_EMPLOYEE_RANGES
ANSWER_OPTIONS = (1, 2, 3, 4, 5, NOT_APPLICABLE)
DRAFT_KEY = "audit_draft"
HISTORY_NOTICE_KEY = "history_notice"
HISTORY_SELECTED_KEY = "history_selected_audit"
COMPARISON_SELECTED_KEY = "comparison_selected_audit"


def _empty_draft() -> dict[str, Any]:
    return {
        "step": 0,
        "profile": {"name": "", "industry": "", "employee_range": ""},
        "answers": {},
        "result": None,
        "saved": False,
    }


def _draft() -> dict[str, Any]:
    if DRAFT_KEY not in st.session_state:
        st.session_state[DRAFT_KEY] = _empty_draft()
    return st.session_state[DRAFT_KEY]


def _reset_draft() -> None:
    st.session_state[DRAFT_KEY] = _empty_draft()
    for key in tuple(st.session_state):
        if key.startswith("answer_"):
            del st.session_state[key]


def _normalize_employee_range(value: str) -> str:
    return normalize_employee_range(value)


def _start_repeat(result: AuditResult) -> None:
    """Начинает новую анкету с реквизитами выбранного сохранённого аудита."""

    _reset_draft()
    st.session_state[DRAFT_KEY]["profile"] = {
        "name": result.profile.name,
        "industry": result.profile.industry,
        "employee_range": _normalize_employee_range(result.profile.employee_range),
    }


def _progress(step: int) -> None:
    percent = max(1, min(step, 5)) * 20
    st.markdown(
        f"""
        <div class="progress-meta">Шаг {step} из 5</div>
        <div class="progress-track" aria-label="Прогресс анкеты">
          <div class="progress-fill" style="width:{percent}%"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _profile_header(profile: dict[str, str], step: int) -> None:
    st.title("Профиль компании")
    if profile["name"]:
        st.markdown(
            f'<div class="audit-company">{escape(profile["name"])}</div>',
            unsafe_allow_html=True,
        )
        details = " · ".join(
            escape(value) for value in (profile["industry"], profile["employee_range"]) if value
        )
        if details:
            st.markdown(f'<div class="audit-meta">{details}</div>', unsafe_allow_html=True)
    _progress(step)


def _render_profile_step(draft: dict[str, Any]) -> None:
    profile = draft["profile"]
    profile["employee_range"] = _normalize_employee_range(profile["employee_range"])
    _profile_header(profile, 1)
    with st.form("profile_form"):
        name = st.text_input(
            "Название компании",
            value=profile["name"],
            placeholder="Например, Альфа Логистика",
            max_chars=100,
        )
        industry = st.selectbox(
            "Отрасль",
            INDUSTRIES,
            index=INDUSTRIES.index(profile["industry"]) if profile["industry"] else None,
            placeholder="Выберите отрасль",
        )
        employee_range = st.selectbox(
            "Количество сотрудников",
            EMPLOYEE_RANGES,
            index=(
                EMPLOYEE_RANGES.index(profile["employee_range"])
                if profile["employee_range"]
                else None
            ),
            placeholder="Выберите диапазон",
        )
        st.caption(
            "Отрасль и численность задают веса контекстной оценки, приоритет рисков "
            "и формат рекомендаций. Базовая зрелость остаётся сопоставимой."
        )
        st.markdown('<div class="audit-section-rule"></div>', unsafe_allow_html=True)
        _, action = st.columns([2.6, 1])
        with action:
            submitted = st.form_submit_button(
                "Продолжить",
                type="primary",
                use_container_width=True,
            )

    if not submitted:
        return
    cleaned_name = name.strip()
    if len(cleaned_name) < 2 or industry is None or employee_range is None:
        st.error("Заполните название, отрасль и количество сотрудников.")
        return
    profile.update(
        name=cleaned_name,
        industry=industry,
        employee_range=employee_range,
    )
    draft["step"] = 1
    st.rerun()


def _render_question_step(draft: dict[str, Any]) -> None:
    if not isinstance(draft.get("step"), int) or not 1 <= draft["step"] <= len(CATEGORIES):
        draft["step"] = len(CATEGORIES)
    category_index = draft["step"] - 1
    category = CATEGORIES[category_index]
    questions = questions_for_category(category.key)
    profile = draft["profile"]
    _profile_header(profile, draft["step"] + 1)

    st.subheader(category.title)
    st.caption(
        "Оцените по шкале от 1 до 5, где 1 — очень низкий уровень, "
        "5 — зрелая практика. «Не применимо» исключается из среднего балла."
    )

    values: dict[str, int | None] = {}
    with st.form(f"questions_{category.key}"):
        for number, question in enumerate(questions, start=1):
            copy_column, score_column = st.columns([2.15, 1], vertical_alignment="center")
            with copy_column:
                st.markdown(
                    '<div class="question-copy">'
                    f"<strong>{number}.</strong>{escape(question.text)}</div>",
                    unsafe_allow_html=True,
                )
            with score_column:
                saved_value = draft["answers"].get(question.id)
                values[question.id] = st.radio(
                    question.text,
                    options=ANSWER_OPTIONS,
                    index=(ANSWER_OPTIONS.index(saved_value) if saved_value is not None else None),
                    format_func=(
                        lambda value: "Не применимо" if value == NOT_APPLICABLE else str(value)
                    ),
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"answer_{question.id}",
                )

        st.markdown('<div style="height:.8rem"></div>', unsafe_allow_html=True)
        back_column, _, next_column = st.columns([1, 1.5, 1])
        with back_column:
            back = st.form_submit_button(
                "Назад",
                use_container_width=True,
            )
        with next_column:
            next_label = "Рассчитать" if category_index == len(CATEGORIES) - 1 else "Продолжить"
            forward = st.form_submit_button(
                next_label,
                type="primary",
                use_container_width=True,
            )

    draft["answers"].update(
        {question_id: value for question_id, value in values.items() if value is not None}
    )
    if back:
        draft["step"] -= 1
        st.rerun()
    if not forward:
        return
    if any(value is None for value in values.values()):
        st.error("Ответьте на все четыре вопроса текущего раздела.")
        return

    if category_index < len(CATEGORIES) - 1:
        draft["step"] += 1
        st.rerun()

    company = CompanyProfile(**profile)
    try:
        draft["result"] = calculate_result(company, draft["answers"])
    except ValueError as error:
        st.error(str(error))
        return
    draft["step"] = 5
    draft["saved"] = False
    st.rerun()


def _score_markup(result: AuditResult) -> str:
    values = []
    bars = []
    for category in CATEGORIES:
        score = result.scores[category.key]
        score_label = "Н/Д" if score is None else str(score)
        width = 0 if score is None else score
        critical = " critical" if score is not None and score < 40 else ""
        weight = result.category_weights.get(category.key)
        weight_label = f'<small class="score-weight">×{weight:.2f}</small>' if weight else ""
        values.append(
            f'<div class="score-value-row"><span>{escape(category.title)} {weight_label}</span>'
            f'<strong class="{critical.strip()}">{score_label}</strong></div>'
        )
        bars.append(
            f'<div class="bar-row"><span>{escape(category.title)}</span>'
            f'<div class="bar-track"><div class="bar-fill{critical}" '
            f'style="width:{width}%"></div></div><strong>{score_label}</strong></div>'
        )
    return (
        '<div class="score-layout"><div class="score-values">'
        + "".join(values)
        + '</div><div class="bar-chart">'
        + "".join(bars)
        + "</div></div>"
    )


def _risk_markup(result: AuditResult) -> str:
    if not result.risks:
        return (
            '<div class="empty-state">Существенных рисков по результатам анкеты не выявлено.</div>'
        )
    severity_classes = {"Высокий": "high", "Средний": "medium", "Низкий": "low"}
    rows = []
    for risk in result.risks:
        severity_class = severity_classes[risk.severity]
        context_markup = (
            f'<div class="risk-context">{escape(risk.context)}</div>' if risk.context else ""
        )
        rows.append(
            f'<tr><td class="risk-mark {severity_class}"></td>'
            f"<td>{escape(risk.title)}{context_markup}</td>"
            f'<td><span class="severity {severity_class}">{escape(risk.severity)}</span></td>'
            f"<td>{risk.horizon_days} дней</td></tr>"
        )
    return (
        '<table class="risk-table"><thead><tr><th></th><th>Риск</th>'
        "<th>Уровень</th><th>Горизонт</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _roadmap_markup(result: AuditResult) -> str:
    items = []
    for item in result.roadmap:
        actions = "".join(f"<li>{escape(action)}</li>" for action in item.actions)
        items.append(
            '<div class="roadmap-item">'
            f'<div class="roadmap-day">{item.horizon_days} дней</div>'
            f'<div class="roadmap-title">{escape(item.title)}</div>'
            f'<div class="roadmap-actions"><ul>{actions}</ul></div></div>'
        )
    return '<div class="roadmap">' + "".join(items) + "</div>"


def _render_context_explanation(result: AuditResult) -> None:
    if result.context_score is None or not result.category_weights:
        return
    with st.expander("Как учтены отрасль и масштаб"):
        st.markdown(
            f"Для профиля **{escape(result.profile.industry)} · "
            f"{escape(result.profile.employee_range)} сотрудников** базовые оценки "
            "направлений умножаются на следующие веса:"
        )
        rows = []
        for category in CATEGORIES:
            weight = result.category_weights[category.key]
            if weight > 1.05:
                influence = "повышенный приоритет"
            elif weight < 0.95:
                influence = "пониженный приоритет"
            else:
                influence = "базовый приоритет"
            rows.append(
                "<tr>"
                f"<td>{escape(category.title)}</td>"
                f"<td>×{weight:.2f}</td>"
                f"<td>{influence}</td>"
                "</tr>"
            )
        st.markdown(
            '<div class="table-scroll"><table class="history-table context-table">'
            "<thead><tr><th>Направление</th><th>Вес</th><th>Влияние</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Базовая зрелость не меняется. Вес влияет на контекстную оценку и может "
            "повысить серьёзность связанного риска на один уровень."
        )


def _result_actions(result: AuditResult, *, allow_save: bool, saved: bool) -> None:
    report = render_html_report(result)
    save_column, _, export_column = st.columns([1.2, 1, 1.45])
    if allow_save:
        with save_column:
            save_clicked = st.button(
                "Аудит сохранён" if saved else "Сохранить аудит",
                disabled=saved,
                use_container_width=True,
            )
        if save_clicked:
            try:
                created = save_audit(result)
            except sqlite3.Error:
                LOGGER.exception("Не удалось сохранить аудит")
                st.error("Не удалось сохранить аудит. Проверьте доступ к папке data.")
            else:
                st.session_state[DRAFT_KEY]["saved"] = True
                if created:
                    st.success("Аудит сохранён в локальной истории.")
                else:
                    st.info("Этот аудит уже присутствует в истории.")
                st.rerun()
    with export_column:
        st.download_button(
            "Экспортировать отчёт",
            data=report.encode("utf-8"),
            file_name=f"it-audit-{result.id[:8]}.html",
            mime="text/html; charset=utf-8",
            type="primary",
            use_container_width=True,
        )


def render_result(result: AuditResult, *, allow_save: bool, saved: bool = False) -> None:
    """Показывает общий экран результата для нового аудита и истории."""

    st.title("Результаты аудита")
    st.markdown(
        f'<div class="audit-company">{escape(result.profile.name)}</div>',
        unsafe_allow_html=True,
    )
    context_card = ""
    if result.context_score is not None:
        context_maturity = maturity_label(result.context_score)
        context_card = (
            '<div class="summary-score context-score">'
            "<span>Контекстная оценка</span>"
            f"<strong>{result.context_score}</strong>"
            f"<small>{escape(context_maturity)} · отрасль и масштаб</small></div>"
        )
    st.markdown(
        '<div class="score-summary">'
        '<div class="summary-score"><span>Базовая зрелость</span>'
        f"<strong>{result.overall_score}</strong>"
        f"<small>{escape(result.maturity)} · единая методика</small></div>"
        f"{context_card}</div>"
        f'<div class="overall-note">Версия анкеты: {escape(result.questionnaire_version)} · '
        f"Версия приложения: {escape(result.app_version)}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_score_markup(result), unsafe_allow_html=True)
    st.caption(
        "Вес × рядом с направлением влияет только на контекстную оценку. "
        "Ответы «Не применимо» исключены из расчёта."
    )
    _render_context_explanation(result)
    st.subheader("Ключевые риски")
    st.markdown(_risk_markup(result), unsafe_allow_html=True)
    st.subheader("План 30 / 60 / 90 дней")
    st.markdown(_roadmap_markup(result), unsafe_allow_html=True)
    _result_actions(result, allow_save=allow_save, saved=saved)


def render_audit_page() -> None:
    """Показывает текущий шаг нового аудита или его результат."""

    draft = _draft()
    result = draft.get("result")
    if result is not None:
        # Streamlit may reload the module after a source update while keeping the
        # previous AuditResult instance in session_state. Attribute access remains
        # valid even though isinstance() against the reloaded class would be false.
        render_result(result, allow_save=True, saved=draft["saved"])
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        if st.button("Начать новый аудит", type="tertiary"):
            _reset_draft()
            st.rerun()
        return
    if draft["step"] == 0:
        _render_profile_step(draft)
    else:
        _render_question_step(draft)


def _format_history_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def _filter_summaries(summaries: list[AuditSummary]) -> list[AuditSummary]:
    query_column, industry_column, maturity_column = st.columns([1.5, 1, 1])
    with query_column:
        query = st.text_input("Поиск по компании", placeholder="Введите название")
    industries = sorted({summary.industry for summary in summaries})
    with industry_column:
        industry = st.selectbox("Отрасль", ("Все отрасли", *industries))
    maturity_order = ("Критический", "Реактивный", "Стабильный", "Зрелый")
    maturities = tuple(
        maturity
        for maturity in maturity_order
        if any(summary.maturity == maturity for summary in summaries)
    )
    with maturity_column:
        maturity = st.selectbox("Уровень", ("Все уровни", *maturities))

    normalized_query = query.strip().casefold()
    return [
        summary
        for summary in summaries
        if (not normalized_query or normalized_query in summary.company_name.casefold())
        and (industry == "Все отрасли" or summary.industry == industry)
        and (maturity == "Все уровни" or summary.maturity == maturity)
    ]


def _score_text(score: int | None) -> str:
    return "Н/Д" if score is None else str(score)


def _render_comparison(selected: AuditResult, summaries: list[AuditSummary]) -> None:
    candidates = [
        summary
        for summary in summaries
        if summary.id != selected.id
        and summary.company_name.strip().casefold() == selected.profile.name.strip().casefold()
    ]
    if not candidates:
        return

    candidates_by_id = {summary.id: summary for summary in candidates}
    if st.session_state.get(COMPARISON_SELECTED_KEY) not in candidates_by_id:
        st.session_state.pop(COMPARISON_SELECTED_KEY, None)
    comparison_id = st.selectbox(
        "Сравнить с другим аудитом этой компании",
        options=list(candidates_by_id),
        format_func=lambda audit_id: (
            f"{_format_history_date(candidates_by_id[audit_id].created_at)} — "
            f"{candidates_by_id[audit_id].overall_score} баллов"
        ),
        key=COMPARISON_SELECTED_KEY,
    )
    try:
        comparison = get_audit(comparison_id)
    except sqlite3.Error:
        LOGGER.exception("Не удалось загрузить аудит для сравнения")
        st.error("Не удалось загрузить аудит для сравнения.")
        return
    if comparison is None:
        st.warning("Аудит для сравнения больше не найден.")
        return

    earlier, later = sorted((selected, comparison), key=lambda item: item.created_at)
    overall_delta = later.overall_score - earlier.overall_score
    st.subheader("Динамика результатов")
    st.caption(
        f"Сравниваются анкеты версий {earlier.questionnaire_version} и "
        f"{later.questionnaire_version}."
    )
    earlier_column, later_column, delta_column = st.columns(3)
    earlier_column.metric(
        f"Было · {_format_history_date(earlier.created_at)}", earlier.overall_score
    )
    later_column.metric(f"Стало · {_format_history_date(later.created_at)}", later.overall_score)
    delta_column.metric("Изменение", f"{overall_delta:+d}")

    rows = []
    if earlier.context_score is not None or later.context_score is not None:
        context_delta = (
            None
            if earlier.context_score is None or later.context_score is None
            else later.context_score - earlier.context_score
        )
        context_delta_label = "—" if context_delta is None else f"{context_delta:+d}"
        rows.append(
            "<tr><td><strong>Контекстная оценка</strong></td>"
            f"<td>{_score_text(earlier.context_score)}</td>"
            f"<td>{_score_text(later.context_score)}</td>"
            f"<td>{context_delta_label}</td></tr>"
        )
    for category in CATEGORIES:
        earlier_score = earlier.scores[category.key]
        later_score = later.scores[category.key]
        delta = (
            None if earlier_score is None or later_score is None else later_score - earlier_score
        )
        delta_label = "—" if delta is None else f"{delta:+d}"
        if delta is None or delta == 0:
            delta_class = ""
        else:
            delta_class = "delta-up" if delta > 0 else "delta-down"
        rows.append(
            "<tr>"
            f"<td>{escape(category.title)}</td>"
            f"<td>{_score_text(earlier_score)}</td>"
            f"<td>{_score_text(later_score)}</td>"
            f'<td class="{delta_class}">{delta_label}</td>'
            "</tr>"
        )
    st.markdown(
        '<div class="table-scroll"><table class="history-table comparison-table">'
        "<thead><tr><th>Направление</th><th>Было</th><th>Стало</th>"
        "<th>Изменение</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render_history_page(new_audit_page: Any | None = None) -> None:
    """Показывает сохранённые аудиты и выбранный полный результат."""

    st.title("История аудитов")
    if notice := st.session_state.pop(HISTORY_NOTICE_KEY, None):
        st.success(notice)
    try:
        all_summaries = list_audits()
    except sqlite3.Error:
        LOGGER.exception("Не удалось загрузить историю")
        st.error("Не удалось открыть локальную базу данных.")
        return
    if not all_summaries:
        st.markdown(
            '<div class="empty-state">'
            "История пока пуста. Завершите и сохраните первый аудит.</div>",
            unsafe_allow_html=True,
        )
        return

    summaries = _filter_summaries(all_summaries)
    st.caption(f"Найдено аудитов: {len(summaries)} из {len(all_summaries)}")
    if not summaries:
        st.markdown(
            '<div class="empty-state">По заданным фильтрам аудиты не найдены.</div>',
            unsafe_allow_html=True,
        )
        return

    history_rows = "".join(
        "<tr>"
        f"<td>{escape(_format_history_date(summary.created_at))}</td>"
        f"<td>{escape(summary.company_name)}</td>"
        f"<td>{escape(summary.industry)}</td>"
        f"<td><strong>{summary.overall_score}</strong></td>"
        f"<td>{_score_text(summary.context_score)}</td>"
        f"<td>{escape(summary.maturity)}</td>"
        f"<td>{escape(summary.questionnaire_version)}</td>"
        "</tr>"
        for summary in summaries
    )
    st.markdown(
        '<div class="table-scroll"><table class="history-table">'
        "<thead><tr><th>Дата</th><th>Компания</th><th>Отрасль</th>"
        "<th>База</th><th>Контекст</th><th>Уровень</th><th>Анкета</th></tr></thead>"
        f"<tbody>{history_rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    summaries_by_id = {summary.id: summary for summary in summaries}
    if st.session_state.get(HISTORY_SELECTED_KEY) not in summaries_by_id:
        st.session_state.pop(HISTORY_SELECTED_KEY, None)
    selected_id = st.selectbox(
        "Открыть аудит",
        options=list(summaries_by_id),
        format_func=lambda audit_id: (
            f"{summaries_by_id[audit_id].company_name} — "
            f"{_format_history_date(summaries_by_id[audit_id].created_at)}"
        ),
        key=HISTORY_SELECTED_KEY,
    )
    selected_summary = summaries_by_id[selected_id]
    try:
        result = get_audit(selected_id)
    except sqlite3.Error:
        LOGGER.exception("Не удалось загрузить аудит")
        st.error("Не удалось загрузить выбранный аудит.")
        return
    if result is None:
        st.warning("Выбранный аудит больше не найден.")
        return

    delete_confirmed = False
    repeat_column, delete_column, _ = st.columns([1.35, 1.2, 1.6])
    with repeat_column:
        repeat_clicked = st.button("Повторить аудит", type="primary", use_container_width=True)
    with delete_column, st.popover("Удалить отчёт", use_container_width=True):
        st.warning(
            f"Удалить аудит «{selected_summary.company_name}»? Это действие нельзя отменить."
        )
        delete_confirmed = st.button(
            "Удалить безвозвратно",
            key=f"confirm_delete_{selected_id}",
            use_container_width=True,
        )
    if repeat_clicked:
        _start_repeat(result)
        if new_audit_page is not None:
            st.switch_page(new_audit_page)
        st.success("Профиль компании перенесён в новую анкету.")
        return
    if delete_confirmed:
        try:
            deleted = delete_audit(selected_id)
        except sqlite3.Error:
            LOGGER.exception("Не удалось удалить аудит")
            st.error("Не удалось удалить выбранный аудит.")
            return
        if deleted:
            st.session_state[HISTORY_NOTICE_KEY] = "Отчёт удалён из истории."
            st.rerun()
        st.warning("Выбранный аудит уже отсутствует в истории.")
        return
    st.markdown('<div class="audit-section-rule"></div>', unsafe_allow_html=True)
    _render_comparison(result, all_summaries)
    render_result(result, allow_save=False)
