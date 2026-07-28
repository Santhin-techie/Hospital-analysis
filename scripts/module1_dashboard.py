"""
Module 1 — Data Ingestion, Geospatial Calibration & Hospital Infrastructure Dashboard
---------------------------------------------------------------------------------------
Standalone operational dashboard for visualizing raw GIS crash distributions,
severity breakdowns, and hospital capability indexing.

Run with:
    streamlit run scripts/module1_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import os

st.set_page_config(page_title="Module 1: Spatial & Infrastructure Dashboard", layout="wide")

ACCIDENTS_PATH = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_simulated_accidents.csv"
HOSPITALS_PATH = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hospitals.csv"

# Load Datasets
if not os.path.exists(ACCIDENTS_PATH) or not os.path.exists(HOSPITALS_PATH):
    st.error("Missing dataset files. Please run scripts/generate_accident_data.py and scripts/build_hospital_table.py first.")
    st.stop()

accidents_df = pd.read_csv(ACCIDENTS_PATH)
hospitals_df = pd.read_csv(HOSPITALS_PATH)

# Header Section
st.title("🗺️ Module 1: Geospatial Crash Calibration & Hospital Indexing")
st.caption("Grounded in Tamil Nadu State Road Safety Crash Statistics (2023) & NHA Hospital Capability Registers")

# Sidebar Controls
st.sidebar.header("🔍 Interactive Map Filters")
selected_junctions = st.sidebar.multiselect(
    "Filter by High-Traffic Corridor / Junction",
    options=accidents_df["near_junction"].unique(),
    default=accidents_df["near_junction"].unique()
)

selected_severities = st.sidebar.multiselect(
    "Filter by Crash Severity",
    options=["Fatal", "Grievous", "Minor", "NonInjury"],
    default=["Fatal", "Grievous", "Minor", "NonInjury"]
)

selected_tiers = st.sidebar.multiselect(
    "Filter Hospital Trauma Tier",
    options=[1, 2, 3],
    default=[1, 2, 3]
)

filtered_accidents = accidents_df[
    (accidents_df["near_junction"].isin(selected_junctions)) &
    (accidents_df["severity"].isin(selected_severities))
].copy()

filtered_hospitals = hospitals_df[hospitals_df["trauma_tier"].isin(selected_tiers)].copy()

# KPI Metrics Header
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
total_crashes = len(filtered_accidents)
fatal_crashes = (filtered_accidents["severity"] == "Fatal").sum()
fatal_pct = (fatal_crashes / total_crashes * 100) if total_crashes > 0 else 0.0
total_hospitals = len(filtered_hospitals)
tier1_count = (filtered_hospitals["trauma_tier"] == 1).sum()
total_icu = filtered_hospitals["icu_beds"].sum()

kpi1.metric("Total Crash Points", f"{total_crashes}")
kpi2.metric("Fatal Crashes", f"{fatal_crashes}", delta=f"{fatal_pct:.1f}% ratio", delta_color="inverse")
kpi3.metric("Indexed Hospitals", f"{total_hospitals}")
kpi4.metric("Tier-1 Trauma Centers", f"{tier1_count}")
kpi5.metric("Total ICU Beds", f"{total_icu:,}")

st.markdown("---")

# PyDeck Map Section
st.subheader("📍 Interactive Geospatial Crash Scatter & Hospital Capabilities Map")
st.caption("Red/Orange/Yellow Dots = Crash Points (by severity) | Large Blue Pillars = Hospitals")

# Color mapping for crash severity
severity_colors = {
    "Fatal": [255, 75, 75, 220],     # Red
    "Grievous": [255, 140, 0, 200],  # Dark Orange
    "Minor": [255, 215, 0, 180],     # Yellow/Gold
    "NonInjury": [52, 224, 161, 160]  # Green
}

filtered_accidents["color"] = filtered_accidents["severity"].map(severity_colors)
filtered_accidents["radius"] = filtered_accidents["severity"].map({"Fatal": 90, "Grievous": 70, "Minor": 50, "NonInjury": 35})

filtered_hospitals["color"] = [[79, 163, 255, 230]] * len(filtered_hospitals) # Bright Blue
filtered_hospitals["elevation"] = (4 - filtered_hospitals["trauma_tier"]) * 500  # Higher pillar for Tier 1

crash_layer = pdk.Layer(
    "ScatterplotLayer",
    data=filtered_accidents,
    get_position="[longitude, latitude]",
    get_fill_color="color",
    get_radius="radius",
    pickable=True,
    radius_min_pixels=3,
    radius_max_pixels=15,
)

hosp_layer = pdk.Layer(
    "ColumnLayer",
    data=filtered_hospitals,
    get_position="[longitude, latitude]",
    get_elevation="elevation",
    elevation_scale=1,
    radius=180,
    get_fill_color="color",
    pickable=True,
    auto_highlight=True,
)

view_state = pdk.ViewState(
    latitude=float(accidents_df["latitude"].mean()),
    longitude=float(accidents_df["longitude"].mean()),
    zoom=10.2,
    pitch=45,
)

st.pydeck_chart(pdk.Deck(
    layers=[crash_layer, hosp_layer],
    initial_view_state=view_state,
    map_style="dark",
    tooltip={"html": "<b>{near_junction}</b><br/>Severity: {severity}<br/>ID: {accident_id}" if "accident_id" in filtered_accidents.columns else "<b>{name}</b><br/>Trauma Tier: {trauma_tier}<br/>ICU Beds: {icu_beds}"},
))

# Detailed Tables & Breakdown Section
st.markdown("---")
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Crash Distribution by Corridor")
    junction_counts = filtered_accidents["near_junction"].value_counts().reset_index()
    junction_counts.columns = ["Corridor / Junction", "Crash Count"]
    st.bar_chart(junction_counts.set_index("Corridor / Junction"))

with col_right:
    st.subheader("🏥 Hospital Capability Taxonomy Table")
    st.dataframe(
        filtered_hospitals[["hospital_id", "name", "trauma_tier", "has_icu", "has_cath_lab", "has_ventilator_bank", "icu_beds", "general_beds"]]
        .rename(columns={
            "hospital_id": "ID", "name": "Hospital Name", "trauma_tier": "Tier",
            "has_icu": "ICU?", "has_cath_lab": "Cath Lab?", "has_ventilator_bank": "Ventilators?",
            "icu_beds": "ICU Beds", "general_beds": "General Beds"
        }),
        width="stretch", hide_index=True
    )
