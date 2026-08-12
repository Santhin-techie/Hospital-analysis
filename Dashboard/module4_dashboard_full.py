"""
Module 4 — Emergency Coverage & Referral Intelligence — FULL CONSOLE DASHBOARD
--------------------------------------------------------------------------------
This version embeds the full animated HTML/CSS design (radar sweep, ticker,
styled alert cards) inside Streamlit using components.html, with your REAL
data from the CSVs injected into it -- so it looks like the original mockup
but shows real numbers.

Run with:
    streamlit run module4_dashboard_full.py

Requires:
    pip install streamlit pandas
"""

import streamlit as st
import pandas as pd
import os
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")
ZONES_PATH = f"{DATA_DIR}\\chennai_hotspot_zones.csv"
HOSPITALS_PATH = f"{DATA_DIR}\\chennai_hospitals.csv"
REAL_COVERAGE_PATH = f"{DATA_DIR}\\chennai_coverage_results.csv"
APPROX_COVERAGE_PATH = f"{DATA_DIR}\\chennai_coverage_results_APPROX.csv"
COVERAGE_PATH = REAL_COVERAGE_PATH if os.path.exists(REAL_COVERAGE_PATH) else APPROX_COVERAGE_PATH
USING_APPROX = COVERAGE_PATH == APPROX_COVERAGE_PATH

st.set_page_config(page_title="Emergency Readiness Console", layout="wide")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------
try:
    zones = pd.read_csv(ZONES_PATH)
    hospitals = pd.read_csv(HOSPITALS_PATH)
    coverage = pd.read_csv(COVERAGE_PATH)
except FileNotFoundError as e:
    st.error(f"Missing data file: {e}")
    st.stop()

coverage_sorted = coverage.sort_values("risk_score", ascending=False).reset_index(drop=True)
nearest_col = "nearest_capable_min" if "nearest_capable_min" in coverage.columns else "nearest_capable_min_APPROX"

# Bring in the human-readable region name + coordinates from the zones table
zones_lookup = zones.set_index("zone_id")[["dominant_area", "centroid_lat", "centroid_lon"]]
coverage_sorted = coverage_sorted.join(zones_lookup, on="zone_id")
coverage_sorted.insert(0, "priority_rank", range(1, len(coverage_sorted) + 1))

n_gap = (coverage["coverage_status"] == "GAP").sum()
n_covered = (coverage["coverage_status"] == "COVERED").sum()
total_accidents = int(zones["accident_count"].sum())
total_fatal = int(zones["fatal_count"].sum())

# ---------------------------------------------------------------------------
# BUILD TICKER ITEMS from real zone data (top 5 by risk)
# ---------------------------------------------------------------------------
ticker_html = ""
for _, row in coverage_sorted.head(5).iterrows():
    css = "crit" if row["coverage_status"] == "GAP" else ""
    dot = "🔴" if row["coverage_status"] == "GAP" else "🟢"
    ticker_html += f'<span class="ticker-item {css}">{dot} <b>#{row["priority_rank"]} {row["zone_id"]}</b> — {row["dominant_area"]} · {row["coverage_status"]} · {row[nearest_col]} min</span>'
# duplicate for seamless scroll loop
ticker_html = ticker_html + ticker_html

# ---------------------------------------------------------------------------
# BUILD ALERT CARDS from real zone data
# ---------------------------------------------------------------------------
alert_cards_html = ""
for _, row in coverage_sorted.iterrows():
    is_gap = row["coverage_status"] == "GAP"
    css_class = "crit" if is_gap else "ok"
    icon = "🔴" if is_gap else "🟢"
    nearest_hosp = row.get("nearest_capable_hospital", "N/A")
    alert_cards_html += f"""
    <div class="a-card {css_class}">
      <div class="a-left">
        <div class="a-rank">#{row['priority_rank']}</div>
        <div class="a-icon">{icon}</div>
        <div>
          <div class="a-title">{row['zone_id']} — {row['dominant_area']}</div>
          <div class="a-detail">{row['coverage_status']} · Risk score <b>{row['risk_score']}</b> · Nearest capable: <b>{nearest_hosp}</b></div>
        </div>
      </div>
      <div class="a-right">
        <div class="a-action">{row[nearest_col]} MIN TRAVEL</div>
      </div>
    </div>
    """

# ---------------------------------------------------------------------------
# BUILD RADAR DOTS -- place gap zones as red dots, covered as green dots
# ---------------------------------------------------------------------------
radar_dots_html = ""
positions = [(30,60),(65,30),(45,75),(75,55),(25,35),(55,45)]
for i, (_, row) in enumerate(coverage_sorted.iterrows()):
    if i >= len(positions):
        break
    top, left = positions[i]
    color = "var(--red)" if row["coverage_status"] == "GAP" else "var(--green)"
    radar_dots_html += f'<div class="radar-dot" style="top:{top}%; left:{left}%; background:{color}; box-shadow:0 0 8px {color};"></div>'

# ---------------------------------------------------------------------------
# FULL HTML (design system reused from the original mockup, values injected)
# ---------------------------------------------------------------------------
html = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Inter:wght@400;500;600;700;800&display=swap');
  :root{{
    --bg:#090C11; --panel:#10141B; --panel-raised:#141922; --line:#212836; --line-bright:#2E3A4D;
    --ink:#DCE3EC; --ink-dim:#64738A; --ink-mid:#93A2B8;
    --red:#FF4B4B; --red-dim:rgba(255,75,75,0.12);
    --amber:#FFB238; --amber-dim:rgba(255,178,56,0.12);
    --green:#34E0A1; --green-dim:rgba(52,224,161,0.12);
    --blue:#4FA3FF; --mono:'JetBrains Mono',monospace; --sans:'Inter',sans-serif;
  }}
  *{{box-sizing:border-box; margin:0; padding:0;}}
  body{{background:var(--bg); color:var(--ink); font-family:var(--sans);}}
  .ticker-wrap{{background:#050709; border-bottom:1px solid var(--line); overflow:hidden; white-space:nowrap; padding:9px 0;}}
  .ticker-track{{display:inline-flex; animation:scroll-left 28s linear infinite;}}
  .ticker-item{{font-family:var(--mono); font-size:11.5px; padding:0 28px; display:inline-flex; align-items:center; gap:8px; color:var(--ink-mid); border-right:1px solid var(--line);}}
  .ticker-item.crit{{color:var(--red);}}
  @keyframes scroll-left{{0%{{transform:translateX(0);}} 100%{{transform:translateX(-50%);}}}}
  .header{{padding:22px 32px 18px 32px; display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid var(--line);}}
  .h-eyebrow{{font-family:var(--mono); font-size:10.5px; letter-spacing:3px; color:var(--green); text-transform:uppercase; margin-bottom:8px;}}
  .h-title{{font-size:24px; font-weight:800;}}
  .h-sub{{font-family:var(--mono); font-size:11.5px; color:var(--ink-dim); margin-top:6px;}}
  .status-pill{{display:inline-flex; align-items:center; gap:7px; background:var(--green-dim); border:1px solid rgba(52,224,161,0.3); color:var(--green); padding:6px 12px; border-radius:20px; font-family:var(--mono); font-size:11px; font-weight:600;}}
  .status-dot{{width:6px; height:6px; border-radius:50%; background:var(--green); animation:blink 1.6s infinite;}}
  @keyframes blink{{0%,100%{{opacity:1;}} 50%{{opacity:0.25;}}}}
  .wrap{{padding:24px 32px;}}
  .counters{{display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line); border:1px solid var(--line); border-radius:10px; overflow:hidden; margin-bottom:26px;}}
  .counter{{background:var(--panel); padding:20px 22px;}}
  .counter-num{{font-family:var(--mono); font-size:32px; font-weight:700;}}
  .counter-num.red{{color:var(--red);}} .counter-num.green{{color:var(--green);}} .counter-num.amber{{color:var(--amber);}}
  .counter-label{{font-size:10.5px; color:var(--ink-dim); text-transform:uppercase; letter-spacing:0.8px; margin-top:8px;}}
  .section{{margin-bottom:28px;}}
  .section-title{{font-family:var(--mono); font-size:11px; letter-spacing:2px; text-transform:uppercase; color:var(--ink-mid); display:flex; align-items:center; gap:10px; margin-bottom:14px;}}
  .section-title::before{{content:''; width:3px; height:14px; background:var(--green); display:inline-block;}}
  .console{{background:var(--panel); border:1px solid var(--line-bright); border-radius:12px; overflow:hidden;}}
  .console-body{{display:grid; grid-template-columns:220px 1fr;}}
  .radar-box{{padding:22px; border-right:1px solid var(--line); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px;}}
  .radar{{width:160px; height:160px; border-radius:50%; border:1px solid var(--line-bright); position:relative; background:repeating-radial-gradient(circle, transparent 0, transparent 25px, var(--line) 26px);}}
  .radar-sweep{{position:absolute; inset:0; border-radius:50%; background:conic-gradient(from 0deg, rgba(52,224,161,0.35), transparent 60deg); animation:sweep 3.2s linear infinite;}}
  @keyframes sweep{{100%{{transform:rotate(360deg);}}}}
  .radar-dot{{position:absolute; width:6px; height:6px; border-radius:50%;}}
  .radar-center{{position:absolute; top:50%; left:50%; width:6px; height:6px; background:var(--green); border-radius:50%; transform:translate(-50%,-50%);}}
  .radar-caption{{font-family:var(--mono); font-size:9.5px; color:var(--ink-dim); text-align:center;}}
  .console-main{{padding:20px 24px;}}
  .cc-line{{font-family:var(--mono); font-size:12px; margin-bottom:9px;}}
  .cc-label{{color:var(--ink-dim);}} .cc-val{{color:var(--ink); font-weight:600;}}
  .alert-grid{{display:flex; flex-direction:column; gap:10px;}}
  .a-card{{background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--line); border-radius:8px; padding:14px 16px; display:flex; justify-content:space-between; align-items:center; gap:16px;}}
  .a-card.crit{{border-left-color:var(--red);}} .a-card.ok{{border-left-color:var(--green);}}
  .a-left{{display:flex; gap:12px; align-items:flex-start;}}
  .a-title{{font-weight:700; font-size:13px; margin-bottom:3px;}}
  .a-detail{{font-size:11.5px; color:var(--ink-mid);}}
  .a-action{{font-family:var(--mono); font-size:10px; padding:6px 10px; border-radius:5px; border:1px solid var(--line-bright); color:var(--ink-mid); white-space:nowrap;}}
  .a-rank{{font-family:var(--mono); font-size:11px; font-weight:700; color:var(--ink-dim); background:var(--panel-raised); border:1px solid var(--line-bright); border-radius:5px; padding:2px 7px; align-self:flex-start; margin-top:1px;}}
</style></head>
<body>
  <div class="ticker-wrap"><div class="ticker-track">{ticker_html}</div></div>
  <div class="header">
    <div>
      <div class="h-eyebrow">Module 04 · Coverage & Referral Intelligence</div>
      <div class="h-title">Emergency Readiness Console</div>
      <div class="h-sub">{'REAL road-network routing' if not USING_APPROX else 'APPROXIMATE routing — run compute_travel_time.py for real results'} · {len(hospitals)} hospitals · {len(zones)} zones</div>
    </div>
    <div class="status-pill"><span class="status-dot"></span>LIVE DATA</div>
  </div>
  <div class="wrap">
    <div class="counters">
      <div class="counter"><div class="counter-num red">{n_gap}</div><div class="counter-label">Zones — Coverage Gap</div></div>
      <div class="counter"><div class="counter-num green">{n_covered}</div><div class="counter-label">Zones — Covered</div></div>
      <div class="counter"><div class="counter-num amber">{total_accidents}</div><div class="counter-label">Total Simulated Accidents</div></div>
      <div class="counter"><div class="counter-num red">{total_fatal}</div><div class="counter-label">Fatal Accidents</div></div>
    </div>

    <div class="section">
      <div class="section-title">Zone Radar</div>
      <div class="console">
        <div class="console-body">
          <div class="radar-box">
            <div class="radar">
              <div class="radar-sweep"></div>
              <div class="radar-center"></div>
              {radar_dots_html}
            </div>
            <div class="radar-caption">{len(zones)} zones scanned</div>
          </div>
          <div class="console-main">
            <div class="cc-line"><span class="cc-label">highest_risk_zone:</span> <span class="cc-val">{coverage_sorted.iloc[0]['zone_id']} — {coverage_sorted.iloc[0]['dominant_area']}</span></div>
            <div class="cc-line"><span class="cc-label">risk_score:</span> <span class="cc-val">{coverage_sorted.iloc[0]['risk_score']}</span></div>
            <div class="cc-line"><span class="cc-label">nearest_capable_hospital:</span> <span class="cc-val">{coverage_sorted.iloc[0].get('nearest_capable_hospital','N/A')}</span></div>
            <div class="cc-line"><span class="cc-label">travel_time:</span> <span class="cc-val">{coverage_sorted.iloc[0][nearest_col]} min</span></div>
            <div class="cc-line"><span class="cc-label">status:</span> <span class="cc-val">{coverage_sorted.iloc[0]['coverage_status']}</span></div>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Active Zone Alerts</div>
      <div class="alert-grid">{alert_cards_html}</div>
    </div>
  </div>
</body></html>
"""

components.html(html, height=1300, scrolling=True)

# ---------------------------------------------------------------------------
# REAL MAP -- actual hospital + zone locations, color-coded by status
# (rendered natively by Streamlit, below the console, since components.html
#  can't host an interactive map inside its iframe easily)
# ---------------------------------------------------------------------------
st.markdown("### 🗺️ Zone & Hospital Map")
st.caption("Red = coverage gap zone · Green = covered zone · Blue = hospital")

import pydeck as pdk

zone_map_df = coverage_sorted.copy()
zone_map_df["color"] = zone_map_df["coverage_status"].apply(
    lambda s: [255, 75, 75, 200] if s == "GAP" else [52, 224, 161, 200]
)
zone_map_df["label"] = zone_map_df["zone_id"] + " — " + zone_map_df["dominant_area"]
zone_map_df["radius"] = zone_map_df["risk_score"] * 8  # bigger dot = higher risk

hosp_map_df = hospitals.copy()
hosp_map_df["color"] = [[74, 163, 255, 200]] * len(hosp_map_df)
hosp_map_df["label"] = hosp_map_df["name"]

zone_layer = pdk.Layer(
    "ScatterplotLayer",
    data=zone_map_df,
    get_position="[centroid_lon, centroid_lat]",
    get_fill_color="color",
    get_radius="radius",
    radius_min_pixels=8,
    radius_max_pixels=40,
    pickable=True,
)

hosp_layer = pdk.Layer(
    "ScatterplotLayer",
    data=hosp_map_df,
    get_position="[longitude, latitude]",
    get_fill_color="color",
    get_radius=180,
    radius_min_pixels=6,
    radius_max_pixels=20,
    pickable=True,
    stroked=True,
    get_line_color=[255, 255, 255, 180],
    line_width_min_pixels=1,
)

view_state = pdk.ViewState(
    latitude=float(zones["centroid_lat"].mean()),
    longitude=float(zones["centroid_lon"].mean()),
    zoom=10,
    pitch=0,
)

st.pydeck_chart(pdk.Deck(
    layers=[zone_layer, hosp_layer],
    initial_view_state=view_state,
    map_style="dark",
    tooltip={"text": "{label}"},
))

# ---------------------------------------------------------------------------
# READABLE ZONE -> REGION LOOKUP TABLE (answers "what area is ZONE-04?")
# ---------------------------------------------------------------------------
st.markdown("### 📍 Zone Reference — What Area Each Zone Covers")
st.dataframe(
    coverage_sorted[["priority_rank", "zone_id", "dominant_area", "risk_score",
                      "coverage_status", "nearest_capable_hospital", nearest_col]]
    .rename(columns={
        "priority_rank": "Rank", "zone_id": "Zone", "dominant_area": "Region / Area",
        "risk_score": "Risk Score", "coverage_status": "Status",
        "nearest_capable_hospital": "Nearest Capable Hospital", nearest_col: "Travel Time (min)"
    }),
    width='stretch', hide_index=True
)