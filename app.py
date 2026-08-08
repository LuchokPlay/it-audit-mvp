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

navigation = st.navigation(
    [
        st.Page(
            render_audit_page,
            title="Новый аудит",
            default=True,
        ),
        st.Page(render_history_page, title="История"),
    ],
    position="sidebar",
)
navigation.run()
