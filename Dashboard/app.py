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

import math
import os
import random
import runpy

import pandas as pd
import pydeck as pdk
import streamlit as st

# Each module keeps its own dashboard file. ?view=<key> opens that dashboard unchanged;
# the left-menu links open these addresses in a new browser tab.
_HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_APPS = {
    "module1": ("Bed occupancy (Module 1)", os.path.join(_HERE, "bed_occupancy", "dashboard.py")),
    "module4": ("Coverage and referral (Module 4)", os.path.join(_HERE, "module4_dashboard_full.py")),
}
_view = st.query_params.get("view")
if _view in MODULE_APPS and os.path.exists(MODULE_APPS[_view][1]):
    runpy.run_path(MODULE_APPS[_view][1], run_name="__main__")
    st.stop()

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
  header[data-testid="stHeader"] { background:transparent; }
  #MainMenu, footer, [data-testid="stDeployButton"] { display:none !important; }
  [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] { display:flex !important; visibility:visible !important; }
  .block-container { padding-top:1.4rem; max-width:1500px; }
  section[data-testid="stSidebar"] { background:#12262D; }
  section[data-testid="stSidebar"] * { color:#E4EEEA !important; }
  a.m4link { display:block; margin:6px 0 0 2px; padding:9px 12px; border-radius:8px; font-weight:600;
             color:#E4EEEA !important; text-decoration:none !important; border:1px solid #44585F; }
  a.m4link:hover { background:#1E3A44; }
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
ROLLUP = next((q for q in [os.path.join(BASE, "bed_occupancy", "outputs", "hospital_risk_rollup.csv"),
                           os.path.join(BASE, "..", "data", "final", "hospital_risk_rollup.csv")]
               if os.path.exists(q)), None)
BEDS_REAL = ROLLUP is not None      # True = Module 1 results are loaded

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
    df["bed_high"] = False
    # A deliberate sample story: the hospital most zones depend on has low blood
    df.loc["Fortis Malar Hospital, Adyar", "blood_low"] = 2
    if BEDS_REAL:
        # REAL Module 1: busiest department's 7-day forecast and the hospital risk level
        r = pd.read_csv(ROLLUP).set_index("hospital_name_department")
        common = df.index.intersection(r.index)
        df.loc[common, "bed_pct"] = r.loc[common, "highest_risk_predicted_occupancy"].round(0)
        df.loc[common, "bed_high"] = r.loc[common, "hospital_risk_level"].eq("HIGH")
    else:
        df.loc["Fortis Malar Hospital, Adyar", "bed_pct"] = 92
    df["bed_pct"] = df["bed_pct"].astype(int)
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
    if r["bed_high"] or r["bed_pct"] >= 90: level = max(level, 2); reasons.append(f"bed forecast high ({r['bed_pct']}% in busiest department)")
    elif r["bed_pct"] >= 80: level = max(level, 1); reasons.append(f"bed forecast {r['bed_pct']}% in busiest department")
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
    _pages = ["Home", "Where should the patient go?"]
    if not os.path.exists(MODULE_APPS["module1"][1]):
        _pages.append("Bed occupancy (Module 1)")
    _pages += ["Medicine stock (Module 2)", "Blood bank (Module 3)"]
    page = st.radio("Go to", _pages, label_visibility="collapsed")
    # Real links: one click opens that module's own dashboard in a new tab
    for _key, (_label, _file) in MODULE_APPS.items():
        if os.path.exists(_file):
            st.markdown(f'<a class="m4link" href="?view={_key}" target="_blank">{_label} &#8599;</a>',
                        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# MODULE 4 PAGE: Coverage and referral (REAL data)
# ---------------------------------------------------------------------------
def kpi(col, number, label, sub, cls):
    col.markdown(f'<div class="kpi"><div class="n {cls}">{number}</div>'
                 f'<div class="l">{label}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)

SLOT_LABELS = {"now": "Now (live)", "morning": "Morning 08:30", "midday": "Midday 13:00",
               "evening": "Evening 18:00", "night": "Night 23:00"}


# ---------------------------------------------------------------------------
# PAGE: Where should the patient go?
# ---------------------------------------------------------------------------
def approx_min(lat1, lon1, lat2, lon2):
    """Rough drive minutes from straight-line distance (same idea as approx_coverage.py)."""
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.4 / 22 * 60

def hospital_problems(r):
    p = []
    if r["trauma_tier"] > 2: p.append("cannot handle trauma")
    if r["bed_high"] or r["bed_pct"] >= 90: p.append(f"bed forecast high ({r['bed_pct']}%)")
    if r["blood_low"] >= 2: p.append("blood running low")
    if r["meds_short"] >= 2: p.append("medicines running out")
    return p

def render_patient_route():
    st.title("Where should the patient go?")
    st.write("Pick where the accident happened. The app checks travel time, trauma capability, beds, "
             "blood and medicine, then tells you where to take the patient.")
    c = cov.set_index("zone_id")
    zi = zones.set_index("zone_id")
    order = list(c.sort_values("risk_score", ascending=False).index)

    when_opts = {"Slowest time of day": "nearest_capable_min"}
    for key, label in [("now", "Now (live traffic)"), ("morning", "Morning peak 08:30"), ("midday", "Midday 13:00"),
                       ("evening", "Evening peak 18:00"), ("night", "Night 23:00")]:
        if f"capable_min_{key}" in c.columns:
            when_opts[label] = f"capable_min_{key}"

    a, b = st.columns(2)
    zone_id = a.selectbox("Accident zone", order, format_func=lambda z: zi.loc[z, "dominant_area"])
    when = b.selectbox("Time of day", list(when_opts))

    zone = zi.loc[zone_id]
    ref_name = c.loc[zone_id, "nearest_capable_hospital"]
    ref_min = c.loc[zone_id, when_opts[when]]
    if pd.isna(ref_min):
        ref_min = c.loc[zone_id, "nearest_capable_min"]

    # Estimate every hospital, scaled so the measured hospital matches its real road time
    d = hosp.copy()
    d["est"] = d.apply(lambda r: approx_min(zone["centroid_lat"], zone["centroid_lon"], r["latitude"], r["longitude"]), axis=1)
    base = float(d.loc[d["name"] == ref_name, "est"].iloc[0])
    factor = min(3.0, max(0.5, float(ref_min) / base)) if base > 0 else 1.0
    d["minutes"] = (d["est"] * factor).round(1)
    d.loc[d["name"] == ref_name, "minutes"] = round(float(ref_min), 1)
    # If the real all-hospital file exists (from compute_travel_time.py), use real TomTom minutes
    used_real = False
    real_path = os.path.join(SIM, "chennai_all_travel_times.csv")
    if os.path.exists(real_path):
        at = pd.read_csv(real_path)
        at = at[(at["zone_id"] == zone_id)].dropna(subset=["travel_min"])
        col = when_opts[when]
        if col != "nearest_capable_min":
            at = at[at["slot"] == col[len("capable_min_"):]]
        m = at.groupby("hospital_id")["travel_min"].max()   # slowest time = max over the five times
        if len(m) >= 3:
            d["minutes"] = d["hospital_id"].map(m)
            d = d.dropna(subset=["minutes"])
            used_real = True
    d["problems"] = d.apply(hospital_problems, axis=1)
    d = d.sort_values("minutes").reset_index(drop=True)

    ready = d[d["problems"].map(len) == 0]
    capable = d[d["trauma_tier"] <= 2]
    best = ready.iloc[0] if len(ready) else (capable.iloc[0] if len(capable) else d.iloc[0])
    nearest = d.iloc[0]

    # ---- The answer ----
    if best["name"] == nearest["name"]:
        color, head = "#1C8160", f"Take the patient to {best['name']}"
        body = f"It is the nearest hospital, about {best['minutes']:.0f} minutes away, and it is ready: trauma-capable, with beds, blood and medicine."
    else:
        extra = best["minutes"] - nearest["minutes"]
        why = "; ".join(nearest["problems"]) or "a better option exists"
        color, head = "#A86F00", f"Do not take the patient to {nearest['name']}. Go to {best['name']}."
        body = (f"{nearest['name']} is the nearest ({nearest['minutes']:.0f} min) but it {why}. "
                f"{best['name']} is about {best['minutes']:.0f} minutes away ({extra:.0f} min more) and is ready.")
    if best["problems"]:
        color = "#C93A24"
        body += f" Warning: even this choice has problems ({'; '.join(best['problems'])}). Call ahead."
    st.markdown(f'<div class="alert" style="--c:{color};padding:18px 20px;"><div style="font-size:21px;font-weight:800;">{head}</div>'
                f'<div style="margin-top:6px;">{body}</div></div>', unsafe_allow_html=True)

    k1, k2, k3 = st.columns(3)
    kpi(k1, f"{best['minutes']:.0f} min", "Travel time to recommended hospital", when, "good" if best["minutes"] <= SAFE_WINDOW else "bad")
    kpi(k2, f"Tier {int(best['trauma_tier'])}", "Trauma level", f"{int(best['icu_beds'])} ICU beds", "")
    kpi(k3, f"{int(best['bed_pct'])}%", "Bed forecast, busiest department (7 days)", "Module 1 data" if BEDS_REAL else "sample data", "mid" if best["bed_pct"] >= 80 else "good")
    st.write("")

    # ---- Comparison table ----
    st.subheader("Compared with other hospitals")
    top = d.head(6).copy()
    top["Verdict"] = top.apply(lambda r: "Go here" if r["name"] == best["name"]
                               else ("Skip: " + ", ".join(r["problems"]) if r["problems"] else "Good backup"), axis=1)
    show = top[["name", "minutes", "trauma_tier", "bed_pct", "blood_low", "meds_short", "Verdict"]].rename(columns={
        "name": "Hospital", "minutes": "Minutes", "trauma_tier": "Trauma tier", "bed_pct": "Bed forecast, busiest dept (%)",
        "blood_low": "Blood groups low", "meds_short": "Medicines running out"})
    st.dataframe(show, hide_index=True, use_container_width=True)

    # ---- Map ----
    d["color"] = d["name"].map(lambda n: GREEN if n == best["name"] else ([201, 58, 36] if n == nearest["name"] else [37, 84, 199]))
    d["label"] = d.apply(lambda r: f"{r['name']}: about {r['minutes']:.0f} min", axis=1)
    line = pd.DataFrame([{"slat": zone["centroid_lat"], "slon": zone["centroid_lon"],
                          "tlat": best["latitude"], "tlon": best["longitude"]}])
    here = pd.DataFrame([{"lat": zone["centroid_lat"], "lon": zone["centroid_lon"], "label": f"Accident zone: {zone['dominant_area']}"}])
    st.pydeck_chart(pdk.Deck(layers=[
        pdk.Layer("LineLayer", line, get_source_position="[slon, slat]", get_target_position="[tlon, tlat]",
                  get_color=[28, 129, 96], get_width=5),
        pdk.Layer("ScatterplotLayer", d, get_position="[longitude, latitude]", get_fill_color="color",
                  get_line_color=[255, 255, 255], stroked=True, get_radius=450, line_width_min_pixels=2, pickable=True),
        pdk.Layer("ScatterplotLayer", here, get_position="[lon, lat]", get_fill_color=[18, 38, 45],
                  get_radius=700, pickable=True),
    ], initial_view_state=pdk.ViewState(latitude=float(zone["centroid_lat"]), longitude=float(zone["centroid_lon"]), zoom=10.2),
        tooltip={"text": "{label}"}, map_style="light"), height=420)
    st.caption("Dark circle is the accident. Green is the recommended hospital, red is the nearest one if it is skipped, blue are the others.")

    if used_real:
        note = "Travel minutes for every hospital are real road times from TomTom."
    else:
        note = (f"Minutes for {ref_name} are real road times from TomTom. Other hospitals are estimated from distance "
                "and scaled to match it. Run compute_travel_time.py to get real minutes for all of them.")
    st.markdown(f'<span class="tag">Note</span> {note} {"Blood and medicine are" if BEDS_REAL else "Beds, blood and medicine are"} sample data until the other modules are connected.',
                unsafe_allow_html=True)


if page == "Where should the patient go?":
    render_patient_route()
    st.stop()

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
    "name": "Hospital", "readiness": "Status", "bed_pct": "Bed forecast, busiest dept (%)",
    "meds_short": "Medicines running out", "blood_low": "Blood groups low",
    "zones_served": "Accident zones served", "why": "Reason"})
order = {"Red": 0, "Amber": 1, "Green": 2}
table = table.sort_values("Status", key=lambda s: s.map(order))
st.dataframe(table, hide_index=True, use_container_width=True)

st.markdown(f'<span class="tag">Data note</span> {"Bed forecasts come from Module 1 (real results). " if BEDS_REAL else ""}'
            f'{"Blood and" if BEDS_REAL else "Beds, blood and"} hospital-level medicine counts are placeholders until those modules are connected. '
            'Accident-zone coverage is real routing data.', unsafe_allow_html=True)