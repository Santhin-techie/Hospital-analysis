from datetime import datetime, date
from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# 1. PAGE SETTINGS AND SHARED DATA LOCATION
# ============================================================

st.set_page_config(
    page_title="Hospital Pharmacy Analytics | Live Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "simulated" / "medicine_inventory_demand.csv"

# Rerun the dashboard every 60 seconds. The CSV is read again on each rerun.
st_autorefresh(interval=60_000, key="pharmacy_common_data_refresh")


# ============================================================
# 2. PROFESSIONAL STYLING
# ============================================================

st.markdown(
    """
    <style>
        .stApp { background: #F3F6FA; }
        .block-container {
            max-width: 1500px;
            padding-top: 1.35rem;
            padding-bottom: 2.5rem;
        }
        h1, h2, h3 { color: #173B57; }
        .hero {
            background: linear-gradient(120deg, #123B5D 0%, #0B7285 100%);
            border-radius: 16px;
            padding: 26px 30px;
            margin-bottom: 18px;
            color: white;
        }
        .hero-title {
            color: #FFFFFF;
            font-size: 30px;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 8px;
        }
        .hero-subtitle {
            color: #D8EEF2;
            font-size: 14px;
            margin-bottom: 14px;
        }
        .live-line {
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 650;
            border-top: 1px solid rgba(255,255,255,0.25);
            padding-top: 11px;
        }
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 13px;
            padding: 15px 17px;
            box-shadow: 0 3px 12px rgba(22, 53, 79, 0.04);
        }
        [data-testid="stMetricLabel"] {
            color: #61778A;
            font-size: 0.84rem;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: #123B5D;
            font-weight: 750;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #E0E7EF;
            border-radius: 10px;
            overflow: hidden;
        }
        .section-note { color: #63788A; font-size: 0.88rem; }
        .footer {
            border-top: 1px solid #DCE5ED;
            padding-top: 13px;
            margin-top: 30px;
            text-align: center;
            color: #6F8090;
            font-size: 0.78rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. LOAD THE COMMON DATASET (NO CACHE, ALWAYS RE-READ)
# ============================================================

REQUIRED_COLUMNS = [
    "medicine_id",
    "medicine_name",
    "category",
    "batch_number",
    "manufacture_date",
    "expiry_date",
    "unit_cost_inr",
    "current_stock_units",
    "reorder_level",
    "base_daily_demand",
    "icmr_surge_season",
    "icmr_surge_factor",
    "forecasted_daily_demand",
]


def load_common_data() -> pd.DataFrame:
    """Load the shared inventory CSV fresh each time Streamlit reruns."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Shared data file was not found: {DATA_PATH}\n"
            "Place medicine_inventory_demand.csv in data/simulated/."
        )

    data = pd.read_csv(DATA_PATH)
    data.columns = data.columns.str.strip()

    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    numeric_columns = [
        "unit_cost_inr",
        "current_stock_units",
        "reorder_level",
        "base_daily_demand",
        "icmr_surge_factor",
        "forecasted_daily_demand",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    data["manufacture_date"] = pd.to_datetime(data["manufacture_date"], errors="coerce")
    data["expiry_date"] = pd.to_datetime(data["expiry_date"], errors="coerce")

    # Recalculate time-sensitive status values from expiry_date on every refresh.
    today = pd.Timestamp(date.today())
    data["days_to_expiry"] = (data["expiry_date"].dt.normalize() - today).dt.days
    data["days_to_expiry"] = data["days_to_expiry"].fillna(999999).astype(int)

    data["projected_stock_left_at_expiry"] = (
        data["current_stock_units"]
        - data["forecasted_daily_demand"] * data["days_to_expiry"].clip(lower=0)
    ).round(1)

    data["expiry_urgency"] = "SAFE"
    data.loc[data["days_to_expiry"].between(31, 90), "expiry_urgency"] = "WARNING"
    data.loc[data["days_to_expiry"].between(1, 30), "expiry_urgency"] = "CRITICAL"
    data.loc[data["days_to_expiry"] <= 0, "expiry_urgency"] = "EXPIRED"

    data["stock_status"] = "STABLE STOCK"
    data["value_at_risk_inr"] = 0.0

    expired = data["days_to_expiry"] <= 0
    near_expiry = data["days_to_expiry"].between(1, 90)
    safe_expiry = data["days_to_expiry"] > 90
    projected_negative = data["projected_stock_left_at_expiry"] < 0

    data.loc[expired, "stock_status"] = "EXPIRED WASTAGE"
    data.loc[expired, "value_at_risk_inr"] = (
        data.loc[expired, "current_stock_units"] * data.loc[expired, "unit_cost_inr"]
    )

    risk_rows = near_expiry | safe_expiry
    shortage_rows = risk_rows & projected_negative
    wastage_rows = near_expiry & ~projected_negative
    stable_rows = safe_expiry & ~projected_negative

    data.loc[shortage_rows, "stock_status"] = "SHORTAGE RISK"
    data.loc[wastage_rows, "stock_status"] = "WASTAGE RISK"
    data.loc[wastage_rows, "value_at_risk_inr"] = (
        data.loc[wastage_rows, "projected_stock_left_at_expiry"].clip(lower=0)
        * data.loc[wastage_rows, "unit_cost_inr"]
    )
    data.loc[stable_rows, "stock_status"] = "STABLE STOCK"

    # A combined action label is used only to sort/display the dashboard.
    data["action_priority"] = "Safe"
    data["priority_rank"] = 4

    warning_mask = (data["days_to_expiry"].between(31, 90)) | (data["stock_status"] == "WASTAGE RISK")
    data.loc[warning_mask, "action_priority"] = "Warning - Review stock/expiry"
    data.loc[warning_mask, "priority_rank"] = 3

    critical_mask = (data["days_to_expiry"].between(1, 30)) | (data["stock_status"] == "SHORTAGE RISK")
    data.loc[critical_mask, "action_priority"] = "Critical - Replenish or prioritize use"
    data.loc[critical_mask, "priority_rank"] = 2

    data.loc[expired, "action_priority"] = "Expired - Remove from usable stock"
    data.loc[expired, "priority_rank"] = 1

    data["value_at_risk_inr"] = data["value_at_risk_inr"].round(2)
    data["stock_value_inr"] = (data["current_stock_units"] * data["unit_cost_inr"]).round(2)

    data = data.sort_values(
        by=["priority_rank", "days_to_expiry", "current_stock_units"],
        ascending=[True, True, True],
    ).reset_index(drop=True)
    return data


try:
    df = load_common_data()
except Exception as error:
    st.error("The shared medicine data could not be loaded.")
    st.code(str(error))
    st.info(
        "Expected file: data/simulated/medicine_inventory_demand.csv. "
        "Check the folder location and CSV column names."
    )
    st.stop()


# ============================================================
# 4. HEADER AND LAST-UPDATED TIME
# ============================================================

last_updated = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
st.markdown(
    f"""
    <div class="hero">
        <div class="hero-title">Hospital Pharmacy Analytics</div>
        <div class="hero-subtitle">
            Shared medicine data | Inventory monitoring, demand estimates,
            expiry risk and replenishment priorities
        </div>
        <div class="live-line">
            LIVE REFRESH: EVERY 1 MINUTE &nbsp; | &nbsp; LAST UPDATED: {last_updated}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Shared source: data/simulated/medicine_inventory_demand.csv. "
    "The dashboard reloads this file every minute and recalculates expiry-related status."
)


# ============================================================
# 5. KEY PERFORMANCE INDICATORS
# ============================================================

total_medicines = int(df["medicine_id"].nunique())
total_stock = int(df["current_stock_units"].sum())
expired_count = int((df["days_to_expiry"] <= 0).sum())
shortage_count = int((df["stock_status"] == "SHORTAGE RISK").sum())
expiring_30_count = int(df["days_to_expiry"].between(1, 30).sum())
warning_count = int(
    (df["days_to_expiry"].between(31, 90) | (df["stock_status"] == "WASTAGE RISK")).sum()
)
total_value_at_risk = float(df["value_at_risk_inr"].sum())

st.subheader("Executive Overview")
metric_row_1 = st.columns(4)
metric_row_1[0].metric("Medicines monitored", f"{total_medicines:,}")
metric_row_1[1].metric("Total current stock", f"{total_stock:,} units")
metric_row_1[2].metric("Shortage-risk medicines", f"{shortage_count:,}")
metric_row_1[3].metric("Expired medicines", f"{expired_count:,}")

metric_row_2 = st.columns(3)
metric_row_2[0].metric("Expiring within 30 days", f"{expiring_30_count:,}")
metric_row_2[1].metric("Expiry / wastage warnings", f"{warning_count:,}")
metric_row_2[2].metric("Estimated value at risk", f"₹{total_value_at_risk:,.2f}")

if expired_count > 0 or shortage_count > 0 or expiring_30_count > 0:
    st.warning(
        f"Action required: {expired_count} expired medicine(s), "
        f"{shortage_count} shortage-risk medicine(s), and "
        f"{expiring_30_count} medicine(s) expiring within 30 days. "
        "Review the priority inventory table below."
    )
else:
    st.success("No expired, shortage-risk, or near-expiry items are currently detected in this dataset.")


# ============================================================
# 6. OVERVIEW CHARTS
# ============================================================

st.subheader("Inventory and Risk Overview")
chart_left, chart_right = st.columns(2)

with chart_left:
    st.markdown("#### Current stock status")
    status_counts = (
        df["stock_status"].value_counts().rename_axis("Stock status").reset_index(name="Medicines")
    )
    status_fig = px.pie(
        status_counts,
        names="Stock status",
        values="Medicines",
        hole=0.56,
        color="Stock status",
        color_discrete_map={
            "SHORTAGE RISK": "#C94C4C",
            "EXPIRED WASTAGE": "#7C2D3B",
            "WASTAGE RISK": "#D99A22",
            "STABLE STOCK": "#35966B",
        },
    )
    status_fig.update_traces(textposition="inside", textinfo="percent+label")
    status_fig.update_layout(
        height=360,
        margin=dict(l=12, r=12, t=16, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    st.plotly_chart(status_fig, use_container_width=True)

with chart_right:
    st.markdown("#### Highest estimated value at risk")
    risk_data = df.nlargest(8, "value_at_risk_inr").copy()
    if not risk_data.empty and risk_data["value_at_risk_inr"].max() > 0:
        risk_fig = px.bar(
            risk_data.sort_values("value_at_risk_inr", ascending=True),
            x="value_at_risk_inr",
            y="medicine_name",
            orientation="h",
            labels={"value_at_risk_inr": "Estimated value at risk (₹)", "medicine_name": "Medicine"},
            color_discrete_sequence=["#287D8E"],
        )
        risk_fig.update_layout(
            height=360,
            margin=dict(l=12, r=12, t=16, b=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        st.plotly_chart(risk_fig, use_container_width=True)
    else:
        st.info("No positive estimated value-at-risk amount is currently present.")


# ============================================================
# 7. PRIORITY INVENTORY TABLE (URGENT ITEMS FIRST)
# ============================================================

st.subheader("Priority Inventory")
st.markdown(
    '<div class="section-note">All medicines are shown automatically. '
    'Expired items appear first, followed by critical stock/expiry risks, warnings, and safe items.</div>',
    unsafe_allow_html=True,
)

priority_columns = [
    "action_priority",
    "medicine_id",
    "medicine_name",
    "category",
    "current_stock_units",
    "reorder_level",
    "forecasted_daily_demand",
    "expiry_date",
    "days_to_expiry",
    "expiry_urgency",
    "stock_status",
    "value_at_risk_inr",
]
priority_view = df[priority_columns].copy()
priority_view["expiry_date"] = priority_view["expiry_date"].dt.date

st.dataframe(
    priority_view,
    use_container_width=True,
    hide_index=True,
    height=500,
    column_config={
        "action_priority": st.column_config.TextColumn("Action priority", width="large"),
        "medicine_id": st.column_config.TextColumn("Medicine ID", width="small"),
        "medicine_name": st.column_config.TextColumn("Medicine", width="large"),
        "current_stock_units": st.column_config.NumberColumn("Current stock", format="%d"),
        "reorder_level": st.column_config.NumberColumn("Reorder level", format="%d"),
        "forecasted_daily_demand": st.column_config.NumberColumn("Daily demand estimate", format="%.1f"),
        "expiry_date": st.column_config.DateColumn("Expiry date", format="DD MMM YYYY"),
        "days_to_expiry": st.column_config.NumberColumn("Days to expiry", format="%d"),
        "value_at_risk_inr": st.column_config.NumberColumn("Value at risk (₹)", format="₹%.2f"),
    },
)


# ============================================================
# 8. DETAILED VIEWS
# ============================================================

tab_expiry, tab_demand, tab_dataset = st.tabs(
    ["Expiry Management", "Demand Estimates", "Shared Data Details"]
)

with tab_expiry:
    st.markdown("#### Batch expiry review")
    expiry_view = df.sort_values(["days_to_expiry", "medicine_name"]).copy()
    expiry_cols = [
        "medicine_name",
        "batch_number",
        "manufacture_date",
        "expiry_date",
        "days_to_expiry",
        "current_stock_units",
        "unit_cost_inr",
        "expiry_urgency",
        "stock_status",
        "value_at_risk_inr",
    ]
    expiry_view = expiry_view[expiry_cols]
    expiry_view["manufacture_date"] = expiry_view["manufacture_date"].dt.date
    expiry_view["expiry_date"] = expiry_view["expiry_date"].dt.date
    st.dataframe(
        expiry_view,
        use_container_width=True,
        hide_index=True,
        height=430,
        column_config={
            "medicine_name": st.column_config.TextColumn("Medicine", width="large"),
            "days_to_expiry": st.column_config.NumberColumn("Days to expiry", format="%d"),
            "current_stock_units": st.column_config.NumberColumn("Current stock", format="%d"),
            "unit_cost_inr": st.column_config.NumberColumn("Unit cost (₹)", format="₹%.2f"),
            "value_at_risk_inr": st.column_config.NumberColumn("Value at risk (₹)", format="₹%.2f"),
        },
    )

with tab_demand:
    st.markdown("#### Daily demand estimates")
    demand_view = df.sort_values("forecasted_daily_demand", ascending=False).copy()
    demand_chart = px.bar(
        demand_view.head(12).sort_values("forecasted_daily_demand", ascending=True),
        x="forecasted_daily_demand",
        y="medicine_name",
        orientation="h",
        labels={"forecasted_daily_demand": "Estimated units per day", "medicine_name": "Medicine"},
        color_discrete_sequence=["#287D8E"],
    )
    demand_chart.update_layout(
        height=430,
        margin=dict(l=12, r=12, t=16, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(demand_chart, use_container_width=True)
    demand_cols = [
        "medicine_id",
        "medicine_name",
        "category",
        "base_daily_demand",
        "icmr_surge_season",
        "icmr_surge_factor",
        "forecasted_daily_demand",
        "reorder_level",
    ]
    st.dataframe(
        demand_view[demand_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "base_daily_demand": st.column_config.NumberColumn("Base daily demand", format="%.1f"),
            "icmr_surge_factor": st.column_config.NumberColumn("Surge factor", format="%.2f"),
            "forecasted_daily_demand": st.column_config.NumberColumn("Estimated daily demand", format="%.1f"),
            "reorder_level": st.column_config.NumberColumn("Reorder level", format="%d"),
        },
    )

with tab_dataset:
    st.markdown("#### Source dataset")
    st.write(f"**File:** `{DATA_PATH.relative_to(PROJECT_DIR)}`")
    st.write(f"**Rows:** {len(df):,} medicine records")
    st.write(f"**Fields:** {len(df.columns):,} after dashboard calculations")
    st.markdown(
        "The source dataset is from the uploaded Hospital-analysis project. "
        "It contains simulated medicine inventory and demand estimates. "
        "It does not contain a historical daily usage time series or hospital identifier. "
        "Therefore, this dashboard does not claim to train Prophet or infer hospital-specific stock."
    )
    with st.expander("Show all columns from the shared source"):
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 9. FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        Hospital Pharmacy Analytics · Shared medicine dataset · Automatic refresh: 60 seconds<br>
        Demo data only. Confirm inventory, expiry and replenishment actions with the hospital pharmacy system.
    </div>
    """,
    unsafe_allow_html=True,
)
