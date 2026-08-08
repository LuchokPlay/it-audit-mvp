"""Страницы и интерактивный сценарий Streamlit."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from html import escape
from typing import Any

import streamlit as st

from it_audit.catalog import CATEGORIES, questions_for_category
from it_audit.models import AuditResult, CompanyProfile
from it_audit.report import render_html_report
from it_audit.scoring import calculate_result
from it_audit.storage import delete_audit, get_audit, list_audits, save_audit

LOGGER = logging.getLogger(__name__)

INDUSTRIES = (
    "Финансы",
    "Ритейл",
    "Производство",
    "Транспорт и логистика",
    "Профессиональные услуги",
    "Государственный сектор",
    "Информационные технологии",
    "Телекоммуникации",
    "Энергетика и ЖКХ",
    "Строительство и недвижимость",
    "Здравоохранение",
    "Образование",
    "Другое",
)

EMPLOYEE_RANGES = ("До 50", "50–100", "101–250", "251–1000", "Более 1000")
DRAFT_KEY = "audit_draft"
HISTORY_NOTICE_KEY = "history_notice"


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
            escape(value)
            for value in (profile["industry"], profile["employee_range"])
            if value
        )
        if details:
            st.markdown(f'<div class="audit-meta">{details}</div>', unsafe_allow_html=True)
    _progress(step)


def _render_profile_step(draft: dict[str, Any]) -> None:
    profile = draft["profile"]
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
            "Отрасль и численность добавляются в отчёт, но не изменяют баллы, риски и план."
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
    category_index = draft["step"] - 1
    category = CATEGORIES[category_index]
    questions = questions_for_category(category.key)
    profile = draft["profile"]
    _profile_header(profile, draft["step"] + 1)

    st.subheader(category.title)
    st.caption("Оцените по шкале от 1 до 5, где 1 — очень низкий уровень, 5 — зрелая практика.")

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
                    options=(1, 2, 3, 4, 5),
                    index=saved_value - 1 if saved_value else None,
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
    draft["result"] = calculate_result(company, draft["answers"])
    draft["step"] = 5
    draft["saved"] = False
    st.rerun()


def _score_markup(result: AuditResult) -> str:
    values = []
    bars = []
    for category in CATEGORIES:
        score = result.scores[category.key]
        critical = " critical" if score < 40 else ""
        values.append(
            f'<div class="score-value-row"><span>{escape(category.title)}</span>'
            f'<strong class="{critical.strip()}">{score}</strong></div>'
        )
        bars.append(
            f'<div class="bar-row"><span>{escape(category.title)}</span>'
            f'<div class="bar-track"><div class="bar-fill{critical}" '
            f'style="width:{score}%"></div></div><strong>{score}</strong></div>'
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
            '<div class="empty-state">'
            "Существенных рисков по результатам анкеты не выявлено.</div>"
        )
    severity_classes = {"Высокий": "high", "Средний": "medium", "Низкий": "low"}
    rows = []
    for risk in result.risks:
        severity_class = severity_classes[risk.severity]
        rows.append(
            f'<tr><td class="risk-mark {severity_class}"></td>'
            f'<td>{escape(risk.title)}</td>'
            f'<td><span class="severity {severity_class}">{escape(risk.severity)}</span></td>'
            f'<td>{risk.horizon_days} дней</td></tr>'
        )
    return (
        '<table class="risk-table"><thead><tr><th></th><th>Риск</th>'
        '<th>Уровень</th><th>Горизонт</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _roadmap_markup(result: AuditResult) -> str:
    items = []
    for item in result.roadmap:
        actions = "<br>".join(escape(action) for action in item.actions)
        items.append(
            '<div class="roadmap-item">'
            f'<div class="roadmap-day">{item.horizon_days} дней</div>'
            f'<div class="roadmap-title">{escape(item.title)}</div>'
            f'<div class="roadmap-actions">{actions}</div></div>'
        )
    return '<div class="roadmap">' + "".join(items) + "</div>"


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
    st.markdown(
        f'<div class="overall-note">Общая оценка: {result.overall_score} · '
        f'{escape(result.maturity)} уровень</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_score_markup(result), unsafe_allow_html=True)
    st.subheader("Ключевые риски")
    st.markdown(_risk_markup(result), unsafe_allow_html=True)
    st.subheader("План 30 / 60 / 90 дней")
    st.markdown(_roadmap_markup(result), unsafe_allow_html=True)
    _result_actions(result, allow_save=allow_save, saved=saved)


def render_audit_page() -> None:
    """Показывает текущий шаг нового аудита или его результат."""

    draft = _draft()
    if isinstance(draft["result"], AuditResult):
        render_result(draft["result"], allow_save=True, saved=draft["saved"])
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


def render_history_page() -> None:
    """Показывает сохранённые аудиты и выбранный полный результат."""

    st.title("История аудитов")
    if notice := st.session_state.pop(HISTORY_NOTICE_KEY, None):
        st.success(notice)
    try:
        summaries = list_audits()
    except sqlite3.Error:
        LOGGER.exception("Не удалось загрузить историю")
        st.error("Не удалось открыть локальную базу данных.")
        return
    if not summaries:
        st.markdown(
            '<div class="empty-state">'
            "История пока пуста. Завершите и сохраните первый аудит.</div>",
            unsafe_allow_html=True,
        )
        return

    history_rows = "".join(
        "<tr>"
        f"<td>{escape(_format_history_date(summary.created_at))}</td>"
        f"<td>{escape(summary.company_name)}</td>"
        f"<td>{escape(summary.industry)}</td>"
        f"<td><strong>{summary.overall_score}</strong></td>"
        f"<td>{escape(summary.maturity)}</td>"
        "</tr>"
        for summary in summaries
    )
    st.markdown(
        '<div class="table-scroll"><table class="history-table">'
        "<thead><tr><th>Дата</th><th>Компания</th><th>Отрасль</th>"
        "<th>Оценка</th><th>Уровень</th></tr></thead>"
        f"<tbody>{history_rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    summaries_by_id = {summary.id: summary for summary in summaries}
    selected_id = st.selectbox(
        "Открыть аудит",
        options=list(summaries_by_id),
        format_func=lambda audit_id: (
            f"{summaries_by_id[audit_id].company_name} — "
            f"{_format_history_date(summaries_by_id[audit_id].created_at)}"
        ),
    )
    selected_summary = summaries_by_id[selected_id]
    delete_confirmed = False
    delete_column, _ = st.columns([1.2, 2.8])
    with delete_column, st.popover("Удалить отчёт", use_container_width=True):
        st.warning(
            f"Удалить аудит «{selected_summary.company_name}»? "
            "Это действие нельзя отменить."
        )
        delete_confirmed = st.button(
            "Удалить безвозвратно",
            key=f"confirm_delete_{selected_id}",
            use_container_width=True,
        )
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
    try:
        result = get_audit(selected_id)
    except sqlite3.Error:
        LOGGER.exception("Не удалось загрузить аудит")
        st.error("Не удалось загрузить выбранный аудит.")
        return
    if result is None:
        st.warning("Выбранный аудит больше не найден.")
        return
    st.markdown('<div class="audit-section-rule"></div>', unsafe_allow_html=True)
    render_result(result, allow_save=False)
