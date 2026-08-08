# ИТ-Аудит: правила работы Codex

## Назначение

Однопользовательское Streamlit-приложение для локального запуска и небольшого VPS.

## Команды

- Установка: `python -m pip install -r requirements-dev.txt`
- Запуск: `python -m streamlit run app.py`
- Тесты: `pytest -q`
- Линтер: `ruff check .`
- Сборка VPS-инсталлятора: `powershell -File deploy/build-bundle.ps1`
- Развёртывание на Ubuntu 22.04: `sudo bash ./it-audit-installer.sh`
- Развёртывание из GitHub: `curl -fsSL https://raw.githubusercontent.com/LuchokPlay/it-audit-mvp/main/deploy/bootstrap.sh | sudo bash`
- Обновление VPS: `sudo it-audit-update`

## Архитектурные правила

- UI находится в `app.py` и `src/it_audit/pages.py`.
- Расчёты, SQLite и HTML-отчёт не должны зависеть от Streamlit.
- Все SQL-запросы параметризованы.
- Все пользовательские значения экранируются перед вставкой в HTML.
- Не добавлять внешние API и новые production-зависимости без необходимости.
- Локальный запуск остаётся без авторизации; на VPS доступ защищает Caddy.
- Пароли и `deploy/Caddyfile.runtime` никогда не коммитятся.
- Каталог вопросов и рекомендаций меняется только вместе с тестами расчётов.

## Definition of Done

- `pytest -q` и `ruff check .` проходят.
- Основной сценарий проверен в браузере на desktop и mobile.
- Интерфейс сопоставлен с утверждённым макетом.
- README содержит достаточные инструкции для запуска в чистом окружении.
- Deployment-тесты подтверждают, что Streamlit не опубликован напрямую на порту 8501.
