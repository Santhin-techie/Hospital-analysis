"""
Medicine Demand & Expiry — Live Streamlit Dashboard
=====================================================
Module 2 of the Hospital Resource Intelligence System.

HOW TO RUN:
    pip install streamlit pandas plotly
    streamlit run medicine_dashboard_streamlit.py

DATA SOURCE:
    Tries to read from database/hospital.db (tables: medicine_master,
    usage_history, batch_stock, medicine_forecast, medicine_alerts) —
    the same SQLite database built in Phases D/E of your pipeline.

    If that database or those tables don't exist yet, this script
    automatically falls back to generating synthetic demo data in
    memory, so you can run and demo this file immediately, and swap
    in your real pipeline output later with zero code changes on
    your end other than finishing Phases C-E.

WHAT THIS SCRIPT DOES EACH REFRESH CYCLE:
    1. Reads current stock, expiry, and forecasted demand
    2. Computes shortage status, wastage risk (₹), and reorder qty
    3. Computes demand trend (rising/stable/falling) vs 90-day average
    4. Re-renders the whole dashboard
    5. Waits REFRESH_SECONDS, then repeats — this is what makes it "live"
"""

import time
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
DB_PATH = Path("database/hospital.db")
REFRESH_SECONDS = 4          # how often the dashboard recalculates + redraws
SHORTAGE_CRIT_DAYS = 3
SHORTAGE_WARN_DAYS = 7

st.set_page_config(page_title="Medicine Stock Intelligence", layout="wide")


# ----------------------------------------------------------------------
# DATA LAYER — real SQL if available, else synthetic fallback
# ----------------------------------------------------------------------
def load_from_sql():
    conn = sqlite3.connect(DB_PATH)
    meds = pd.read_sql("SELECT * FROM medicine_master", conn)
    batch = pd.read_sql("SELECT * FROM batch_stock", conn)
    forecast = pd.read_sql("SELECT * FROM medicine_forecast", conn)
    usage = pd.read_sql("SELECT * FROM usage_history", conn)
    conn.close()
    return meds, batch, forecast, usage


def generate_synthetic():
    """Fallback demo data — used only if hospital.db / tables aren't ready yet."""
    meds = pd.DataFrame([
        {"medicine_id": "M01", "medicine_name": "Insulin (vial)", "unit_price": 180, "reorder_lead_time_days": 5},
        {"medicine_id": "M02", "medicine_name": "Amoxicillin 250mg", "unit_price": 8, "reorder_lead_time_days": 4},
        {"medicine_id": "M03", "medicine_name": "Atropine Injection", "unit_price": 95, "reorder_lead_time_days": 6},
        {"medicine_id": "M04", "medicine_name": "Paracetamol 500mg", "unit_price": 2, "reorder_lead_time_days": 3},
        {"medicine_id": "M05", "medicine_name": "Surgical Syringe 5ml", "unit_price": 6, "reorder_lead_time_days": 5},
        {"medicine_id": "M06", "medicine_name": "ORS Sachets", "unit_price": 5, "reorder_lead_time_days": 7},
        {"medicine_id": "M07", "medicine_name": "IV Saline 500ml", "unit_price": 20, "reorder_lead_time_days": 4},
        {"medicine_id": "M08", "medicine_name": "Ceftriaxone 1g", "unit_price": 150, "reorder_lead_time_days": 5},
    ])

    # persistent state across refresh cycles, so stock genuinely depletes over time
    if "sim_state" not in st.session_state:
        rng = np.random.default_rng(42)
        st.session_state.sim_state = pd.DataFrame({
            "medicine_id": meds["medicine_id"],
            "current_quantity": rng.integers(20, 900, size=len(meds)).astype(float),
            "days_to_expiry": rng.integers(2, 120, size=len(meds)).astype(float),
            "daily_use": rng.uniform(1, 30, size=len(meds)),
            "avg90_daily_use": rng.uniform(1, 30, size=len(meds)),
        })

    state = st.session_state.sim_state
    state["current_quantity"] = (state["current_quantity"] - state["daily_use"] * np.random.uniform(0.3, 0.7, len(state))).clip(lower=0)
    state["days_to_expiry"] = (state["days_to_expiry"] - 0.03).clip(lower=0)
    state["daily_use"] = (state["daily_use"] + np.random.uniform(-0.2, 0.2, len(state))).clip(lower=0.2)

    batch = state.rename(columns={"current_quantity": "current_quantity"}).copy()
    batch["expiry_date"] = pd.Timestamp.today() + pd.to_timedelta(batch["days_to_expiry"], unit="D")
    forecast = state[["medicine_id", "daily_use"]].rename(columns={"daily_use": "forecast_daily_demand"})
    forecast["avg90_daily_demand"] = state["avg90_daily_use"]

    # dummy usage history for the drill-down chart
    usage_rows = []
    for _, m in meds.iterrows():
        base = state.loc[state.medicine_id == m.medicine_id, "daily_use"].values[0]
        for d in range(30):
            date = pd.Timestamp.today() - pd.Timedelta(days=29 - d)
            qty = max(0, base + np.random.normal(0, base * 0.2))
            usage_rows.append({"medicine_id": m.medicine_id, "date": date, "quantity_used": qty})
    usage = pd.DataFrame(usage_rows)

    return meds, batch, forecast, usage


def load_data():
    try:
        if DB_PATH.exists():
            return load_from_sql()
    except Exception:
        pass
    return generate_synthetic()


# ----------------------------------------------------------------------
# CALCULATION LAYER — shortage / expiry / trend logic
# ----------------------------------------------------------------------
def compute_alerts(meds, batch, forecast):
    df = batch.merge(meds, on="medicine_id").merge(forecast, on="medicine_id")

    if "expiry_date" in df.columns:
        df["expiry_date"] = pd.to_datetime(df["expiry_date"])
        df["days_to_expiry"] = (df["expiry_date"] - pd.Timestamp.today()).dt.days.clip(lower=0)

    df["days_of_stock_left"] = df["current_quantity"] / df["forecast_daily_demand"].replace(0, np.nan)
    df["days_of_stock_left"] = df["days_of_stock_left"].fillna(0)

    lead_time = df["reorder_lead_time_days"] if "reorder_lead_time_days" in df.columns else SHORTAGE_WARN_DAYS
    df["shortage_status"] = np.select(
        [df["days_of_stock_left"] < SHORTAGE_CRIT_DAYS, df["days_of_stock_left"] < lead_time],
        ["Critical", "Warning"], default="Safe"
    )

    df["projected_unused"] = (df["current_quantity"] - df["forecast_daily_demand"] * df["days_to_expiry"]).clip(lower=0)
    df["wastage_risk_rs"] = (df["projected_unused"] * df["unit_price"]).round(0)

    df["suggested_reorder_qty"] = (df["forecast_daily_demand"] * 30 - df["current_quantity"]).clip(lower=0).round(0)

    if "avg90_daily_demand" in df.columns:
        df["trend_ratio"] = df["forecast_daily_demand"] / df["avg90_daily_demand"].replace(0, np.nan)
    else:
        df["trend_ratio"] = 1.0
    df["trend_ratio"] = df["trend_ratio"].fillna(1.0)

    conditions = [df["trend_ratio"] > 1.2, df["trend_ratio"] < 0.8]
    choices_label = ["↑ Rising", "↓ Falling"]
    choices_action = ["Order more", "Order less"]
    df["trend_label"] = np.select(conditions, choices_label, default="→ Stable")
    df["recommended_action"] = np.select(conditions, choices_action, default="Maintain")

    return df


# ----------------------------------------------------------------------
# RENDER LAYER
# ----------------------------------------------------------------------
def render_dashboard(df, usage, meds):
    st.title("💊 Medicine Stock Intelligence — Live")
    st.caption(f"Last updated: {pd.Timestamp.now().strftime('%H:%M:%S')} · auto-refreshes every {REFRESH_SECONDS}s")

    view = st.radio("View", ["Simple", "Advanced"], horizontal=True)

    crit_count = (df["shortage_status"] == "Critical").sum()
    total_wastage = df["wastage_risk_rs"].sum()
    total_saved = df.loc[df["recommended_action"] == "Order less",
                          "forecast_daily_demand"].sum() * 30 * df["unit_price"].mean() * 0  # placeholder-safe
    rising_count = (df["trend_label"] == "↑ Rising").sum()

    if view == "Simple":
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Need Attention Now", int(crit_count))
        c2.metric("🟡 Running Low", int((df["shortage_status"] == "Warning").sum()))
        c3.metric("🟢 Healthy Stock", int((df["shortage_status"] == "Safe").sum()))

        st.subheader("What needs action today")
        urgent = df[df["shortage_status"] != "Safe"].sort_values("days_of_stock_left")
        if urgent.empty:
            st.success("Nothing needs attention right now — all stock levels are healthy.")
        else:
            for _, r in urgent.head(8).iterrows():
                color = "🔴" if r["shortage_status"] == "Critical" else "🟡"
                st.write(f"{color} **{r['medicine_name']}** — {int(r['current_quantity'])} units left, "
                         f"~{r['days_of_stock_left']:.1f} days of stock remaining")

    else:  # Advanced
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Critical Shortage", int(crit_count))
        c2.metric("Wastage Risk (₹)", f"₹{total_wastage:,.0f}")
        c3.metric("Rising-Demand Items", int(rising_count))
        c4.metric("Items Tracked", len(df))

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔴 Shortage Watchlist")
            short_cols = ["medicine_name", "current_quantity", "days_of_stock_left", "suggested_reorder_qty", "shortage_status"]
            st.dataframe(
                df.sort_values("days_of_stock_left")[short_cols].head(8)
                  .rename(columns={"medicine_name": "Medicine", "current_quantity": "Stock",
                                    "days_of_stock_left": "Days Left", "suggested_reorder_qty": "Reorder Qty",
                                    "shortage_status": "Status"}),
                use_container_width=True, hide_index=True
            )

        with col2:
            st.subheader("🟡 Expiry Watchlist")
            exp_cols = ["medicine_name", "current_quantity", "days_to_expiry", "projected_unused", "wastage_risk_rs"]
            st.dataframe(
                df.sort_values("wastage_risk_rs", ascending=False)[exp_cols].head(8)
                  .rename(columns={"medicine_name": "Medicine", "current_quantity": "Batch Qty",
                                    "days_to_expiry": "Days to Expiry", "projected_unused": "Unused (proj.)",
                                    "wastage_risk_rs": "₹ Risk"}),
                use_container_width=True, hide_index=True
            )

        st.subheader("📊 Demand Trend & Reorder Advisor")
        trend_cols = ["medicine_name", "forecast_daily_demand", "trend_label", "recommended_action"]
        st.dataframe(
            df[trend_cols].rename(columns={"medicine_name": "Medicine", "forecast_daily_demand": "Forecast Daily Use",
                                            "trend_label": "Trend", "recommended_action": "Recommended Action"}),
            use_container_width=True, hide_index=True
        )

        st.subheader("🔍 Drill-Down")
        selected = st.selectbox("Select medicine", meds["medicine_name"])
        sel_id = meds.loc[meds["medicine_name"] == selected, "medicine_id"].values[0]
        hist = usage[usage["medicine_id"] == sel_id].sort_values("date")

        fig = go.Figure()
        if not hist.empty:
            fig.add_trace(go.Scatter(x=hist["date"], y=hist["quantity_used"],
                                      mode="lines", name="Usage History", line=dict(color="#12232A")))
        row = df[df["medicine_id"] == sel_id]
        if not row.empty:
            daily = row["forecast_daily_demand"].values[0]
            stock = row["current_quantity"].values[0]
            future_dates = pd.date_range(pd.Timestamp.today(), periods=30)
            fig.add_trace(go.Scatter(x=future_dates, y=[daily] * 30, mode="lines",
                                      name="Forecasted Demand", line=dict(color="#1D6E73", dash="dash")))
            fig.add_trace(go.Scatter(x=future_dates, y=[max(0, stock - daily * i) for i in range(30)],
                                      mode="lines", name="Projected Stock", line=dict(color="#57696E")))
        fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# MAIN LOOP — this is what makes the dashboard "live"
# ----------------------------------------------------------------------
placeholder = st.empty()

while True:
    meds, batch, forecast, usage = load_data()
    alerts_df = compute_alerts(meds, batch, forecast)

    with placeholder.container():
        render_dashboard(alerts_df, usage, meds)

    time.sleep(REFRESH_SECONDS)
    st.rerun()