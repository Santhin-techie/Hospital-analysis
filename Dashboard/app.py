"""
Hospital Resource Intelligence - Master Dashboard (Home page)

Folder layout (same style as your scripts folder):
    Dashboard/app.py            <- this file
    data/simulated/             <- chennai_hospitals.csv, chennai_hotspot_zones.csv,
                                   chennai_coverage_results_LIVE.csv (or _APPROX.csv),
                                   medicine_inventory_demand.csv (optional)

Run (from the Dashboard folder):  streamlit run app.py

Module 4 (coverage) uses your REAL results.
Modules 1-3 use SAMPLE data until teammates give their CSV files.
Search for "SAMPLE" below to find what to replace.
"""

import os
import random

import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Hospital Readiness - Master Console", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(BASE, "..", "data", "simulated")

RED, AMBER, GREEN = [201, 58, 36], [217, 162, 27], [28, 129, 96]
COLOR = {"Red": RED, "Amber": AMBER, "Green": GREEN}
SAFE_WINDOW = 20

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"], .stApp { font-family:'Schibsted Grotesk', system-ui, sans-serif; }
  .stApp { background:#E4EEEA; color:#12262D; }
  header[data-testid="stHeader"], #MainMenu, footer { display:none !important; }
  .block-container { padding-top:1.4rem; max-width:1500px; }
  section[data-testid="stSidebar"] { background:#12262D; }
  section[data-testid="stSidebar"] * { color:#E4EEEA !important; }
  h1 { font-weight:800; letter-spacing:-0.02em; }
  .kpi { background:#F6FAF8; border:1px solid #B9D0C8; border-radius:14px; padding:16px 18px; }
  .kpi .n { font-size:34px; font-weight:800; line-height:1.1; }
  .kpi .l { font-size:13.5px; color:#44585F; margin-top:2px; }
  .kpi .s { font-size:11.5px; color:#44585F; margin-top:6px; }
  .bad { color:#C93A24; } .mid { color:#A86F00; } .good { color:#1C8160; }
  .alert { background:#F6FAF8; border:1px solid #B9D0C8; border-left:6px solid var(--c);
           border-radius:10px; padding:10px 14px; margin-bottom:8px; font-size:14.5px; }
  .alert small { color:#44585F; }
  .tag { font-size:11.5px; font-weight:700; padding:2px 8px; border-radius:999px; background:#FAF0D6; color:#A86F00; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
@st.cache_data
def load():
    hosp = pd.read_csv(os.path.join(SIM, "chennai_hospitals.csv"))
    zones = pd.read_csv(os.path.join(SIM, "chennai_hotspot_zones.csv"))
    live = os.path.join(SIM, "chennai_coverage_results_LIVE.csv")
    approx = os.path.join(SIM, "chennai_coverage_results_APPROX.csv")
    if os.path.exists(live):
        cov = pd.read_csv(live)
    else:
        cov = pd.read_csv(approx).rename(columns={"nearest_capable_min_APPROX": "nearest_capable_min"})
    med_path = os.path.join(SIM, "medicine_inventory_demand.csv")
    med = pd.read_csv(med_path) if os.path.exists(med_path) else None
    return hosp, zones, cov, med

try:
    hosp, zones, cov, med = load()
except FileNotFoundError as e:
    st.error(f"Missing data file: {e}. Keep app.py in the Dashboard folder and the data folder one level up, like the scripts folder.")
    st.stop()

# ---------------------------------------------------------------------------
# SAMPLE data for Modules 1-3 (one row per hospital)
# Replace each block with the teammate's real CSV when it is ready.
# ---------------------------------------------------------------------------
def sample_module_status(hosp_df):
    rng = random.Random(7)
    rows = []
    for _, h in hosp_df.iterrows():
        rows.append({
            "name": h["name"],
            "bed_pct": rng.randint(55, 88),        # Module 1: predicted bed use tomorrow (%)
            "meds_short": rng.choice([0, 0, 1, 2]),   # Module 2: medicines about to run out
            "blood_low": rng.choice([0, 0, 0, 1, 2]), # Module 3: blood groups running low
        })
    df = pd.DataFrame(rows).set_index("name")
    # A deliberate story: the hospital most zones depend on is under strain
    df.loc["Fortis Malar Hospital, Adyar", ["bed_pct", "blood_low"]] = [92, 2]
    return df

status = sample_module_status(hosp)

# ---------------------------------------------------------------------------
# Combine the four answers into one colour per hospital
# ---------------------------------------------------------------------------
served = cov["nearest_capable_hospital"].value_counts()
hosp = hosp.set_index("name").join(status)
hosp["zones_served"] = served.reindex(hosp.index).fillna(0).astype(int)
hosp = hosp.reset_index()

def readiness(r):
    reasons, level = [], 0
    if r["bed_pct"] >= 90: level = max(level, 2); reasons.append(f"beds forecast {r['bed_pct']}% full")
    elif r["bed_pct"] >= 80: level = max(level, 1); reasons.append(f"beds forecast {r['bed_pct']}% full")
    if r["blood_low"] >= 2: level = max(level, 2); reasons.append(f"{r['blood_low']} blood groups low")
    elif r["blood_low"] == 1: level = max(level, 1); reasons.append("1 blood group low")
    if r["meds_short"] >= 2: level = max(level, 2); reasons.append(f"{r['meds_short']} medicines running out")
    elif r["meds_short"] == 1: level = max(level, 1); reasons.append("1 medicine running out")
    if r["zones_served"] >= 3 and level >= 1:
        level = 2; reasons.append(f"{r['zones_served']} accident zones depend on it")
    elif r["zones_served"] >= 3:
        level = max(level, 1); reasons.append(f"{r['zones_served']} accident zones depend on it")
    return pd.Series({"readiness": ["Green", "Amber", "Red"][level], "why": ", ".join(reasons) or "all clear"})

hosp[["readiness", "why"]] = hosp.apply(readiness, axis=1)

# ---------------------------------------------------------------------------
# Sidebar menu
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Hospital Readiness")
    st.caption("Master console")
    page = st.radio("Go to", [
        "Home",
        "Where should the patient go?",
        "Bed occupancy (Module 1)",
        "Medicine stock (Module 2)",
        "Blood bank (Module 3)",
        "Coverage and referral (Module 4)",
    ], label_visibility="collapsed")

if page != "Home":
    st.title(page)
    st.info("This page is next. Home is ready first.")
    st.stop()

# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
st.title("Are our hospitals ready today?")
st.write("One view of beds, medicine, blood and accident-zone coverage across 12 Chennai hospitals.")

gap_zones = cov[cov["coverage_status"] == "GAP"]
n_red = int((hosp["readiness"] == "Red").sum())
n_amber = int((hosp["readiness"] == "Amber").sum())

if med is not None:
    med_short = int((med["stock_status"] == "SHORTAGE RISK").sum())
    med_expired = int((med["stock_status"] == "EXPIRED WASTAGE").sum())
    med_sub = f"{med_expired} more already expired"
else:
    med_short, med_sub = int(hosp["meds_short"].sum()), "sample data"

def kpi(col, number, label, sub, cls):
    col.markdown(f'<div class="kpi"><div class="n {cls}">{number}</div>'
                 f'<div class="l">{label}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
kpi(c1, len(gap_zones), "Accident zones too far from a trauma hospital",
    f"of {len(cov)} zones, over {SAFE_WINDOW} min at the worst time of day", "bad" if len(gap_zones) else "good")
kpi(c2, n_red, "Hospitals in trouble", f"{n_amber} more need care", "bad" if n_red else "good")
kpi(c3, med_short, "Medicines at risk of running out", med_sub, "mid" if med_short else "good")
kpi(c4, int(hosp["blood_low"].sum()), "Blood groups running low", "across all hospitals (sample data)", "mid")

st.write("")
left, right = st.columns([1.7, 1])

# ---- Map -------------------------------------------------------------------
with left:
    st.subheader("Map")
    z = zones.merge(cov[["zone_id", "coverage_status", "nearest_capable_min"]], on="zone_id")
    z["color"] = z["coverage_status"].map(lambda s: RED if s == "GAP" else GREEN)
    z["label"] = z.apply(lambda r: f"{r['dominant_area']}: {r['nearest_capable_min']:.0f} min to a trauma hospital "
                                   f"({'too far' if r['coverage_status']=='GAP' else 'covered'})", axis=1)
    h = hosp.copy()
    h["color"] = h["readiness"].map(COLOR)
    h["label"] = h.apply(lambda r: f"{r['name']}: {r['readiness']} ({r['why']})", axis=1)

    layers = [
        pdk.Layer("ScatterplotLayer", z, get_position="[centroid_lon, centroid_lat]",
                  get_fill_color="color", get_radius=900, opacity=0.35, pickable=True),
        pdk.Layer("ScatterplotLayer", z, get_position="[centroid_lon, centroid_lat]",
                  get_line_color="color", stroked=True, filled=False, get_radius=900, line_width_min_pixels=2),
        pdk.Layer("ScatterplotLayer", h, get_position="[longitude, latitude]",
                  get_fill_color="color", get_line_color=[255, 255, 255], stroked=True,
                  get_radius=450, line_width_min_pixels=2, pickable=True),
    ]
    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=12.98, longitude=80.19, zoom=9.6),
        tooltip={"text": "{label}"}, map_style="light"), height=520)
    st.caption("Small dots are hospitals, large circles are accident zones. Green is ready, yellow needs care, red is in trouble.")

# ---- Warnings --------------------------------------------------------------
with right:
    st.subheader("Warnings")
    alerts = []
    for _, r in gap_zones.sort_values("risk_score", ascending=False).iterrows():
        area = zones.set_index("zone_id").loc[r["zone_id"], "dominant_area"]
        alerts.append(("Red", f"{area} is {r['nearest_capable_min']:.0f} min from a trauma hospital",
                       f"Worst at {r['worst_slot']}" if "worst_slot" in r else ""))
    for _, r in hosp[hosp["readiness"] == "Red"].iterrows():
        alerts.append(("Red", r["name"], r["why"]))
    for _, r in hosp[hosp["readiness"] == "Amber"].iterrows():
        alerts.append(("Amber", r["name"], r["why"]))
    for level, title, detail in alerts[:8]:
        st.markdown(f'<div class="alert" style="--c:rgb{tuple(COLOR[level])}"><b>{title}</b><br>'
                    f'<small>{detail}</small></div>', unsafe_allow_html=True)
    if not alerts:
        st.success("No warnings. Everything is within limits.")

# ---- Hospital table --------------------------------------------------------
st.subheader("Hospital readiness")
table = hosp[["name", "readiness", "bed_pct", "meds_short", "blood_low", "zones_served", "why"]].rename(columns={
    "name": "Hospital", "readiness": "Status", "bed_pct": "Beds full tomorrow (%)",
    "meds_short": "Medicines running out", "blood_low": "Blood groups low",
    "zones_served": "Accident zones served", "why": "Reason"})
order = {"Red": 0, "Amber": 1, "Green": 2}
table = table.sort_values("Status", key=lambda s: s.map(order))
st.dataframe(table, hide_index=True, use_container_width=True)

st.markdown('<span class="tag">Sample data</span> Beds, blood and the hospital-level medicine counts are placeholders '
            'until Modules 1 to 3 are connected. Accident-zone coverage is real routing data.', unsafe_allow_html=True)