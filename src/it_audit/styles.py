"""Общая визуальная система Streamlit-интерфейса."""

import streamlit as st

GLOBAL_CSS = """
<style>
:root {
  --audit-navy: #10182f;
  --audit-blue: #123fad;
  --audit-blue-soft: #edf3ff;
  --audit-muted: #667085;
  --audit-line: #d9dee8;
  --audit-soft: #f6f8fc;
  --audit-red: #e53935;
  --audit-amber: #f59e0b;
}

html, body, [class*="st-"] { font-family: Arial, "Helvetica Neue", sans-serif; }
.stApp { background: #ffffff; color: var(--audit-navy); }
[data-testid="stHeader"] { background: rgba(255,255,255,.96); }
[data-testid="stToolbar"] { right: 1rem; }
[data-testid="stMainBlockContainer"] {
  max-width: 1120px;
  padding-top: 2.25rem;
  padding-bottom: 4rem;
}
[data-testid="stSidebar"] {
  background: #ffffff;
  border-right: 1px solid var(--audit-line);
  min-width: 220px;
}
[data-testid="stSidebarContent"] { padding-top: .75rem; }
[data-testid="stSidebarNav"] { padding-top: 0; }
[data-testid="stSidebarNav"]::before {
  content: "ИТ-Аудит";
  display: block;
  color: var(--audit-navy);
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -.03em;
  padding: .8rem 1rem 1.45rem;
  margin-bottom: .55rem;
  border-bottom: 1px solid var(--audit-line);
}
[data-testid="stSidebarNav"] a {
  min-height: 44px;
  border-radius: 0;
  font-size: .94rem;
  color: var(--audit-navy);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: var(--audit-blue-soft);
  color: var(--audit-blue);
  font-weight: 700;
  border-left: 3px solid var(--audit-blue);
}
[data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stExpandSidebarButton"] span,
[data-testid="stExpandSidebarButton"] button span,
[data-testid="stSidebarCollapseButton"] button span { display: none; }
[data-testid="stExpandSidebarButton"]::before,
[data-testid="stExpandSidebarButton"] button::before {
  content: "☰";
  color: var(--audit-navy);
  font-size: 1.25rem;
  line-height: 1;
}
[data-testid="stSidebarCollapseButton"] button::before {
  content: "×";
  color: var(--audit-navy);
  font-size: 1.4rem;
  line-height: 1;
}
h1, h2, h3 { color: var(--audit-navy); letter-spacing: -.025em; }
h1 { font-size: 2rem !important; line-height: 1.18 !important; margin-bottom: .35rem !important; }
h2 { font-size: 1.35rem !important; line-height: 1.3 !important; }
p, label, input, button { font-size: .94rem; }
.audit-company {
  color: var(--audit-blue);
  font-size: 1.08rem;
  font-weight: 750;
  margin: .2rem 0 .3rem;
}
.audit-meta { color: var(--audit-muted); font-size: .86rem; margin-bottom: 1.2rem; }
.audit-section-rule { border-top: 1px solid var(--audit-line); margin: 1.3rem 0; }
.progress-meta {
  display: flex;
  justify-content: flex-end;
  color: var(--audit-navy);
  font-size: .85rem;
  margin: .2rem 0 .45rem;
}
.progress-track { height: 4px; background: #e6e9ef; overflow: hidden; margin-bottom: 1.65rem; }
.progress-fill { height: 100%; background: var(--audit-blue); transition: width .18s ease; }
.question-copy { color: var(--audit-navy); line-height: 1.5; padding: .55rem 0; }
.question-copy strong { color: var(--audit-blue); margin-right: .35rem; }
[data-testid="stForm"] { border: 0; padding: 0; }
[data-testid="stForm"] [data-testid="stHorizontalBlock"]:has([role="radiogroup"]) {
  border-bottom: 1px solid var(--audit-line);
  padding: .45rem 0 .75rem;
}
[role="radiogroup"] { justify-content: flex-end; gap: .15rem; }
[role="radiogroup"] label { min-width: 34px; justify-content: center; }
.stButton > button, .stDownloadButton > button {
  min-height: 42px;
  font-size: .9rem;
  font-weight: 700;
  border-radius: 4px;
}
[data-testid="stPopoverButton"] [data-testid="stIconMaterial"] { display: none; }
.score-layout {
  display: grid;
  grid-template-columns: minmax(220px, .8fr) minmax(360px, 1.25fr);
  gap: 2.8rem;
  align-items: stretch;
  margin: 1.15rem 0 2rem;
}
.score-values { border-right: 1px solid var(--audit-line); padding-right: 2.2rem; }
.score-value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 54px;
  gap: 1rem;
}
.score-value-row strong { color: var(--audit-blue); font-size: 1.15rem; }
.score-value-row strong.critical { color: var(--audit-red); }
.bar-chart { padding: .1rem 0; }
.bar-row {
  display: grid;
  grid-template-columns: 150px 1fr 34px;
  align-items: center;
  gap: .75rem;
  min-height: 54px;
  font-size: .78rem;
}
.bar-track { height: 26px; background: var(--audit-soft); position: relative; }
.bar-fill { height: 100%; background: var(--audit-blue); }
.bar-fill.critical { background: var(--audit-red); }
.risk-table { width: 100%; border-collapse: collapse; margin: .6rem 0 1.8rem; }
.risk-table th {
  color: var(--audit-muted);
  font-size: .72rem;
  font-weight: 700;
  text-align: left;
  padding: .65rem .7rem;
  border-bottom: 1px solid var(--audit-line);
  text-transform: uppercase;
  letter-spacing: .035em;
}
.risk-table td { padding: .85rem .7rem; border-bottom: 1px solid var(--audit-line); }
.table-scroll { width: 100%; overflow-x: auto; margin: .7rem 0 1.25rem; }
.history-table {
  width: 100%; min-width: 650px; border-collapse: collapse; font-size: .9rem;
}
.history-table th {
  color: var(--audit-muted);
  font-size: .72rem;
  font-weight: 700;
  text-align: left;
  padding: .65rem .7rem;
  border: 1px solid var(--audit-line);
  background: #f7f8fb;
  text-transform: uppercase;
  letter-spacing: .035em;
}
.history-table td { padding: .72rem .7rem; border: 1px solid var(--audit-line); }
.history-table strong { color: var(--audit-blue); }
.comparison-table { min-width: 520px; }
.comparison-table .delta-up { color: #16803a; font-weight: 750; }
.comparison-table .delta-down { color: var(--audit-red); font-weight: 750; }
.risk-mark { width: 5px; padding: 0 !important; }
.risk-mark.high { background: var(--audit-red); }
.risk-mark.medium { background: var(--audit-amber); }
.risk-mark.low { background: var(--audit-blue); }
.severity { font-weight: 750; }
.severity.high { color: var(--audit-red); }
.severity.medium { color: #c36b00; }
.severity.low { color: var(--audit-blue); }
.empty-state {
  border: 1px solid var(--audit-line);
  padding: 1rem 1.1rem;
  color: var(--audit-muted);
}
.roadmap {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.7rem;
  border-top: 2px solid var(--audit-line);
  margin: 1.4rem 0 2rem;
  padding-top: 1.2rem;
}
.roadmap-item { position: relative; }
.roadmap-item::before {
  content: "";
  position: absolute;
  width: 13px;
  height: 13px;
  border: 2px solid var(--audit-blue);
  background: #fff;
  border-radius: 50%;
  top: -1.68rem;
  left: 0;
}
.roadmap-item:first-child::before { background: var(--audit-blue); }
.roadmap-day { color: var(--audit-blue); font-weight: 800; margin-bottom: .3rem; }
.roadmap-title { font-weight: 700; margin-bottom: .45rem; }
.roadmap-actions { color: var(--audit-muted); font-size: .83rem; line-height: 1.45; }
.overall-note { color: var(--audit-muted); font-size: .84rem; margin-top: -.3rem; }
[data-testid="stDataFrame"] { border: 1px solid var(--audit-line); }

@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] { padding: 1.4rem 1rem 3rem; }
  h1 { font-size: 1.65rem !important; }
  .score-layout { grid-template-columns: 1fr; gap: 1.2rem; }
  .score-values { border-right: 0; border-bottom: 1px solid var(--audit-line); padding: 0 0 .7rem; }
  .bar-row { grid-template-columns: 112px 1fr 30px; gap: .45rem; }
  .risk-table th:nth-child(3), .risk-table td:nth-child(3) { display: none; }
  .roadmap { grid-template-columns: 1fr; gap: 1.55rem; border-top: 0; padding-left: 1rem; }
  .roadmap-item { border-left: 2px solid var(--audit-line); padding-left: 1rem; }
  .roadmap-item::before { top: 0; left: -8px; }
  [role="radiogroup"] { justify-content: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
</style>
"""


def apply_global_styles() -> None:
    """Подключает согласованные дизайн-токены один раз за rerun."""

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
