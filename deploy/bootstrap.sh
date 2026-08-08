#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_URL="${IT_AUDIT_REPOSITORY_URL:-https://github.com/LuchokPlay/it-audit-mvp.git}"
readonly REPOSITORY_REF="${IT_AUDIT_GITHUB_REF:-main}"
readonly SOURCE_DIR="${IT_AUDIT_SOURCE_DIR:-/opt/it-audit-source}"
readonly UPDATE_COMMAND="/usr/local/bin/it-audit-update"

log() {
    printf '\n[ИТ-Аудит] %s\n' "$*"
}

fail() {
    printf '\n[ИТ-Аудит] Ошибка: %s\n' "$*" >&2
    exit 1
}

require_root() {
    [[ "${EUID}" -eq 0 ]] || fail "Запустите установку через sudo."
}

install_git() {
    log "Устанавливаю Git и корневые сертификаты."
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates git
}

checkout_repository() {
    if [[ ! -e "${SOURCE_DIR}" ]]; then
        log "Клонирую ${REPOSITORY_URL}, ветка ${REPOSITORY_REF}."
        git clone --filter=blob:none --single-branch --branch "${REPOSITORY_REF}" \
            "${REPOSITORY_URL}" "${SOURCE_DIR}"
        return
    fi

    [[ -d "${SOURCE_DIR}/.git" ]] || \
        fail "${SOURCE_DIR} уже существует, но не является Git-репозиторием."
    [[ -z "$(git -C "${SOURCE_DIR}" status --porcelain)" ]] || \
        fail "В ${SOURCE_DIR} есть локальные изменения. Уберите их перед обновлением."

    log "Обновляю исходники из ${REPOSITORY_REF}."
    git -C "${SOURCE_DIR}" fetch --depth=1 origin "${REPOSITORY_REF}"
    git -C "${SOURCE_DIR}" checkout --detach FETCH_HEAD
}

main() {
    require_root
    install_git
    checkout_repository

    bash "${SOURCE_DIR}/deploy/install.sh"
    install -m 0755 "${SOURCE_DIR}/deploy/update.sh" "${UPDATE_COMMAND}.new"
    mv -f "${UPDATE_COMMAND}.new" "${UPDATE_COMMAND}"

    log "GitHub-обновления настроены. Следующее обновление: sudo it-audit-update"
}

main "$@"
