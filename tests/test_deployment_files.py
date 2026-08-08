import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compose_exposes_only_reverse_proxy() -> None:
    compose = read("compose.yaml")

    assert '"80:80"' in compose
    assert '"443:443"' in compose
    assert '"8501:8501"' not in compose
    assert "./data:/app/data" in compose
    assert "condition: service_healthy" in compose


def test_caddy_requires_encrypted_authentication() -> None:
    caddyfile = read("deploy/Caddyfile.example")

    assert "https://__IT_AUDIT_HOST__" in caddyfile
    assert "tls internal" in caddyfile
    assert "basic_auth" in caddyfile
    assert "__IT_AUDIT_PASSWORD_HASH__" in caddyfile
    assert "reverse_proxy app:8501" in caddyfile


def test_installer_does_not_contain_a_default_password() -> None:
    installer = read("deploy/install.sh")

    assert 'read -r -s -p "Пароль для входа на сайт: "' in installer
    assert "caddy hash-password" in installer
    assert "Caddyfile.runtime" in installer
    assert re.search(r"^\s*(?:readonly\s+)?password=", installer, re.MULTILINE) is None


def test_installer_checks_caddy_without_public_ip_loopback() -> None:
    installer = read("deploy/install.sh")

    assert '--resolve "${IT_AUDIT_HOST}:443:127.0.0.1"' in installer


def test_container_runs_application_as_non_root() -> None:
    dockerfile = read("Dockerfile")

    assert "USER audit" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--server.address=0.0.0.0" in dockerfile
    assert "python:3.14.6-slim" in dockerfile
