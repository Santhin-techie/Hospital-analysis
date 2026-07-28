"""
MASTER DASHBOARD (Pixel-Accurate HTML Version)
------------------------------------------------------------------------
This embeds the REAL HTML/CSS design directly (like an iframe) instead of
using Streamlit's native widgets -- so it looks exactly like the mockup,
not an approximation.

Navigation: plain Streamlit buttons in the sidebar (left, native look).
Content area: pixel-accurate embedded HTML (right, matches your mockup),
rebuilt with real data every time you click a different module.

Run with:
    streamlit run master_dashboard_ultra.py
"""

import streamlit as st
import pandas as pd
import os
import streamlit.components.v1 as components

st.set_page_config(page_title="HRI System — Master Console", layout="wide")

# ---------------------------------------------------------------------------
# PATHS + DATA CONTRACT
# ---------------------------------------------------------------------------
FINAL_DIR = r"C:\Users\santhin kumar k\mini\data\final"
SIM_DIR = r"C:\Users\santhin kumar k\mini\data\simulated"

MODULE_FILES = {
    "bed":      {"name": "Bed Occupancy Forecasting",       "file": "bed_occupancy_forecast.csv",
                 "cols": ["hospital_id","department","date","predicted_occupancy","capacity"], "icon": "🛏️"},
    "medicine": {"name": "Medicine Stock & Expiry",          "file": "medicine_stock_status.csv",
                 "cols": ["hospital_id","medicine_name","stock_level","days_to_shortage","expiry_risk"], "icon": "💊"},
    "blood":    {"name": "Blood Bank Intelligence",          "file": "blood_coverage_results.csv",
                 "cols": ["hospital_id","blood_group","stock_units","forecasted_demand","status"], "icon": "🩸"},
    "coverage": {"name": "Coverage & Referral Intelligence", "file": "chennai_coverage_results.csv",
                 "cols": ["zone_id","dominant_area","risk_score","coverage_status","nearest_capable_hospital"], "icon": "🚨"},
}

def find_module_file(fname):
    for d in [FINAL_DIR, SIM_DIR]:
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    if fname == "chennai_coverage_results.csv":
        p = os.path.join(SIM_DIR, "chennai_coverage_results_APPROX.csv")
        if os.path.exists(p):
            return p
    return None

if "active_page" not in st.session_state:
    st.session_state.active_page = "overview"

# ---------------------------------------------------------------------------
# SIDEBAR — plain functional nav (this part stays native Streamlit)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏥 HRI SYSTEM")
    st.caption("Master Console")
    st.markdown("---")
    if st.button("◈  Dashboard", width='stretch'):
        st.session_state.active_page = "overview"
    st.caption("MODULES")
    for key, m in MODULE_FILES.items():
        if st.button(f"{m['icon']}  {m['name']}", width='stretch', key=f"nav_{key}"):
            st.session_state.active_page = key

# ---------------------------------------------------------------------------
# SHARED HTML HEAD/CSS -- reused by every page for visual consistency
# ---------------------------------------------------------------------------
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
:root{
  --bg-deep:#0B0E23; --bg-mid:#131735;
  --panel:rgba(255,255,255,0.04); --panel-border:rgba(255,255,255,0.08);
  --ink:#F1F3FA; --ink-dim:#8891B5; --ink-mid:#B4BADB;
  --violet:#7C5CFF; --violet-glow:rgba(124,92,255,0.45);
  --blue:#3EA6FF; --green:#35E0A1; --amber:#FFB238; --red:#FF5C7A; --pink:#FF5CA8;
  --sans:'Plus Jakarta Sans',sans-serif; --mono:'JetBrains Mono',monospace;
}
*{box-sizing:border-box; margin:0; padding:0;}
body{
  font-family:var(--sans); color:var(--ink);
  background:
    radial-gradient(circle at 15% 0%, rgba(124,92,255,0.18), transparent 40%),
    radial-gradient(circle at 85% 15%, rgba(62,166,255,0.14), transparent 45%),
    linear-gradient(180deg, var(--bg-deep), var(--bg-mid));
  padding:26px 30px;
}
.page-title{font-size:24px; font-weight:800; margin-bottom:4px;}
.breadcrumb{font-size:11.5px; color:var(--ink-dim); margin-bottom:18px;}
.breadcrumb b{color:var(--ink);}
.stat-grid{display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:22px;}
.stat-card{background:var(--panel); border:1px solid var(--panel-border); border-radius:16px; padding:20px; position:relative; overflow:hidden;}
.stat-label{font-size:11px; color:var(--ink-dim); margin-bottom:6px;}
.stat-value{font-size:22px; font-weight:800;}
.stat-icon{width:38px; height:38px; border-radius:11px; display:flex; align-items:center; justify-content:center; font-size:16px; float:right;}
.glass-panel{background:var(--panel); border:1px solid var(--panel-border); border-radius:18px; padding:22px; margin-bottom:18px;}
.panel-title{font-size:14.5px; font-weight:700; margin-bottom:4px;}
.panel-sub{font-size:11px; color:var(--ink-dim); margin-bottom:14px;}
.mod-row{display:flex; align-items:center; justify-content:space-between; padding:13px 4px; border-bottom:1px solid var(--panel-border);}
.mod-row:last-child{border-bottom:none;}
.mod-left{display:flex; align-items:center; gap:13px;}
.mod-icon{width:38px; height:38px; border-radius:11px; display:flex; align-items:center; justify-content:center; font-size:16px;}
.mod-name{font-size:13px; font-weight:700;}
.mod-desc{font-size:10.5px; color:var(--ink-dim); margin-top:2px;}
.mod-status{font-family:var(--mono); font-size:9.5px; font-weight:700; padding:5px 10px; border-radius:7px;}
.mod-status.ready{background:rgba(53,224,161,0.15); color:var(--green);}
.mod-status.pending{background:rgba(255,178,56,0.15); color:var(--amber);}
table.data-tbl{width:100%; border-collapse:collapse; font-size:12px;}
table.data-tbl th{text-align:left; font-family:var(--mono); font-size:9.5px; text-transform:uppercase; letter-spacing:0.5px; color:var(--ink-dim); padding-bottom:10px; border-bottom:1px solid var(--panel-border); font-weight:600;}
table.data-tbl td{padding:10px 8px 10px 0; border-bottom:1px solid var(--panel-border);}
.badge{font-family:var(--mono); font-size:9.5px; padding:3px 9px; border-radius:12px; font-weight:700;}
.badge.green{background:rgba(53,224,161,0.15); color:var(--green);}
.badge.red{background:rgba(255,92,122,0.15); color:var(--red);}
.empty-box{background:var(--panel); border:1px dashed var(--panel-border); border-radius:16px; padding:50px; text-align:center; color:var(--ink-dim);}
.empty-title{font-size:15px; font-weight:700; color:var(--ink-mid); margin-bottom:8px;}
.empty-code{font-family:var(--mono); font-size:11px; background:rgba(255,255,255,0.05); padding:10px 14px; border-radius:8px; display:inline-block; margin-top:10px;}
"""

# ---------------------------------------------------------------------------
# PAGE: OVERVIEW
# ---------------------------------------------------------------------------
def render_overview():
    ready = {k: find_module_file(m["file"]) is not None for k, m in MODULE_FILES.items()}
    ready_count = sum(ready.values())

    rows_html = ""
    colors = {"bed": ("#7C5CFF","#3EA6FF"), "medicine": ("#3EA6FF","#35E0A1"),
              "blood": ("#FF5C7A","#FF5CA8"), "coverage": ("#35E0A1","#1BA97A")}
    for key, m in MODULE_FILES.items():
        c1, c2 = colors[key]
        status_class = "ready" if ready[key] else "pending"
        status_label = "✓ READY" if ready[key] else "PENDING"
        rows_html += f"""
        <div class="mod-row">
          <div class="mod-left">
            <div class="mod-icon" style="background:linear-gradient(135deg,{c1},{c2});">{m['icon']}</div>
            <div><div class="mod-name">{m['name']}</div><div class="mod-desc">{m['file']}</div></div>
          </div>
          <div class="mod-status {status_class}">{status_label}</div>
        </div>"""

    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="breadcrumb">Dashboards / <b>Master Overview</b></div>
      <div class="page-title">Emergency Readiness Overview</div>
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#7C5CFF,#3EA6FF);">🏥</div><div class="stat-label">Hospitals Monitored</div><div class="stat-value">12</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#FF5CA8,#FF5C7A);">📍</div><div class="stat-label">Modules Ready</div><div class="stat-value">{ready_count}/4</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#35E0A1,#1BA97A);">📋</div><div class="stat-label">Data Contract</div><div class="stat-value">Locked</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#FFB238,#E08A1E);">⚡</div><div class="stat-label">Sync Status</div><div class="stat-value">Live</div></div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Module Integration Status</div>
        <div class="panel-sub">shared data contract · hospital_id linked across all 4</div>
        {rows_html}
      </div>
    </body></html>"""
    components.html(html, height=520, scrolling=False)

# ---------------------------------------------------------------------------
# PAGE: MODULE DETAIL (works for all 4 module keys)
# ---------------------------------------------------------------------------
def render_module(key):
    m = MODULE_FILES[key]
    path = find_module_file(m["file"])

    if not path:
        html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
          <div class="breadcrumb">Dashboards / Modules / <b>{m['name']}</b></div>
          <div class="page-title">{m['icon']} {m['name']}</div>
          <div class="empty-box">
            <div class="empty-title">⏳ Waiting for {m['name']} data</div>
            Save <b>{m['file']}</b> into the shared folder:
            <div class="empty-code">{FINAL_DIR}</div>
            <div style="margin-top:14px; font-size:11px;">Required columns: {', '.join(m['cols'])}</div>
          </div>
        </body></html>"""
        components.html(html, height=420, scrolling=False)
        return

    df = pd.read_csv(path)

    display_df = df.head(15)
    header_html = "".join(f"<th>{c}</th>" for c in display_df.columns)
    body_html = ""
    for _, row in display_df.iterrows():
        cells = ""
        for c in display_df.columns:
            val = row[c]
            if c in ("coverage_status", "status"):
                badge_class = "green" if str(val).upper() in ("COVERED","OK","STABLE") else "red"
                cells += f'<td><span class="badge {badge_class}">{val}</span></td>'
            else:
                cells += f"<td>{val}</td>"
        body_html += f"<tr>{cells}</tr>"

    stat_html = ""
    if key == "coverage" and "coverage_status" in df.columns:
        n_gap = int((df["coverage_status"] == "GAP").sum())
        n_covered = int((df["coverage_status"] == "COVERED").sum())
        stat_html = f"""
        <div class="stat-grid" style="grid-template-columns:repeat(2,1fr);">
          <div class="stat-card"><div class="stat-label">Zones — Gap</div><div class="stat-value" style="color:var(--red);">{n_gap}</div></div>
          <div class="stat-card"><div class="stat-label">Zones — Covered</div><div class="stat-value" style="color:var(--green);">{n_covered}</div></div>
        </div>"""

    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="breadcrumb">Dashboards / Modules / <b>{m['name']}</b></div>
      <div class="page-title">{m['icon']} {m['name']}</div>
      {stat_html}
      <div class="glass-panel">
        <div class="panel-title">Data Preview</div>
        <div class="panel-sub">{len(df)} rows total · showing first {len(display_df)} · source: {os.path.basename(path)}</div>
        <table class="data-tbl">
          <thead><tr>{header_html}</tr></thead>
          <tbody>{body_html}</tbody>
        </table>
      </div>
    </body></html>"""
    components.html(html, height=650, scrolling=True)

# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
page = st.session_state.active_page
if page == "overview":
    render_overview()
else:
    render_module(page)