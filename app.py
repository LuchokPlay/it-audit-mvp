"""Точка входа локального Streamlit-приложения."""

import sqlite3

import streamlit as st

from it_audit import __version__
from it_audit.pages import render_audit_page, render_history_page
from it_audit.storage import init_db
from it_audit.styles import apply_global_styles

st.set_page_config(
    page_title="ИТ-Аудит",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "### ИТ-Аудит\n\n"
            f"Версия приложения: **{__version__}**\n\n"
            "Экспресс-оценка ИТ-зрелости компании."
        )
    },
)
apply_global_styles()

try:
    init_db()
except sqlite3.Error:
    st.error("Не удалось подготовить локальную базу данных в папке data.")
    st.stop()

audit_page = st.Page(
    render_audit_page,
    title="Новый аудит",
    default=True,
)


def history_page_renderer() -> None:
    render_history_page(audit_page)


history_page = st.Page(history_page_renderer, title="История")
navigation = st.navigation(
    [audit_page, history_page],
    position="sidebar",
)
navigation.run()
