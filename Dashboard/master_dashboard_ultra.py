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
import random
from datetime import datetime

st.set_page_config(page_title="HRI System — Master Console", layout="wide")

# ---------------------------------------------------------------------------
# GLOBAL SHELL STYLING — makes the OUTER Streamlit app (sidebar, page
# background, native widgets like the map) match the embedded HTML's dark
# glass theme exactly. Without this, the embedded console looks fine but
# everything native (map, toggle, captions) sits on a plain white/default
# background — that mismatch is what makes it feel "bolted on" instead of
# one continuous product.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

    .stApp {
        background:
            radial-gradient(circle at 15% 0%, rgba(124,92,255,0.18), transparent 40%),
            radial-gradient(circle at 85% 15%, rgba(62,166,255,0.14), transparent 45%),
            linear-gradient(180deg, #0B0E23, #131735) !important;
    }

    /* Sidebar matches the same dark theme instead of default light/gray */
    section[data-testid="stSidebar"] {
        background: rgba(255,255,255,0.03);
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] * { color: #F1F3FA !important; }
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small { color: #8891B5 !important; }

    /* Remove the default big top padding so content sits flush like a real dashboard */
    .block-container { padding-top: 1.6rem; padding-bottom: 2rem; }

    /* Native widgets (toggle, captions, warnings) restyled to match the dark theme */
    .stMarkdown, .stCaption, p, label, span { color: #DCE3EC; }
    .stToggle label { color: #F1F3FA !important; }
    div[data-testid="stMetricValue"] { color: #F1F3FA; }

    /* Native map container gets a matching dark card frame instead of floating on blank space */
    div[data-testid="stDeckGlJsonChart"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
    }

    /* Kill the harsh white flash of default Streamlit alert/warning boxes */
    div[data-testid="stAlert"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        color: #DCE3EC;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# PATHS + DATA CONTRACT
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_DIR = os.path.join(BASE_DIR, "..", "data", "final")
SIM_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")
os.makedirs(FINAL_DIR, exist_ok=True)

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

ZONES_PATH = find_module_file("chennai_hotspot_zones.csv")
HOSPITALS_PATH = find_module_file("chennai_hospitals.csv")

if "active_page" not in st.session_state:
    st.session_state.active_page = "overview"

# ---------------------------------------------------------------------------
# GLOBAL LIVE SIMULATION MODE (10-min refresh)
# ---------------------------------------------------------------------------
# IMPORTANT: this simulates realistic fluctuation on top of your real base
# data -- it does NOT connect to a real hospital server. No public API exists
# for live hospital occupancy/stock data in India; a genuine version would
# require official data-sharing partnership with a hospital network or state
# health department, which is out of scope here. This is the honest,
# disclosed stand-in: same numbers you'd see live, refreshed periodically,
# clearly labeled as simulated.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏥 HRI SYSTEM")
    st.caption("Master Console")
    st.markdown("---")
    live_mode = st.toggle("🔴 Live Simulation (10 min)", value=False, key="global_live_mode")
    if live_mode:
        st.caption("Simulating periodic live fluctuation on real base data. Not a real hospital feed.")
    st.markdown("---")
    if st.button("◈  Dashboard", width='stretch'):
        st.session_state.active_page = "overview"
    st.caption("MODULES")
    for key, m in MODULE_FILES.items():
        if st.button(f"{m['icon']}  {m['name']}", width='stretch', key=f"nav_{key}"):
            st.session_state.active_page = key

if live_mode:
    try:
        from streamlit_autorefresh import st_autorefresh
        refresh_count = st_autorefresh(interval=600_000, limit=None, key="master_live_refresh")  # 10 min
    except ImportError:
        st.sidebar.warning("Run `pip install streamlit-autorefresh` to enable Live Simulation.")
        refresh_count = 0
else:
    refresh_count = 0

def jitter_value(value, pct=0.08, seed=0):
    """Small bounded random fluctuation, seeded by refresh count so it's
    stable between reruns but changes each 10-min refresh cycle."""
    rng = random.Random(seed + int(value * 100))
    return round(value * (1 + rng.uniform(-pct, pct)), 1)

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
.ticker-wrap{background:rgba(0,0,0,0.25); border:1px solid var(--panel-border); border-radius:12px; overflow:hidden; white-space:nowrap; padding:9px 0; margin-bottom:18px;}
.ticker-track{display:inline-flex; animation:scroll-left 26s linear infinite;}
.ticker-item{font-family:var(--mono); font-size:11px; padding:0 26px; display:inline-flex; align-items:center; gap:8px; color:var(--ink-mid); border-right:1px solid var(--panel-border);}
.ticker-item.crit{color:var(--red);}
@keyframes scroll-left{0%{transform:translateX(0);} 100%{transform:translateX(-50%);}}
.console-body{display:grid; grid-template-columns:200px 1fr; gap:0;}
.radar-box{padding:10px 20px 10px 4px; border-right:1px solid var(--panel-border); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px;}
.radar{width:150px; height:150px; border-radius:50%; border:1px solid var(--panel-border); position:relative; background:repeating-radial-gradient(circle, transparent 0, transparent 24px, var(--panel-border) 25px);}
.radar-sweep{position:absolute; inset:0; border-radius:50%; background:conic-gradient(from 0deg, rgba(53,224,161,0.4), transparent 60deg); animation:sweep 3.2s linear infinite;}
@keyframes sweep{100%{transform:rotate(360deg);}}
.radar-dot{position:absolute; width:7px; height:7px; border-radius:50%;}
.radar-center{position:absolute; top:50%; left:50%; width:6px; height:6px; background:var(--green); border-radius:50%; transform:translate(-50%,-50%);}
.radar-caption{font-family:var(--mono); font-size:9.5px; color:var(--ink-dim);}
.console-main{padding:14px 22px;}
.cc-line{font-family:var(--mono); font-size:12px; margin-bottom:9px;}
.cc-label{color:var(--ink-dim);} .cc-val{color:var(--ink); font-weight:700;}
.alert-grid{display:flex; flex-direction:column; gap:9px;}
.a-card{background:rgba(0,0,0,0.15); border:1px solid var(--panel-border); border-left:3px solid var(--panel-border); border-radius:10px; padding:13px 16px; display:flex; justify-content:space-between; align-items:center; gap:16px;}
.a-card.crit{border-left-color:var(--red);} .a-card.ok{border-left-color:var(--green);}
.a-left{display:flex; gap:12px; align-items:flex-start;}
.a-rank{font-family:var(--mono); font-size:10.5px; font-weight:700; color:var(--ink-dim); background:rgba(255,255,255,0.05); border:1px solid var(--panel-border); border-radius:6px; padding:2px 7px; align-self:flex-start; margin-top:1px;}
.a-title{font-weight:700; font-size:12.5px; margin-bottom:3px;}
.a-detail{font-size:11px; color:var(--ink-mid);}
.a-action{font-family:var(--mono); font-size:9.5px; padding:6px 10px; border-radius:6px; border:1px solid var(--panel-border); color:var(--ink-mid); white-space:nowrap;}
.hero-grid{display:grid; grid-template-columns:1.3fr 1fr; gap:16px; margin-bottom:20px;}
.hero-map-card{background:var(--panel); border:1px solid var(--panel-border); border-radius:18px; padding:16px; height:260px; position:relative; overflow:hidden;}
.hero-map-label{position:absolute; top:14px; left:14px; font-family:var(--mono); font-size:10px; color:var(--ink-mid); background:rgba(0,0,0,0.35); padding:6px 12px; border-radius:10px; z-index:2;}
.hero-info-card{background:var(--panel); border:1px solid var(--panel-border); border-radius:18px; padding:20px 22px; display:flex; flex-direction:column; justify-content:center;}
.hero-stat-line{display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--panel-border); font-size:12px;}
.hero-stat-line:last-child{border-bottom:none;}
.hero-stat-label{color:var(--ink-dim);}
.hero-stat-val{font-weight:700; color:var(--ink);}
"""

# ---------------------------------------------------------------------------
# PAGE: OVERVIEW
# ---------------------------------------------------------------------------
def render_overview():
    ready = {k: find_module_file(m["file"]) is not None for k, m in MODULE_FILES.items()}
    ready_count = sum(ready.values())

    # ---- Real zone-map hero (replaces any decorative image with actual data) ----
    hero_map_svg = ""
    hero_stats_html = ""
    if ZONES_PATH and HOSPITALS_PATH:
        zones_df = pd.read_csv(ZONES_PATH)
        coverage_path = find_module_file(MODULE_FILES["coverage"]["file"])
        if coverage_path:
            cov_df = pd.read_csv(coverage_path)
            nearest_col = "nearest_capable_min" if "nearest_capable_min" in cov_df.columns else "nearest_capable_min_APPROX"
            cov_sorted = cov_df.sort_values("risk_score", ascending=False).reset_index(drop=True)

            lat_min, lat_max = zones_df["centroid_lat"].min(), zones_df["centroid_lat"].max()
            lon_min, lon_max = zones_df["centroid_lon"].min(), zones_df["centroid_lon"].max()

            def norm(lat, lon):
                x = 30 + (lon - lon_min) / (lon_max - lon_min + 1e-9) * 260
                y = 25 + (1 - (lat - lat_min) / (lat_max - lat_min + 1e-9)) * 220
                return round(x, 1), round(y, 1)

            dots = ""
            for _, row in zones_df.iterrows():
                x, y = norm(row["centroid_lat"], row["centroid_lon"])
                status_row = cov_sorted[cov_sorted["zone_id"] == row["zone_id"]]
                is_gap = len(status_row) and status_row["coverage_status"].values[0] == "GAP"
                color = "var(--red)" if is_gap else "var(--green)"
                size = 5 + min(9, row["risk_score"] / 28)
                dots += f'<circle cx="{x}" cy="{y}" r="{size+7:.1f}" fill="{color}" opacity="0.15"/><circle cx="{x}" cy="{y}" r="{size:.1f}" fill="{color}" opacity="0.9"/>'
            hero_map_svg = f'<svg viewBox="0 0 320 270" width="100%" height="100%">{dots}</svg>'

            top = cov_sorted.iloc[0]
            n_covered = int((cov_sorted["coverage_status"] == "COVERED").sum())
            n_total = len(cov_sorted)
            display_risk = jitter_value(float(top['risk_score']), seed=refresh_count) if live_mode else top['risk_score']
            hero_stats_html = f"""
            <div class="hero-stat-line"><span class="hero-stat-label">Highest risk zone</span><span class="hero-stat-val">{top['zone_id']} — {top.get('dominant_area','')}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">Risk score</span><span class="hero-stat-val">{display_risk}{' 🔴' if live_mode else ''}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">Zones covered</span><span class="hero-stat-val">{n_covered} / {n_total}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">Nearest capable hospital</span><span class="hero-stat-val">{top.get('nearest_capable_hospital','N/A')}</span></div>
            """

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

    hero_section = ""
    if hero_map_svg:
        hero_section = f"""
        <div class="hero-grid">
          <div class="hero-map-card">
            <div class="hero-map-label">Live Zone Network · Chennai Metro</div>
            {hero_map_svg}
          </div>
          <div class="hero-info-card">
            <div class="panel-title">Network Snapshot</div>
            {hero_stats_html}
          </div>
        </div>"""

    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="breadcrumb">Dashboards / <b>Master Overview</b></div>
      <div class="page-title">Emergency Readiness Overview</div>
      {hero_section}
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
    components.html(html, height=520 + (260 if hero_map_svg else 0), scrolling=False)

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
# PAGE: COVERAGE & REFERRAL INTELLIGENCE
# Lightweight summary here + a link out to the FULL original console,
# which runs as its own separate Streamlit app (module4_dashboard_full.py)
# so your exact original design renders untouched, with zero interference
# from the master dashboard's shared theme.
# ---------------------------------------------------------------------------
MODULE4_APP_URL = "http://localhost:8502"  # change this if you run it on a different port

def render_coverage_rich():
    m = MODULE_FILES["coverage"]
    coverage_path = find_module_file(m["file"])

    if not (coverage_path and ZONES_PATH and HOSPITALS_PATH):
        render_module("coverage")
        return

    coverage = pd.read_csv(coverage_path)
    zones = pd.read_csv(ZONES_PATH)
    hospitals = pd.read_csv(HOSPITALS_PATH)

    nearest_col = "nearest_capable_min" if "nearest_capable_min" in coverage.columns else "nearest_capable_min_APPROX"
    zones_lookup = zones.set_index("zone_id")[["dominant_area", "centroid_lat", "centroid_lon"]]
    cov = coverage.sort_values("risk_score", ascending=False).reset_index(drop=True).join(zones_lookup, on="zone_id")
    cov.insert(0, "priority_rank", range(1, len(cov) + 1))

    n_gap = int((cov["coverage_status"] == "GAP").sum())
    n_covered = int((cov["coverage_status"] == "COVERED").sum())
    top = cov.iloc[0]
    display_travel = jitter_value(float(top[nearest_col]), seed=refresh_count) if live_mode else top[nearest_col]

    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="breadcrumb">Dashboards / Modules / <b>Coverage & Referral Intelligence</b>{'  ·  🔴 LIVE SIM' if live_mode else ''}</div>
      <div class="page-title">🚨 Coverage & Referral Intelligence</div>
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#FF5C7A,#FF5CA8);">📍</div><div class="stat-label">Zones — Gap</div><div class="stat-value">{n_gap}</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#35E0A1,#1BA97A);">✅</div><div class="stat-label">Zones — Covered</div><div class="stat-value">{n_covered}</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#7C5CFF,#3EA6FF);">🏥</div><div class="stat-label">Hospitals</div><div class="stat-value">{len(hospitals)}</div></div>
        <div class="stat-card"><div class="stat-icon" style="background:linear-gradient(135deg,#FFB238,#E08A1E);">📊</div><div class="stat-label">Total Accidents</div><div class="stat-value">{int(zones['accident_count'].sum())}</div></div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Highest Priority Zone (quick preview)</div>
        <div class="panel-sub">{top['zone_id']} — {top['dominant_area']} · risk score {top['risk_score']} · {display_travel} min to {top.get('nearest_capable_hospital','N/A')} · status {top['coverage_status']}</div>
      </div>
    </body></html>"""
    components.html(html, height=430, scrolling=False)

    # ---- Link out to the full, original, untouched Module 4 console ----
    st.markdown(f"""
    <div style="background:linear-gradient(160deg, rgba(124,92,255,0.18), rgba(62,166,255,0.10));
                border:1px solid rgba(124,92,255,0.35); border-radius:18px;
                padding:26px 30px; margin-top:18px; display:flex;
                justify-content:space-between; align-items:center;">
        <div>
            <div style="font-size:15px; font-weight:700; color:#F1F3FA; margin-bottom:6px;">
                🖥️ Full Module 4 Console — Live Radar, Ticker & Route Map
            </div>
            <div style="font-size:12px; color:#B4BADB; max-width:520px; line-height:1.5;">
                Your original design (animated radar sweep, scrolling alert ticker, live
                simulation mode, and real travel-time route lines) runs as its own
                dedicated app, exactly as built — not compressed to fit this theme.
            </div>
        </div>
        <a href="{MODULE4_APP_URL}" target="_blank" style="text-decoration:none;">
            <div style="background:#F1F3FA; color:#0B0E23; font-weight:700; font-size:13px;
                        padding:13px 22px; border-radius:12px; white-space:nowrap;">
                Open Full Console →
            </div>
        </a>
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"Opens in a new tab at {MODULE4_APP_URL} — make sure module4_dashboard_full.py is running separately (see instructions below).")

    with st.expander("How to run the full console alongside this dashboard"):
        st.code(
            "# In a second terminal, from your Dashboard folder:\n"
            "streamlit run module4_dashboard_full.py --server.port 8502",
            language="bash"
        )
        st.markdown("Keep both terminals running — this master dashboard on port **8501**, and the full Module 4 console on port **8502**. The button above links directly to it.")

# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
page = st.session_state.active_page
if page == "overview":
    render_overview()
elif page == "coverage":
    render_coverage_rich()
else:
    render_module(page)