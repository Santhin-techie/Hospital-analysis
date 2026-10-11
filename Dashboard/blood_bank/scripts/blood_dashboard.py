"""
Module 3 — Blood Bank Intelligence: Dashboard
----------------------------------------------
Reads the risk-engine contract and the 14-day forecast and shows them.

Run from the project root:   py -m streamlit run app\\blood_dashboard.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
STATUS_ORDER = ["SHORTAGE RISK", "LOW STOCK", "EXPIRY RISK", "STABLE"]
STATUS_COLOR = {"SHORTAGE RISK": "#C0392B", "LOW STOCK": "#E67E22",
                "EXPIRY RISK": "#B7950B", "STABLE": "#1E8449"}

st.set_page_config(page_title="Blood Bank Intelligence - Chennai", layout="wide")


@st.cache_data
def load():
    cov = pd.read_csv(SIM_DIR / "blood_coverage_results.csv")
    fpath = OUT_DIR / "blood_forecasts.csv"
    if not fpath.exists():
        fpath = SIM_DIR / "blood_forecasts.csv"
    fc = pd.read_csv(fpath, parse_dates=["date"])
    ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
    hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv")
    return cov, fc, ops, hosp


cov, fc, ops, hosp = load()
names = hosp.set_index("hospital_id")["name"].to_dict()
cov["hospital"] = cov["hospital_id"].map(names).fillna(cov["hospital_id"])
cov["blood_group"] = pd.Categorical(cov["blood_group"], GROUPS, ordered=True)

st.title("Blood Bank Intelligence - Chennai")
st.caption(f"Stock as of {ops.date.max().date()} | forecast "
           f"{fc.date.min().date()} to {fc.date.max().date()} | simulated data")

# ---------------- Sidebar filters ----------------
st.sidebar.header("Filters")
sel_h = st.sidebar.multiselect("Hospital", sorted(cov.hospital.unique()))
sel_g = st.sidebar.multiselect("Blood group", GROUPS)
sel_s = st.sidebar.multiselect("Status", STATUS_ORDER)
view = cov.copy()
if sel_h:
    view = view[view.hospital.isin(sel_h)]
if sel_g:
    view = view[view.blood_group.isin(sel_g)]
if sel_s:
    view = view[view.status.isin(sel_s)]

# ---------------- KPI row ----------------
counts = view.status.value_counts().reindex(STATUS_ORDER).fillna(0).astype(int)
cols = st.columns(5)
for c, s in zip(cols[:4], STATUS_ORDER):
    c.metric(s.title(), int(counts[s]))
if "recommended_units" in view:
    cols[4].metric("Units to source (7d)", int(view.recommended_units.sum()))

tab1, tab2, tab3, tab4 = st.tabs(["Status grid", "Action list", "Forecast", "Map"])

# ---------------- Tab 1: hospital x group status grid ----------------
with tab1:
    metric = st.radio("Show", ["Status", "Days of cover"], horizontal=True)
    if metric == "Status":
        grid = view.pivot_table(index="hospital", columns="blood_group", values="status",
                                aggfunc="first", observed=True)
        styled = grid.style.map(lambda v: f"background-color: {STATUS_COLOR.get(v, 'white')}; color: white")
    else:
        grid = view.pivot_table(index="hospital", columns="blood_group", values="days_of_cover",
                                aggfunc="first", observed=True)
        styled = grid.style.format("{:.1f}").background_gradient(cmap="RdYlGn", vmin=0, vmax=10)
    st.dataframe(styled, use_container_width=True)

# ---------------- Tab 2: action list ----------------
with tab2:
    st.subheader("Where to act first")
    act = view[view.status != "STABLE"].copy()
    act["status"] = pd.Categorical(act["status"], STATUS_ORDER, ordered=True)
    sort_col = "stress_shortfall_7d" if "stress_shortfall_7d" in act else "days_of_cover"
    act = act.sort_values(["status", sort_col], ascending=[True, sort_col != "stress_shortfall_7d"])
    show = [c for c in ["hospital", "blood_group", "status", "stock_units", "forecasted_demand",
                        "days_of_cover", "units_expiring_3d", "projected_stock_7d",
                        "stress_shortfall_7d", "recommended_units"] if c in act.columns]
    st.dataframe(act[show], use_container_width=True, hide_index=True)
    st.download_button("Download action list (CSV)", act[show].to_csv(index=False),
                       "blood_action_list.csv", "text/csv")

# ---------------- Tab 3: forecast for one hospital x group ----------------
with tab3:
    c1, c2 = st.columns(2)
    h = c1.selectbox("Hospital", sorted(cov.hospital.unique()), key="fh")
    g = c2.selectbox("Blood group", GROUPS, index=GROUPS.index("O+"), key="fg")
    hid = {v: k for k, v in names.items()}.get(h, h)
    hist = (ops[(ops.hospital_id == hid) & (ops.blood_group == g)
                & (ops.date > ops.date.max() - pd.Timedelta(days=42))]
            .set_index("date")[["units_demanded", "units_donated"]]
            .rename(columns={"units_demanded": "Demand (actual)", "units_donated": "Donations (actual)"}))
    f = (fc[(fc.hospital_id == hid) & (fc.blood_group == g)].set_index("date")
         [["demand_forecast", "demand_upper_p90", "donation_forecast"]]
         .rename(columns={"demand_forecast": "Demand (forecast)",
                          "demand_upper_p90": "Demand P90 upper",
                          "donation_forecast": "Donations (forecast)"}))
    st.line_chart(pd.concat([hist, f], axis=1))
    row = cov[(cov.hospital_id == hid) & (cov.blood_group == g)]
    if len(row):
        r = row.iloc[0]
        st.write(f"**{r.status}** - stock {r.stock_units} units, "
                 f"{r.days_of_cover} days of cover, 7-day forecast demand {r.forecasted_demand}.")

# ---------------- Tab 4: map ----------------
with tab4:
    worst = (cov.assign(rank=cov.status.map({s: i for i, s in enumerate(STATUS_ORDER)}))
             .groupby("hospital_id")["rank"].min().map(dict(enumerate(STATUS_ORDER))))
    m = hosp[["hospital_id", "latitude", "longitude"]].copy()
    m["color"] = m.hospital_id.map(worst).map(STATUS_COLOR).fillna("#808080")
    m["size"] = 300
    st.caption("Colour = worst status across the 8 blood groups at that hospital.")
    st.map(m, latitude="latitude", longitude="longitude", color="color", size="size")