"""Генерация автономного печатного HTML-отчёта."""

from __future__ import annotations

from datetime import datetime
from html import escape

from it_audit.catalog import CATEGORIES
from it_audit.models import AuditResult


def _format_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return escape(value)
    return parsed.strftime("%d.%m.%Y %H:%M")


def _score_rows(result: AuditResult) -> str:
    rows = []
    for category in CATEGORIES:
        score = result.scores[category.key]
        color = "#e53935" if score < 40 else "#123fad"
        rows.append(
            f"""
            <div class="score-row">
              <div class="score-label">{escape(category.title)}</div>
              <div class="score-track">
                <div class="score-fill" style="width:{score}%;background:{color}"></div>
              </div>
              <strong>{score}</strong>
            </div>
            """
        )
    return "".join(rows)


def _risk_rows(result: AuditResult) -> str:
    if not result.risks:
        return '<p class="empty">Существенных рисков по результатам анкеты не выявлено.</p>'
    return "".join(
        f"""
        <tr>
          <td>{escape(risk.title)}</td>
          <td>
            <span class="severity severity-{risk.severity.lower()}">
              {escape(risk.severity)}
            </span>
          </td>
          <td>{risk.horizon_days} дней</td>
        </tr>
        """
        for risk in result.risks
    )


def _roadmap_columns(result: AuditResult) -> str:
    return "".join(
        f"""
        <article class="roadmap-item">
          <div class="roadmap-day">{item.horizon_days} дней</div>
          <h3>{escape(item.title)}</h3>
          <ul>{''.join(f'<li>{escape(action)}</li>' for action in item.actions)}</ul>
        </article>
        """
        for item in result.roadmap
    )


def render_html_report(result: AuditResult) -> str:
    """Возвращает автономный UTF-8 HTML без внешних ресурсов и скриптов."""

    company = escape(result.profile.name)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ИТ-Аудит — {company}</title>
  <style>
    :root {{ color-scheme: light; --navy:#10182f; --blue:#123fad; --muted:#667085;
      --line:#d9dee8; --soft:#f6f8fc; --red:#e53935; --amber:#f59e0b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--navy); background:#fff; font:15px/1.55 Arial,sans-serif; }}
    main {{ width:min(980px, calc(100% - 48px)); margin:48px auto 72px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:28px; margin-bottom:34px; }}
    .brand {{ color:var(--blue); font-size:18px; font-weight:800; margin-bottom:28px; }}
    h1 {{ font-size:34px; line-height:1.15; margin:0 0 8px; }}
    h2 {{ font-size:22px; margin:36px 0 16px; }}
    h3 {{ font-size:15px; margin:8px 0; }}
    .meta {{ color:var(--muted); display:flex; gap:24px; flex-wrap:wrap; }}
    .overall {{ display:flex; align-items:baseline; gap:12px; margin-top:24px; }}
    .overall strong {{ color:var(--blue); font-size:42px; line-height:1; }}
    .score-row {{ display:grid; grid-template-columns:220px 1fr 42px; gap:16px;
      align-items:center; padding:11px 0; }}
    .score-track {{ height:14px; background:#edf0f6; overflow:hidden; }}
    .score-fill {{ height:100%; }}
    table {{ border-collapse:collapse; width:100%; }}
    th, td {{ text-align:left; padding:13px 10px; border-bottom:1px solid var(--line); }}
    th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .severity {{ font-weight:700; }}
    .severity-высокий {{ color:var(--red); }} .severity-средний {{ color:#c36b00; }}
    .severity-низкий {{ color:var(--blue); }}
    .roadmap {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:28px;
      border-top:2px solid var(--line); padding-top:20px; }}
    .roadmap-day {{ color:var(--blue); font-weight:800; }}
    ul {{ padding-left:18px; margin:8px 0 0; }}
    .disclaimer {{ margin-top:42px; padding:16px 18px; background:var(--soft);
      color:var(--muted); font-size:12px; }}
    @media (max-width:700px) {{
      main {{ width:min(100% - 28px, 980px); margin-top:28px; }}
      .score-row {{ grid-template-columns:1fr 42px; }}
      .score-track {{ grid-column:1 / -1; grid-row:2; }}
      .roadmap {{ grid-template-columns:1fr; }}
    }}
    @media print {{ main {{ width:100%; margin:0; }} .disclaimer {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="brand">ИТ-Аудит</div>
    <h1>Результаты аудита</h1>
    <div class="meta">
      <strong>{company}</strong>
      <span>{escape(result.profile.industry)}</span>
      <span>{escape(result.profile.employee_range)} сотрудников</span>
      <span>{_format_date(result.created_at)}</span>
    </div>
    <div class="overall">
      <strong>{result.overall_score}</strong>
      <span>{escape(result.maturity)} уровень</span>
    </div>
  </header>
  <section><h2>Оценки по направлениям</h2>{_score_rows(result)}</section>
  <section><h2>Ключевые риски</h2><table>
    <thead><tr><th>Риск</th><th>Уровень</th><th>Горизонт</th></tr></thead>
    <tbody>{_risk_rows(result)}</tbody>
  </table></section>
  <section>
    <h2>План 30 / 60 / 90 дней</h2>
    <div class="roadmap">{_roadmap_columns(result)}</div>
  </section>
  <p class="disclaimer">
    Демонстрационная методика. Результаты предназначены для первичного обсуждения
    и не заменяют полноценное обследование.
  </p>
</main>
</body>
</html>"""
