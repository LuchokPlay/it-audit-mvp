#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_REF="${IT_AUDIT_GITHUB_REF:-main}"
readonly SOURCE_DIR="${IT_AUDIT_SOURCE_DIR:-/opt/it-audit-source}"
readonly TARGET_DIR="${IT_AUDIT_INSTALL_DIR:-/opt/it-audit}"
readonly UPDATE_COMMAND="/usr/local/bin/it-audit-update"

log() {
    printf '\n[ИТ-Аудит] %s\n' "$*"
}

fail() {
    printf '\n[ИТ-Аудит] Ошибка: %s\n' "$*" >&2
    exit 1
}

require_environment() {
    [[ "${EUID}" -eq 0 ]] || fail "Запустите обновление через sudo: sudo it-audit-update"
    [[ -d "${SOURCE_DIR}/.git" ]] || \
        fail "Не найден Git checkout в ${SOURCE_DIR}. Выполните GitHub-установку заново."
    [[ -f "${TARGET_DIR}/compose.yaml" ]] || \
        fail "Не найдена установленная копия в ${TARGET_DIR}."
    [[ -f "${TARGET_DIR}/deploy/Caddyfile.runtime" ]] || \
        fail "Не найден runtime-конфиг Caddy; обновление остановлено, чтобы не потерять вход."
    command -v rsync >/dev/null 2>&1 || fail "Не найден rsync."
    command -v docker >/dev/null 2>&1 || fail "Не найден Docker."
    docker compose version >/dev/null 2>&1 || fail "Не найден Docker Compose."
    [[ -z "$(git -C "${SOURCE_DIR}" status --porcelain)" ]] || \
        fail "В ${SOURCE_DIR} есть локальные изменения. Обновление их не перезапишет."
}

fetch_release() {
    local previous_commit new_commit
    previous_commit="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"

    log "Получаю свежую версию из GitHub (${REPOSITORY_REF})."
    git -C "${SOURCE_DIR}" fetch --depth=1 origin "${REPOSITORY_REF}"
    new_commit="$(git -C "${SOURCE_DIR}" rev-parse FETCH_HEAD)"
    git -C "${SOURCE_DIR}" checkout --detach "${new_commit}"

    if [[ "${previous_commit}" == "${new_commit}" ]]; then
        log "Новых commit нет; проверяю текущую установку."
    else
        log "Версия изменена: ${previous_commit:0:12} -> ${new_commit:0:12}."
    fi
}

sync_application() {
    log "Синхронизирую код без изменения SQLite и пароля."
    rsync -a --delete \
        --exclude='.git/' \
        --exclude='.venv/' \
        --exclude='data/' \
        --exclude='dist/' \
        --exclude='deploy/Caddyfile.runtime' \
        "${SOURCE_DIR}/" "${TARGET_DIR}/"

    install -d -m 0750 -o 10001 -g 10001 "${TARGET_DIR}/data"
}

install_update_command() {
    install -m 0755 "${SOURCE_DIR}/deploy/update.sh" "${UPDATE_COMMAND}.new"
    mv -f "${UPDATE_COMMAND}.new" "${UPDATE_COMMAND}"
}

restart_application() {
    local app_id status=""

    log "Пересобираю и запускаю контейнеры."
    cd "${TARGET_DIR}"
    docker compose config --quiet
    docker compose up -d --build --remove-orphans

    app_id="$(docker compose ps -q app)"
    [[ -n "${app_id}" ]] || fail "Контейнер приложения не создан."

    for _ in {1..30}; do
        status="$(docker inspect --format '{{.State.Health.Status}}' "${app_id}")"
        [[ "${status}" == "healthy" ]] && break
        if [[ "${status}" == "unhealthy" ]]; then
            docker compose logs --tail=100 app >&2
            fail "Новая версия не прошла healthcheck."
        fi
        sleep 2
    done

    [[ "${status}" == "healthy" ]] || fail "Приложение не стало готовым за 60 секунд."
}

main() {
    require_environment
    fetch_release
    sync_application
    restart_application
    install_update_command

    log "Обновление завершено. SQLite и настройки входа сохранены."
}

main "$@"
