#!/usr/bin/env bash
set -Eeuo pipefail

readonly TARGET_DIR="${IT_AUDIT_INSTALL_DIR:-/opt/it-audit}"
readonly LOGIN_NAME="audit"
readonly CADDY_IMAGE="caddy:2.11.4-alpine"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
SOURCE_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly SOURCE_DIR

log() {
    printf '\n[ИТ-Аудит] %s\n' "$*"
}

fail() {
    printf '\n[ИТ-Аудит] Ошибка: %s\n' "$*" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        fail "Запустите установщик через sudo: sudo bash deploy/install.sh"
    fi
}

check_os() {
    [[ -r /etc/os-release ]] || fail "Не удалось определить операционную систему."
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "22.04" ]] || \
        fail "Поддерживается Ubuntu 22.04, обнаружено: ${PRETTY_NAME:-неизвестно}."
}

install_docker() {
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl rsync

    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        log "Docker и Compose уже установлены."
        systemctl enable --now docker
        return
    fi

    log "Устанавливаю Docker Engine и Docker Compose из официального apt-репозитория."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    local architecture codename
    architecture="$(dpkg --print-architecture)"
    codename="${UBUNTU_CODENAME:-${VERSION_CODENAME}}"
    cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${codename}
Components: stable
Architectures: ${architecture}
Signed-By: /etc/apt/keyrings/docker.asc
EOF

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    docker compose version >/dev/null
}

copy_application() {
    log "Размещаю приложение в ${TARGET_DIR}."
    install -d -m 0755 "${TARGET_DIR}"

    if [[ "${SOURCE_DIR}" != "${TARGET_DIR}" ]]; then
        rsync -a --delete \
            --exclude='.git/' \
            --exclude='.venv/' \
            --exclude='data/' \
            --exclude='dist/' \
            --exclude='deploy/Caddyfile.runtime' \
            "${SOURCE_DIR}/" "${TARGET_DIR}/"
    fi

    install -d -m 0750 -o 10001 -g 10001 "${TARGET_DIR}/data"
}

detect_host() {
    local detected_host
    detected_host="${IT_AUDIT_HOST:-}"
    if [[ -z "${detected_host}" ]]; then
        detected_host="$(curl -4 -fsS --max-time 8 https://api.ipify.org || true)"
    fi
    if [[ -z "${detected_host}" ]]; then
        detected_host="$(hostname -I | awk '{print $1}')"
    fi
    [[ -n "${detected_host}" ]] || fail "Не удалось определить IP. Задайте IT_AUDIT_HOST."

    local entered_host
    read -r -p "Публичный IP VPS [${detected_host}]: " entered_host
    IT_AUDIT_HOST="${entered_host:-${detected_host}}"
    if [[ ! "${IT_AUDIT_HOST}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        fail "Ожидался IPv4-адрес, получено: ${IT_AUDIT_HOST}"
    fi
    local octet
    IFS='.' read -r -a octets <<< "${IT_AUDIT_HOST}"
    for octet in "${octets[@]}"; do
        ((10#${octet} >= 0 && 10#${octet} <= 255)) || \
            fail "Некорректный IPv4-адрес: ${IT_AUDIT_HOST}"
    done
    export IT_AUDIT_HOST
}

read_password() {
    local password confirmation
    while true; do
        read -r -s -p "Пароль для входа на сайт: " password
        printf '\n'
        [[ ${#password} -ge 12 ]] || {
            printf 'Пароль должен содержать не менее 12 символов.\n' >&2
            continue
        }
        read -r -s -p "Повторите пароль: " confirmation
        printf '\n'
        [[ "${password}" == "${confirmation}" ]] || {
            printf 'Пароли не совпадают. Попробуйте ещё раз.\n' >&2
            continue
        }
        break
    done

    local secret_file password_hash
    secret_file="$(mktemp)"
    chmod 600 "${secret_file}"
    trap 'rm -f "${secret_file:-}"' RETURN
    printf 'PASSWORD=%s\n' "${password}" > "${secret_file}"
    unset password confirmation

    password_hash="$(docker run --rm --env-file "${secret_file}" \
        --entrypoint sh "${CADDY_IMAGE}" \
        -c 'caddy hash-password --plaintext "$PASSWORD"')"
    rm -f "${secret_file}"
    trap - RETURN
    [[ -n "${password_hash}" ]] || fail "Не удалось сформировать хеш пароля."
    IT_AUDIT_PASSWORD_HASH="${password_hash}"
    export IT_AUDIT_PASSWORD_HASH
}

write_caddy_config() {
    local config_path
    config_path="${TARGET_DIR}/deploy/Caddyfile.runtime"
    umask 077
    cat > "${config_path}" <<EOF
{
    admin off
}

https://${IT_AUDIT_HOST} {
    tls internal
    encode zstd gzip

    basic_auth {
        ${LOGIN_NAME} ${IT_AUDIT_PASSWORD_HASH}
    }

    header {
        -Server
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }

    reverse_proxy app:8501
}
EOF
    unset IT_AUDIT_PASSWORD_HASH
}

start_application() {
    log "Собираю и запускаю контейнеры."
    cd "${TARGET_DIR}"
    docker compose config --quiet
    docker compose up -d --build --remove-orphans

    local app_id status
    app_id="$(docker compose ps -q app)"
    [[ -n "${app_id}" ]] || fail "Контейнер приложения не создан."

    for _ in {1..30}; do
        status="$(docker inspect --format '{{.State.Health.Status}}' "${app_id}")"
        if [[ "${status}" == "healthy" ]]; then
            break
        fi
        if [[ "${status}" == "unhealthy" ]]; then
            docker compose logs --tail=100 app >&2
            fail "Проверка работоспособности приложения завершилась ошибкой."
        fi
        sleep 2
    done
    [[ "${status}" == "healthy" ]] || fail "Приложение не стало готовым за 60 секунд."

    local http_status=""
    for _ in {1..15}; do
        http_status="$(curl -k -sS -o /dev/null -w '%{http_code}' \
            "https://${IT_AUDIT_HOST}/" || true)"
        [[ "${http_status}" == "401" ]] && break
        sleep 2
    done
    [[ "${http_status}" == "401" ]] || {
        docker compose logs --tail=100 caddy >&2
        fail "Защищённый HTTPS-вход не ответил ожидаемым кодом 401."
    }
}

main() {
    require_root
    check_os
    install_docker
    copy_application
    detect_host
    read_password
    write_caddy_config
    start_application

    cat <<EOF

[ИТ-Аудит] Установка завершена.
Адрес: https://${IT_AUDIT_HOST}
Логин: ${LOGIN_NAME}
Пароль: тот, который вы только что ввели

При первом открытии браузер предупредит о локальном сертификате Caddy.
Проверьте отпечаток и разрешите переход только для этого IP.
SQLite хранится в ${TARGET_DIR}/data и сохраняется при обновлениях.
EOF
}

main "$@"
