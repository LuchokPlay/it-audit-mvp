# ruff: noqa: E501
"""Контекст отрасли и масштаба для оценки рисков и рекомендаций."""

from __future__ import annotations

from dataclasses import dataclass

from it_audit.models import CompanyProfile

CATEGORY_KEYS = ("infrastructure", "security", "automation", "management")
CATEGORY_TITLES = {
    "infrastructure": "Инфраструктура",
    "security": "Информационная безопасность",
    "automation": "Автоматизация",
    "management": "Управление ИТ",
}

SUPPORTED_INDUSTRIES = (
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

SUPPORTED_EMPLOYEE_RANGES = ("1–50", "51–100", "101–250", "251–1000", "Более 1000")
LEGACY_EMPLOYEE_RANGES = {"До 50": "1–50", "50–100": "51–100"}

INDUSTRY_WEIGHTS: dict[str, dict[str, float]] = {
    "Финансы": {"infrastructure": 1.15, "security": 1.35, "automation": 0.85, "management": 1.10},
    "Ритейл": {"infrastructure": 1.20, "security": 1.15, "automation": 1.10, "management": 0.90},
    "Производство": {
        "infrastructure": 1.35,
        "security": 1.10,
        "automation": 0.95,
        "management": 1.00,
    },
    "Транспорт и логистика": {
        "infrastructure": 1.30,
        "security": 1.05,
        "automation": 1.10,
        "management": 0.95,
    },
    "Профессиональные услуги": {
        "infrastructure": 0.90,
        "security": 1.25,
        "automation": 1.00,
        "management": 1.10,
    },
    "Государственный сектор": {
        "infrastructure": 1.10,
        "security": 1.30,
        "automation": 0.85,
        "management": 1.15,
    },
    "Информационные технологии": {
        "infrastructure": 1.00,
        "security": 1.25,
        "automation": 1.25,
        "management": 0.90,
    },
    "Телекоммуникации": {
        "infrastructure": 1.35,
        "security": 1.20,
        "automation": 1.00,
        "management": 0.95,
    },
    "Энергетика и ЖКХ": {
        "infrastructure": 1.40,
        "security": 1.25,
        "automation": 0.80,
        "management": 1.05,
    },
    "Строительство и недвижимость": {
        "infrastructure": 1.10,
        "security": 1.05,
        "automation": 1.00,
        "management": 0.95,
    },
    "Здравоохранение": {
        "infrastructure": 1.30,
        "security": 1.35,
        "automation": 0.80,
        "management": 1.05,
    },
    "Образование": {
        "infrastructure": 1.00,
        "security": 1.20,
        "automation": 0.90,
        "management": 1.00,
    },
    "Другое": {key: 1.00 for key in CATEGORY_KEYS},
}

SIZE_WEIGHTS: dict[str, dict[str, float]] = {
    "1–50": {"infrastructure": 1.00, "security": 1.10, "automation": 0.85, "management": 0.85},
    "51–100": {"infrastructure": 1.00, "security": 1.10, "automation": 0.95, "management": 0.95},
    "101–250": {"infrastructure": 1.00, "security": 1.10, "automation": 1.00, "management": 1.00},
    "251–1000": {"infrastructure": 1.10, "security": 1.20, "automation": 1.05, "management": 1.15},
    "Более 1000": {
        "infrastructure": 1.15,
        "security": 1.25,
        "automation": 1.05,
        "management": 1.25,
    },
}

INDUSTRY_ASSETS = {
    "Финансы": "платёжный контур, ДБО, финансовые и персональные данные",
    "Ритейл": "кассы, интернет-магазин, ERP и платёжные интеграции",
    "Производство": "АСУ ТП, производственное оборудование, MES и ERP",
    "Транспорт и логистика": "TMS/WMS, маршрутизацию, склады и мобильные рабочие места",
    "Профессиональные услуги": "клиентские данные, проектные пространства и удалённый доступ",
    "Государственный сектор": "государственные информационные системы и данные граждан",
    "Информационные технологии": "репозитории кода, CI/CD, облачные среды и секреты",
    "Телекоммуникации": "сетевое ядро, биллинг и системы мониторинга услуг",
    "Энергетика и ЖКХ": "объекты критической инфраструктуры, АСУ ТП и диспетчеризацию",
    "Строительство и недвижимость": "проектные данные, площадки, подрядчиков и системы доступа",
    "Здравоохранение": "медицинские системы, диагностическое оборудование и данные пациентов",
    "Образование": "учётные записи учащихся, образовательные платформы и персональные данные",
    "Другое": "критичные бизнес-системы и данные компании",
}

SIZE_GOVERNANCE = {
    "1–50": "Закрепить одного владельца и дублёра, используя единый простой реестр контроля.",
    "51–100": "Назначить владельца процесса и вести ежемесячный контроль в едином реестре.",
    "101–250": "Разделить ответственность по функциям и ежемесячно сводить статус руководству.",
    "251–1000": "Автоматизировать контроль, назначить владельцев по подразделениям и единые KPI.",
    "Более 1000": "Разделить контроль по бизнес-единицам и консолидировать его на корпоративном уровне.",
}


@dataclass(frozen=True)
class CompoundRiskRule:
    trigger_question_ids: tuple[str, ...]
    title: str
    action: str


INDUSTRY_RISK_RULES: dict[str, CompoundRiskRule] = {
    "Финансы": CompoundRiskRule(
        ("security_access", "security_mfa", "security_incidents"),
        "Компрометация учётной записи может затронуть финансовые операции и регулируемые данные",
        "Провести сценарную проверку захвата привилегированной учётной записи и закрыть разрывы MFA, журналирования и реагирования.",
    ),
    "Ритейл": CompoundRiskRule(
        ("infra_monitoring", "infra_backup", "automation_integrations"),
        "Сбой кассового или интеграционного контура может остановить продажи сразу в нескольких каналах",
        "Проверить восстановление кассового контура и платёжных интеграций, затем настроить единый мониторинг доступности продаж.",
    ),
    "Производство": CompoundRiskRule(
        ("infra_monitoring", "infra_backup", "security_incidents"),
        "ИТ-инцидент может перейти в незапланированный простой производства",
        "Провести учение по отказу производственного контура с участием ИТ, технологов и ответственных за АСУ ТП.",
    ),
    "Транспорт и логистика": CompoundRiskRule(
        ("infra_monitoring", "automation_integrations", "infra_backup"),
        "Недоступность TMS/WMS или обмена данными может сорвать маршруты и складские операции",
        "Проверить резервный сценарий работы склада и диспетчеризации при недоступности TMS/WMS и интеграций.",
    ),
    "Профессиональные услуги": CompoundRiskRule(
        ("security_access", "security_mfa", "management_vendors"),
        "Недостаточное разделение доступов повышает риск раскрытия данных нескольких клиентов",
        "Разделить клиентские пространства, пересмотреть внешние доступы и установить срок автоматического отзыва прав.",
    ),
    "Государственный сектор": CompoundRiskRule(
        ("security_access", "security_incidents", "infra_backup"),
        "Инцидент может нарушить оказание государственной услуги и затронуть данные граждан",
        "Проверить непрерывность приоритетной госуслуги и порядок уведомления ответственных при инциденте.",
    ),
    "Информационные технологии": CompoundRiskRule(
        ("automation_delivery", "security_access", "security_patching"),
        "Недостаточный контроль цепочки поставки ПО повышает риск выпуска уязвимого изменения",
        "Добавить в CI/CD проверку зависимостей, секретов и обязательное подтверждение критичных изменений.",
    ),
    "Телекоммуникации": CompoundRiskRule(
        ("infra_monitoring", "infra_lifecycle", "security_incidents"),
        "Отказ сетевого элемента может привести к массовой деградации услуг без быстрого восстановления",
        "Провести учение по отказу узла сети и проверить эскалацию, резервирование и информирование пользователей.",
    ),
    "Энергетика и ЖКХ": CompoundRiskRule(
        ("infra_monitoring", "security_incidents", "infra_lifecycle"),
        "Кибер- или технический инцидент может повлиять на непрерывность критической инфраструктуры",
        "Отдельно проверить сегментацию АСУ ТП, резервное управление и совместное реагирование ИТ и технологических служб.",
    ),
    "Строительство и недвижимость": CompoundRiskRule(
        ("security_access", "automation_integrations", "management_vendors"),
        "Распределённые площадки и подрядчики создают неконтролируемые точки доступа к проектным данным",
        "Инвентаризировать доступы подрядчиков и ввести сроки действия прав для площадок и проектных систем.",
    ),
    "Здравоохранение": CompoundRiskRule(
        ("infra_backup", "security_access", "security_incidents"),
        "Недоступность медицинской системы или утечка данных может повлиять на оказание помощи пациентам",
        "Проверить автономный сценарий работы клинического подразделения и восстановление медицинских данных в установленный срок.",
    ),
    "Образование": CompoundRiskRule(
        ("security_access", "security_mfa", "infra_backup"),
        "Массовые и сезонные учётные записи повышают риск захвата доступа и потери учебных данных",
        "Настроить жизненный цикл учётных записей учащихся и преподавателей и проверить восстановление учебной платформы.",
    ),
}

SIZE_RISK_RULES: dict[str, CompoundRiskRule] = {
    "1–50": CompoundRiskRule(
        ("security_incidents", "management_vendors"),
        "Критичные знания и административные доступы могут быть сосредоточены у одного специалиста",
        "Назначить дублёра, зафиксировать аварийные контакты и хранить инструкции и доступы в контролируемом месте.",
    ),
    "51–100": CompoundRiskRule(
        ("infra_assets", "security_access"),
        "Рост числа устройств и сотрудников может опережать учёт активов и отзыв доступов",
        "Связать реестр сотрудников, оборудования и доступов с единым процессом приёма, перевода и увольнения.",
    ),
    "101–250": CompoundRiskRule(
        ("automation_integrations", "management_service"),
        "Разрозненные процессы подразделений могут создавать очереди, дублирование данных и ручные обходы",
        "Выбрать межфункциональный процесс с наибольшими потерями и назначить единого владельца улучшения.",
    ),
    "251–1000": CompoundRiskRule(
        ("infra_monitoring", "management_service", "management_kpi"),
        "Масштаб ИТ-сервисов может превышать возможности ручной координации и неформальных SLA",
        "Сформировать каталог критичных сервисов, назначить владельцев и автоматизировать контроль SLA и инцидентов.",
    ),
    "Более 1000": CompoundRiskRule(
        ("security_access", "management_vendors", "management_kpi"),
        "Децентрализация доступов, поставщиков и ответственности может скрывать системные нарушения контроля",
        "Ввести корпоративные контрольные показатели и регулярные выборочные проверки по бизнес-единицам.",
    ),
}


def normalize_employee_range(value: str) -> str:
    """Возвращает актуальное имя диапазона для старых и новых профилей."""

    return LEGACY_EMPLOYEE_RANGES.get(value, value)


def category_weights(profile: CompanyProfile) -> dict[str, float]:
    """Объединяет отраслевые и размерные веса направлений."""

    industry = INDUSTRY_WEIGHTS.get(profile.industry, INDUSTRY_WEIGHTS["Другое"])
    size = SIZE_WEIGHTS.get(
        normalize_employee_range(profile.employee_range), SIZE_WEIGHTS["101–250"]
    )
    return {key: round(industry[key] * size[key], 2) for key in CATEGORY_KEYS}


def calculate_context_score(
    scores: dict[str, int | None], profile: CompanyProfile
) -> tuple[int, dict[str, float]]:
    """Считает взвешенную оценку только по применимым направлениям."""

    weights = category_weights(profile)
    applicable = [(key, score) for key, score in scores.items() if score is not None]
    weighted_sum = sum(score * weights[key] for key, score in applicable)
    total_weight = sum(weights[key] for key, _ in applicable)
    return round(weighted_sum / total_weight), weights


def contextual_action(action: str, category: str, profile: CompanyProfile) -> str:
    """Дополняет базовое действие отраслевым охватом и форматом управления."""

    assets = INDUSTRY_ASSETS.get(profile.industry, INDUSTRY_ASSETS["Другое"])
    size = normalize_employee_range(profile.employee_range)
    governance = SIZE_GOVERNANCE.get(size, SIZE_GOVERNANCE["101–250"])
    focus_by_category = {
        "infrastructure": f"Первый охват: {assets}.",
        "security": f"В первую очередь проверить доступ и защиту для: {assets}.",
        "automation": f"Приоритет автоматизации: операции и данные вокруг {assets}.",
        "management": f"Назначить владельцев и показатели для: {assets}.",
    }
    return f"{action.rstrip('.')}. {focus_by_category[category]} {governance}"


def context_description(category: str, profile: CompanyProfile, weight: float) -> str:
    """Объясняет, почему конкретный риск получил такой приоритет."""

    size = normalize_employee_range(profile.employee_range)
    return (
        f"Контекст: {profile.industry}, {size} сотрудников; "
        f"вес направления «{CATEGORY_TITLES[category]}» — ×{weight:.2f}."
    )
