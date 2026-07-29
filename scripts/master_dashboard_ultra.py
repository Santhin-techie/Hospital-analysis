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

ZONES_PATH = find_module_file("chennai_hotspot_zones.csv")
HOSPITALS_PATH = find_module_file("chennai_hospitals.csv")

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
# PAGE: COVERAGE & REFERRAL INTELLIGENCE (rich version — ticker, radar, map)
# ---------------------------------------------------------------------------
def render_coverage_rich():
    m = MODULE_FILES["coverage"]
    coverage_path = find_module_file(m["file"])

    if not (coverage_path and ZONES_PATH and HOSPITALS_PATH):
        render_module("coverage")  # fall back to the plain "waiting for data" card
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

    # ticker
    ticker_html = ""
    for _, row in cov.head(5).iterrows():
        css = "crit" if row["coverage_status"] == "GAP" else ""
        dot = "🔴" if row["coverage_status"] == "GAP" else "🟢"
        ticker_html += f'<span class="ticker-item {css}">{dot} <b>#{row["priority_rank"]} {row["zone_id"]}</b> — {row["dominant_area"]} · {row["coverage_status"]} · {row[nearest_col]} min</span>'
    ticker_html *= 2

    # radar dots
    radar_dots_html = ""
    positions = [(30,60),(65,30),(45,75),(75,55),(25,35),(55,45)]
    for i, (_, row) in enumerate(cov.iterrows()):
        if i >= len(positions):
            break
        top, left = positions[i]
        color = "var(--red)" if row["coverage_status"] == "GAP" else "var(--green)"
        radar_dots_html += f'<div class="radar-dot" style="top:{top}%; left:{left}%; background:{color}; box-shadow:0 0 8px {color};"></div>'

    # alert cards
    alert_cards_html = ""
    for _, row in cov.iterrows():
        is_gap = row["coverage_status"] == "GAP"
        css_class = "crit" if is_gap else "ok"
        icon = "🔴" if is_gap else "🟢"
        alert_cards_html += f"""
        <div class="a-card {css_class}">
          <div class="a-left">
            <div class="a-rank">#{row['priority_rank']}</div>
            <div>{icon}</div>
            <div>
              <div class="a-title">{row['zone_id']} — {row['dominant_area']}</div>
              <div class="a-detail">{row['coverage_status']} · Risk score <b>{row['risk_score']}</b> · Nearest: <b>{row.get('nearest_capable_hospital','N/A')}</b></div>
            </div>
          </div>
          <div class="a-action">{row[nearest_col]} MIN</div>
        </div>"""

    top = cov.iloc[0]
    html = f"""<!DOCTYPE html><html><head><style>{BASE_CSS}</style></head><body>
      <div class="ticker-wrap"><div class="ticker-track">{ticker_html}</div></div>
      <div class="breadcrumb">Dashboards / Modules / <b>Coverage & Referral Intelligence</b></div>
      <div class="page-title">🚨 Coverage & Referral Intelligence</div>
      <div class="stat-grid" style="grid-template-columns:repeat(4,1fr);">
        <div class="stat-card"><div class="stat-label">Zones — Gap</div><div class="stat-value" style="color:var(--red);">{n_gap}</div></div>
        <div class="stat-card"><div class="stat-label">Zones — Covered</div><div class="stat-value" style="color:var(--green);">{n_covered}</div></div>
        <div class="stat-card"><div class="stat-label">Hospitals</div><div class="stat-value">{len(hospitals)}</div></div>
        <div class="stat-card"><div class="stat-label">Total Accidents</div><div class="stat-value">{int(zones['accident_count'].sum())}</div></div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Zone Radar</div>
        <div class="console-body">
          <div class="radar-box">
            <div class="radar"><div class="radar-sweep"></div><div class="radar-center"></div>{radar_dots_html}</div>
            <div class="radar-caption">{len(zones)} zones scanned</div>
          </div>
          <div class="console-main">
            <div class="cc-line"><span class="cc-label">highest_risk_zone:</span> <span class="cc-val">{top['zone_id']} — {top['dominant_area']}</span></div>
            <div class="cc-line"><span class="cc-label">risk_score:</span> <span class="cc-val">{top['risk_score']}</span></div>
            <div class="cc-line"><span class="cc-label">nearest_capable_hospital:</span> <span class="cc-val">{top.get('nearest_capable_hospital','N/A')}</span></div>
            <div class="cc-line"><span class="cc-label">travel_time:</span> <span class="cc-val">{top[nearest_col]} min</span></div>
            <div class="cc-line"><span class="cc-label">status:</span> <span class="cc-val">{top['coverage_status']}</span></div>
          </div>
        </div>
      </div>
      <div class="glass-panel">
        <div class="panel-title">Active Zone Alerts</div>
        <div class="alert-grid">{alert_cards_html}</div>
      </div>
    </body></html>"""
    components.html(html, height=1150, scrolling=True)

    # --- real interactive map (native Streamlit, can't easily go inside the iframe) ---
    st.markdown("### 🗺️ Zone & Hospital Map")
    st.caption("Red = coverage gap · Green = covered · Blue = hospital")
    try:
        import pydeck as pdk
        zone_map_df = cov.copy()
        zone_map_df["color"] = zone_map_df["coverage_status"].apply(lambda s: [255,75,75,200] if s=="GAP" else [52,224,161,200])
        zone_map_df["radius"] = zone_map_df["risk_score"] * 8
        hosp_map_df = hospitals.copy()
        hosp_map_df["color"] = [[74,163,255,200]] * len(hosp_map_df)

        zone_layer = pdk.Layer("ScatterplotLayer", data=zone_map_df,
            get_position="[centroid_lon, centroid_lat]", get_fill_color="color",
            get_radius="radius", radius_min_pixels=8, radius_max_pixels=40, pickable=True)
        hosp_layer = pdk.Layer("ScatterplotLayer", data=hosp_map_df,
            get_position="[longitude, latitude]", get_fill_color="color", get_radius=180,
            radius_min_pixels=6, radius_max_pixels=20, pickable=True,
            stroked=True, get_line_color=[255,255,255,180], line_width_min_pixels=1)
        view_state = pdk.ViewState(latitude=float(zones["centroid_lat"].mean()),
                                    longitude=float(zones["centroid_lon"].mean()), zoom=10, pitch=0)
        st.pydeck_chart(pdk.Deck(layers=[zone_layer, hosp_layer], initial_view_state=view_state,
                                  map_style="dark", tooltip={"text": "{dominant_area}"}))
    except ImportError:
        st.warning("pydeck not installed — run `pip install pydeck` to enable the map.")

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