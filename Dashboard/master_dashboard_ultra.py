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
    @import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Stencil:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    .stApp {
        background:
            repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(255,255,255,0.012) 40px),
            repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(255,255,255,0.012) 40px),
            #1E2420 !important;
    }

    /* Sidebar -- same flat board color, no violet gradient */
    section[data-testid="stSidebar"] {
        background: #191F1B;
        border-right: 1px solid #3A423C;
    }
    section[data-testid="stSidebar"] * { color: #EDE7D9 !important; font-family: 'IBM Plex Sans', sans-serif; }
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {
        color: #8B9187 !important; font-family: 'IBM Plex Mono', monospace !important;
        letter-spacing: 0.6px; text-transform: uppercase; font-size: 10px !important;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        font-family: 'Big Shoulders Stencil', sans-serif !important; letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] hr { border-color: #3A423C; }

    /* Sidebar nav buttons -- bordered plates with left accent, feel clickable */
    section[data-testid="stSidebar"] div.stButton > button {
        background: #20261F;
        border: 1px solid #3A423C;
        border-left: 3px solid #5C9484;
        border-radius: 0;
        color: #EDE7D9 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 12.5px;
        text-align: left;
        padding: 11px 14px;
        transition: background 0.15s ease, border-left-color 0.15s ease, transform 0.1s ease;
    }
    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: #2A322A;
        border-left-color: #D69A3E;
        transform: translateX(2px);
    }
    section[data-testid="stSidebar"] div.stButton > button:active {
        border-left-color: #C1443A;
    }

    /* Toggle switch recolored to match the amber/board accent instead of blue */
    section[data-testid="stSidebar"] [data-baseweb="toggle"] { background-color: #3A423C !important; }
    section[data-testid="stSidebar"] [aria-checked="true"][data-baseweb="toggle"] { background-color: #D69A3E !important; }

    .block-container { padding-top: 1.6rem; padding-bottom: 2rem; }

    .stMarkdown, .stCaption, p, label, span { color: #EDE7D9; }
    div[data-testid="stMetricValue"] { color: #EDE7D9; font-family: 'Big Shoulders Stencil', sans-serif; }

    /* Native map container -- flat border, no rounded glass look */
    div[data-testid="stDeckGlJsonChart"] {
        border-radius: 0;
        overflow: hidden;
        border: 1px solid #3A423C;
    }

    /* Alert/warning boxes match the board's flat panel style */
    div[data-testid="stAlert"] {
        background: #252C26;
        border: 1px solid #3A423C;
        border-radius: 0;
        color: #EDE7D9;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 12.5px;
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
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Stencil:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');
:root{
  --board:#1E2420; --board-raised:#252C26; --board-line:#3A423C;
  --chalk:#EDE7D9; --chalk-dim:#8B9187; --chalk-mid:#B6BCAF;
  --red:#C1443A; --amber:#D69A3E; --green:#5C9484;
  --stencil:'Big Shoulders Stencil',sans-serif; --sans:'IBM Plex Sans',sans-serif; --mono:'IBM Plex Mono',monospace;
}
*{box-sizing:border-box; margin:0; padding:0;}
@keyframes fadeIn{ from{opacity:0;} to{opacity:1;} }
@keyframes tickFlicker{ 0%,100%{opacity:1;} 92%{opacity:1;} 94%{opacity:0.6;} 96%{opacity:1;} }
body{
  font-family:var(--sans); color:var(--chalk);
  background:
    repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(255,255,255,0.015) 40px),
    repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(255,255,255,0.015) 40px),
    var(--board);
  padding:28px 34px;
}
.page-title{
  font-family:var(--stencil); font-weight:700; font-size:34px; letter-spacing:1.5px;
  text-transform:uppercase; margin-bottom:2px; color:var(--chalk);
}
.breadcrumb{font-family:var(--mono); font-size:11px; color:var(--chalk-dim); margin-bottom:20px; letter-spacing:0.3px;}
.breadcrumb b{color:var(--chalk);}

/* ===== MANIFEST STAT ROW (replaces card grid) ===== */
.stat-grid{
  display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr; gap:1px;
  background:var(--board-line); border:1px solid var(--board-line); margin-bottom:20px;
}
.stat-card{ background:var(--board-raised); padding:20px 22px; position:relative; transition:background 0.15s ease; }
.stat-card:hover{ background:#2A322A; }
.stat-card:first-child{ display:flex; flex-direction:column; justify-content:center; }
.stat-label{ font-family:var(--mono); font-size:10px; color:var(--chalk-dim); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px; }
.stat-value{ font-family:var(--stencil); font-size:38px; font-weight:700; line-height:1; color:var(--chalk); }
.stat-icon{ display:none; }

/* ===== SUPPLY MANIFEST PANEL (replaces glass-panel card) ===== */
.glass-panel{ background:var(--board-raised); border:1px solid var(--board-line); padding:24px 26px; margin-bottom:18px; }
.panel-title{ font-family:var(--stencil); font-size:17px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:3px; }
.panel-sub{ font-family:var(--mono); font-size:10.5px; color:var(--chalk-dim); margin-bottom:16px; }

.mod-row{
  display:flex; align-items:center; justify-content:space-between; padding:12px 4px;
  border-bottom:1px dotted var(--board-line); transition:background 0.15s ease;
}
.mod-row:hover{ background:rgba(255,255,255,0.02); }
.mod-row:last-child{border-bottom:none;}
.mod-left{ display:flex; align-items:center; gap:14px; flex:1; }
.mod-icon{
  width:32px; height:32px; border:1px solid var(--board-line); background:var(--board);
  display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;
}
.mod-name{ font-size:13.5px; font-weight:600; }
.mod-name::after{ content:''; display:inline-block; flex:1; margin:0 8px; border-bottom:1px dotted var(--board-line); min-width:40px; }
.mod-desc{ font-family:var(--mono); font-size:10px; color:var(--chalk-dim); }
.mod-status{ font-family:var(--mono); font-size:10px; font-weight:600; padding:3px 10px; letter-spacing:0.5px; border:1px solid; flex-shrink:0; }
.mod-status.ready{ color:var(--green); border-color:var(--green); }
.mod-status.pending{ color:var(--amber); border-color:var(--amber); }

table.data-tbl{width:100%; border-collapse:collapse; font-size:12.5px;}
table.data-tbl th{text-align:left; font-family:var(--mono); font-size:9.5px; text-transform:uppercase; letter-spacing:0.6px; color:var(--chalk-dim); padding-bottom:10px; border-bottom:1px solid var(--board-line); font-weight:600;}
table.data-tbl td{padding:10px 8px 10px 0; border-bottom:1px dotted var(--board-line);}
.badge{font-family:var(--mono); font-size:9.5px; padding:3px 9px; font-weight:600; border:1px solid;}
.badge.green{color:var(--green); border-color:var(--green);}
.badge.red{color:var(--red); border-color:var(--red);}
.empty-box{background:var(--board-raised); border:1px dashed var(--board-line); padding:50px; text-align:center; color:var(--chalk-dim);}
.empty-title{font-family:var(--stencil); font-size:18px; text-transform:uppercase; color:var(--chalk-mid); margin-bottom:8px;}
.empty-code{font-family:var(--mono); font-size:11px; background:rgba(0,0,0,0.3); padding:10px 14px; display:inline-block; margin-top:10px;}

/* ===== STATUS TICKER (styled like a teletype line, not a rounded pill strip) ===== */
.ticker-wrap{background:rgba(0,0,0,0.35); border-top:1px solid var(--board-line); border-bottom:1px solid var(--board-line); overflow:hidden; white-space:nowrap; padding:8px 0; margin-bottom:20px;}
.ticker-track{display:inline-flex; animation:scroll-left 26s linear infinite;}
.ticker-item{font-family:var(--mono); font-size:10.5px; padding:0 24px; display:inline-flex; align-items:center; gap:8px; color:var(--chalk-dim); border-right:1px solid var(--board-line);}
.ticker-item.crit{color:var(--red); animation:tickFlicker 3s infinite;}
@keyframes scroll-left{0%{transform:translateX(0);} 100%{transform:translateX(-50%);}}

.console-body{display:grid; grid-template-columns:200px 1fr; gap:0;}
.radar-box{padding:10px 20px 10px 4px; border-right:1px solid var(--board-line); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px;}
.radar{width:150px; height:150px; border-radius:50%; border:1px solid var(--board-line); position:relative; background:repeating-radial-gradient(circle, transparent 0, transparent 24px, var(--board-line) 25px);}
.radar-sweep{position:absolute; inset:0; border-radius:50%; background:conic-gradient(from 0deg, rgba(92,148,132,0.4), transparent 60deg); animation:sweep 3.2s linear infinite;}
@keyframes sweep{100%{transform:rotate(360deg);}}
.radar-dot{position:absolute; width:7px; height:7px; border-radius:50%;}
.radar-center{position:absolute; top:50%; left:50%; width:6px; height:6px; background:var(--green); border-radius:50%; transform:translate(-50%,-50%);}
.radar-caption{font-family:var(--mono); font-size:9.5px; color:var(--chalk-dim);}
.console-main{padding:14px 22px;}
.cc-line{font-family:var(--mono); font-size:12px; margin-bottom:9px;}
.cc-label{color:var(--chalk-dim);} .cc-val{color:var(--chalk); font-weight:600;}

/* ===== ALERT LOG (teletype list, not rounded cards) ===== */
.alert-grid{display:flex; flex-direction:column;}
.a-card{
  background:transparent; border:none; border-bottom:1px dotted var(--board-line);
  padding:12px 2px; display:flex; justify-content:space-between; align-items:center; gap:16px;
}
.a-card.crit .a-title::before{ content:'! '; color:var(--red); }
.a-card.ok .a-title::before{ content:'· '; color:var(--green); }
.a-left{display:flex; gap:12px; align-items:flex-start;}
.a-rank{font-family:var(--mono); font-size:10px; color:var(--chalk-dim); padding-top:2px;}
.a-title{font-family:var(--mono); font-weight:600; font-size:12.5px; margin-bottom:2px;}
.a-detail{font-size:11px; color:var(--chalk-mid);}
.a-action{font-family:var(--mono); font-size:9.5px; padding:4px 10px; border:1px solid var(--board-line); color:var(--chalk-dim); white-space:nowrap;}

/* ===== INCIDENT PLATE (hero) + PINNED ZONE TAGS ===== */
.hero-grid{display:grid; grid-template-columns:1fr 1.4fr; gap:1px; margin-bottom:20px; background:var(--board-line); border:1px solid var(--board-line);}
.hero-map-card{background:var(--board-raised); padding:22px; position:relative; overflow:visible; display:flex; flex-wrap:wrap; align-content:flex-start; gap:14px 10px;}
.hero-map-label{width:100%; font-family:var(--mono); font-size:10px; color:var(--chalk-dim); letter-spacing:0.5px; margin-bottom:6px;}
.hero-map-card svg{ display:none; } /* map dots replaced by pinned tags below, generated separately */
.zone-tag{
  background:var(--board); border:1px solid var(--board-line); border-left:4px solid var(--tag-color, var(--green));
  padding:10px 14px; min-width:118px; font-family:var(--mono);
  transform:rotate(var(--tilt, 0deg)); transition:transform 0.15s ease, border-color 0.15s ease;
}
.zone-tag:hover{ transform:rotate(0deg) scale(1.03); border-color:var(--tag-color, var(--green)); }
.zone-tag .zt-id{ font-size:12px; font-weight:600; color:var(--chalk); }
.zone-tag .zt-area{ font-size:9.5px; color:var(--chalk-dim); margin-top:2px; }
.zone-tag .zt-status{ font-size:9px; margin-top:6px; color:var(--tag-color, var(--green)); letter-spacing:0.4px; }

.hero-info-card{background:var(--board-raised); padding:24px 26px; display:flex; flex-direction:column; justify-content:center;}
.hero-stat-line{display:flex; justify-content:space-between; padding:11px 0; border-bottom:1px dotted var(--board-line); font-size:12.5px;}
.hero-stat-line:last-child{border-bottom:none;}
.hero-stat-label{color:var(--chalk-dim); font-family:var(--mono); font-size:10.5px;}
.hero-stat-val{font-weight:600; color:var(--chalk);}
"""

COUNT_UP_JS = """
<script>
  document.querySelectorAll('.count-up').forEach(function(el){
    var target = parseFloat(el.getAttribute('data-target'));
    if (isNaN(target)) return;
    var decimals = (el.getAttribute('data-target').split('.')[1] || '').length;
    var duration = 800, start = null;
    function step(ts){
      if (!start) start = ts;
      var progress = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = (target * eased).toFixed(decimals);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = target.toFixed(decimals);
    }
    requestAnimationFrame(step);
  });
</script>
"""

# ---------------------------------------------------------------------------
# PAGE: OVERVIEW
# ---------------------------------------------------------------------------
def render_overview():
    ready = {k: find_module_file(m["file"]) is not None for k, m in MODULE_FILES.items()}
    ready_count = sum(ready.values())

    # ---- Zone tags (pinned index-card style, replaces the SVG map dots) ----
    zone_tags_html = ""
    hero_stats_html = ""
    n_gap = 0
    if ZONES_PATH and HOSPITALS_PATH:
        zones_df = pd.read_csv(ZONES_PATH)
        coverage_path = find_module_file(MODULE_FILES["coverage"]["file"])
        if coverage_path:
            cov_df = pd.read_csv(coverage_path)
            nearest_col = "nearest_capable_min" if "nearest_capable_min" in cov_df.columns else "nearest_capable_min_APPROX"
            cov_sorted = cov_df.sort_values("risk_score", ascending=False).reset_index(drop=True)

            tilts = [-2, 1.5, -1, 2, -1.5, 1]
            for i, row in zones_df.iterrows():
                status_row = cov_sorted[cov_sorted["zone_id"] == row["zone_id"]]
                is_gap = len(status_row) and status_row["coverage_status"].values[0] == "GAP"
                color_var = "var(--red)" if is_gap else "var(--green)"
                status_text = "UNCOVERED" if is_gap else "COVERED"
                tilt = tilts[i % len(tilts)]
                zone_tags_html += f"""
                <div class="zone-tag" style="--tag-color:{color_var}; --tilt:{tilt}deg;">
                  <div class="zt-id">{row['zone_id']}</div>
                  <div class="zt-area">{row.get('dominant_area','')}</div>
                  <div class="zt-status">{status_text}</div>
                </div>"""

            top = cov_sorted.iloc[0]
            n_covered = int((cov_sorted["coverage_status"] == "COVERED").sum())
            n_total = len(cov_sorted)
            n_gap = n_total - n_covered
            display_risk = jitter_value(float(top['risk_score']), seed=refresh_count) if live_mode else top['risk_score']
            hero_stats_html = f"""
            <div class="hero-stat-line"><span class="hero-stat-label">HIGHEST RISK ZONE</span><span class="hero-stat-val">{top['zone_id']} — {top.get('dominant_area','')}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">RISK SCORE</span><span class="hero-stat-val">{display_risk}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">ZONES COVERED</span><span class="hero-stat-val">{n_covered} / {n_total}</span></div>
            <div class="hero-stat-line"><span class="hero-stat-label">NEAREST CAPABLE HOSPITAL</span><span class="hero-stat-val">{top.get('nearest_capable_hospital','N/A')}</span></div>
            """

    rows_html = ""
    for key, m in MODULE_FILES.items():
        status_class = "ready" if ready[key] else "pending"
        status_label = "READY" if ready[key] else "PENDING"
        rows_html += f"""
        <div class="mod-row">
          <div class="mod-left">
            <div class="mod-icon">{m['icon']}</div>
            <div class="mod-name">{m['name']}</div>
          </div>
          <div class="mod-status {status_class}">{status_label}</div>
        </div>"""

    hero_section = ""
    if zone_tags_html:
        hero_section = f"""
        <div class="hero-grid">
          <div class="hero-map-card">
            <div class="hero-map-label">ZONE MANIFEST — CHENNAI METRO</div>
            {zone_tags_html}
          </div>
          <div class="hero-info-card">
            <div class="panel-title">Network Snapshot</div>
            {hero_stats_html}
          </div>
        </div>"""

    all_clear = n_gap == 0
    incident_label = "ALL CLEAR" if all_clear else "ZONES UNCOVERED"
    incident_value = "0" if all_clear else str(n_gap)
    incident_color = "var(--green)" if all_clear else "var(--red)"

    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="breadcrumb">Dashboards / <b>Master Overview</b></div>
      <div class="page-title">Emergency Readiness Board</div>
      {hero_section}
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">INCIDENT STATUS</div>
          <div class="stat-value" style="color:{incident_color};"><span class="count-up" data-target="{incident_value}">0</span></div>
          <div style="font-family:var(--mono); font-size:10px; color:var(--chalk-dim); margin-top:4px; letter-spacing:0.5px;">{incident_label}</div>
        </div>
        <div class="stat-card"><div class="stat-label">HOSPITALS MONITORED</div><div class="stat-value"><span class="count-up" data-target="12">0</span></div></div>
        <div class="stat-card"><div class="stat-label">MODULES READY</div><div class="stat-value"><span class="count-up" data-target="{ready_count}">0</span>/4</div></div>
        <div class="stat-card"><div class="stat-label">DATA CONTRACT</div><div class="stat-value" style="font-size:18px;">LOCKED</div></div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Module Manifest</div>
        <div class="panel-sub">shared data contract — hospital_id linked across all 4</div>
        {rows_html}
      </div>
    {COUNT_UP_JS}</body></html>"""
    components.html(html, height=560 + (240 if zone_tags_html else 0), scrolling=False)

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
          <div class="stat-card"><div class="stat-label">Zones — Gap</div><div class="stat-value" style="color:var(--red);"><span class="count-up" data-target="{n_gap}">0</span></div></div>
          <div class="stat-card"><div class="stat-label">Zones — Covered</div><div class="stat-value" style="color:var(--green);"><span class="count-up" data-target="{n_covered}">0</span></div></div>
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
    {COUNT_UP_JS}</body></html>"""
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
        <div class="stat-card"><div class="stat-label">ZONES — GAP</div><div class="stat-value" style="color:var(--red);"><span class="count-up" data-target="{n_gap}">0</span></div></div>
        <div class="stat-card"><div class="stat-label">ZONES — COVERED</div><div class="stat-value" style="color:var(--green);"><span class="count-up" data-target="{n_covered}">0</span></div></div>
        <div class="stat-card"><div class="stat-label">HOSPITALS</div><div class="stat-value"><span class="count-up" data-target="{len(hospitals)}">0</span></div></div>
        <div class="stat-card"><div class="stat-label">TOTAL ACCIDENTS</div><div class="stat-value"><span class="count-up" data-target="{int(zones['accident_count'].sum())}">0</span></div></div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Highest Priority Zone (quick preview)</div>
        <div class="panel-sub">{top['zone_id']} — {top['dominant_area']} · risk score {top['risk_score']} · {display_travel} min to {top.get('nearest_capable_hospital','N/A')} · status {top['coverage_status']}</div>
      </div>
    {COUNT_UP_JS}</body></html>"""
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