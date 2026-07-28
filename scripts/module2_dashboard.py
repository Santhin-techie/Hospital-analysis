"""
Module 2 — Medicine Demand Forecasting + Expiry-Aware Stock Dashboard
-----------------------------------------------------------------------
Standalone operational dashboard for pharmaceutical inventory management,
seasonal surge forecasting (ICMR-grounded), and financial risk tracking.

Run with:
    streamlit run scripts/module2_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Medicine Demand & Expiry Intelligence", layout="wide")

DATA_PATH = r"C:\Users\santhin kumar k\mini\data\simulated\medicine_inventory_demand.csv"

# Load Dataset
if not os.path.exists(DATA_PATH):
    st.error(f"Dataset not found at {DATA_PATH}. Please run scripts/generate_medicine_data.py first.")
    st.stop()

df = pd.read_csv(DATA_PATH)

# Header Section
st.title("💊 Module 2: Medicine Demand Forecasting & Expiry-Aware Dashboard")
st.caption("Grounded in ICMR Epidemiological Disease-Burden & NLEM 2022 Essential Medicine Standards")

# Sidebar Controls
st.sidebar.header("🔍 Filter & Scenario Controls")
selected_category = st.sidebar.multiselect(
    "Filter by Category",
    options=df["category"].unique(),
    default=df["category"].unique()
)

urgency_filter = st.sidebar.multiselect(
    "Expiry Urgency Status",
    options=["EXPIRED", "CRITICAL", "WARNING", "SAFE"],
    default=["EXPIRED", "CRITICAL", "WARNING", "SAFE"]
)

# Seasonal Surge Multiplier Simulator
season_scenario = st.sidebar.selectbox(
    "Simulate Seasonality Surge",
    ["Standard Baseline", "Monsoon Dengue/Flu Peak (+50% Analgesics/Antimalarials)", "Winter Respiratory Spike (+40% Antibiotics/Asthma)", "Summer Gastro Surge (+30% ORS/Gastro)"]
)

filtered_df = df[
    (df["category"].isin(selected_category)) &
    (df["expiry_urgency"].isin(urgency_filter))
].copy()

# Recalculate dynamic surge if scenario selected
if "Monsoon" in season_scenario:
    filtered_df["forecasted_daily_demand"] = filtered_df.apply(
        lambda r: round(r["forecasted_daily_demand"] * 1.5, 1) if r["category"] in ["Analgesic / Antipyretic", "Antimalarial"] else r["forecasted_daily_demand"], axis=1
    )
elif "Winter" in season_scenario:
    filtered_df["forecasted_daily_demand"] = filtered_df.apply(
        lambda r: round(r["forecasted_daily_demand"] * 1.4, 1) if r["category"] in ["Antibacterial", "Respiratory"] else r["forecasted_daily_demand"], axis=1
    )
elif "Summer" in season_scenario:
    filtered_df["forecasted_daily_demand"] = filtered_df.apply(
        lambda r: round(r["forecasted_daily_demand"] * 1.3, 1) if r["category"] in ["Electrolyte Replenisher", "Gastrointestinal", "Antiemetic"] else r["forecasted_daily_demand"], axis=1
    )

# Recalculate Stock Left at Expiry Formula:
# projected_stock_left_at_expiry = current_stock - (forecasted_daily_demand * max(0, days_to_expiry))
filtered_df["projected_stock_left_at_expiry"] = filtered_df.apply(
    lambda r: round(r["current_stock_units"] - (r["forecasted_daily_demand"] * max(0, r["days_to_expiry"])), 1), axis=1
)

# Recalculate Value at Risk
filtered_df["value_at_risk_inr"] = filtered_df.apply(
    lambda r: round(r["current_stock_units"] * r["unit_cost_inr"], 2) if r["days_to_expiry"] <= 0
    else (round(r["projected_stock_left_at_expiry"] * r["unit_cost_inr"], 2) if r["projected_stock_left_at_expiry"] > 0 else 0.0), axis=1
)

# KPI Cards
col1, col2, col3, col4 = st.columns(4)
total_stock_value = (filtered_df["current_stock_units"] * filtered_df["unit_cost_inr"]).sum()
total_val_at_risk = filtered_df["value_at_risk_inr"].sum()
shortage_count = (filtered_df["projected_stock_left_at_expiry"] < 0).sum()
critical_count = (filtered_df["expiry_urgency"].isin(["EXPIRED", "CRITICAL"])).sum()

col1.metric("Total Inventory Value", f"₹{total_stock_value:,.2f}")
col2.metric("Wastage Value at Risk", f"₹{total_val_at_risk:,.2f}", delta=f"{len(filtered_df[filtered_df['value_at_risk_inr']>0])} batches at risk", delta_color="inverse")
col3.metric("Shortage Alert Batches", f"{shortage_count}", delta="Action Required", delta_color="inverse")
col4.metric("Critical / Expired Batches", f"{critical_count}", delta="High Priority", delta_color="inverse")

st.markdown("---")

# Main Inventory & Expiry Table
st.subheader("📋 Medicine Expiry & Forecasted Stock Left Table")
st.caption("Formula: Projected Stock Left = Current Stock − (Forecasted Daily Demand × Days to Expiry)")

# Function to color code rows based on urgency
def style_urgency(val):
    if val == "EXPIRED":
        return "background-color: #FF4B4B; color: white; font-weight: bold;"
    elif val == "CRITICAL":
        return "background-color: #FF7B25; color: white; font-weight: bold;"
    elif val == "WARNING":
        return "background-color: #FFD166; color: black; font-weight: bold;"
    else:
        return "background-color: #06D6A0; color: black;"

display_cols = [
    "medicine_id", "medicine_name", "category", "batch_number", "expiry_date", 
    "days_to_expiry", "current_stock_units", "forecasted_daily_demand", 
    "projected_stock_left_at_expiry", "expiry_urgency", "stock_status", "value_at_risk_inr"
]

formatted_df = filtered_df[display_cols].rename(columns={
    "medicine_id": "ID", "medicine_name": "Medicine", "category": "Category",
    "batch_number": "Batch", "expiry_date": "Expiry Date", "days_to_expiry": "Days Left",
    "current_stock_units": "Current Stock", "forecasted_daily_demand": "Daily Forecast",
    "projected_stock_left_at_expiry": "Stock @ Expiry", "expiry_urgency": "Urgency",
    "stock_status": "Risk Status", "value_at_risk_inr": "Value at Risk (₹)"
})

st.dataframe(formatted_df, width="stretch", hide_index=True)

# Breakdown Charts
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📊 Stock Risk Breakdown")
    status_counts = filtered_df["stock_status"].value_counts().reset_index()
    status_counts.columns = ["Risk Status", "Batch Count"]
    st.bar_chart(status_counts.set_index("Risk Status"))

with col_b:
    st.subheader("📈 Top ICMR Seasonal Surge Multipliers")
    surge_df = filtered_df[["medicine_name", "icmr_surge_season", "icmr_surge_factor"]].sort_values("icmr_surge_factor", ascending=False).head(8)
    st.dataframe(surge_df.rename(columns={"medicine_name": "Medicine", "icmr_surge_season": "ICMR Peak Season", "icmr_surge_factor": "Surge Factor"}), hide_index=True)
