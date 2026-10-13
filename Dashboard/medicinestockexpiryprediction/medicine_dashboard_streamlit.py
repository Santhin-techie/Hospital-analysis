from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# 1. PAGE SETTINGS AND DATABASE LOCATION
# ============================================================

st.set_page_config(
    page_title="Hospital Pharmacy Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dashboard file is in the main project folder.
PROJECT_DIR = Path(__file__).resolve().parent

DB_PATH = PROJECT_DIR / "database" / "hospital.db"


# ============================================================
# 2. PROFESSIONAL PAGE DESIGN
# ============================================================

st.markdown(
    """
    <style>
        /* ---------- DARK THEME: dark background, white text ---------- */
        :root { color-scheme: dark; }

        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background-color: #0F1720;
            color: #E8EEF4;
        }

        header[data-testid="stHeader"] { background: transparent; }

        .block-container {
            max-width: 1450px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }

        /* All normal text white */
        .stApp p, .stApp li, .stApp label, .stApp span,
        [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] p,
        [data-testid="stCaptionContainer"] {
            color: #E8EEF4;
        }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color: #9FB0C0;
        }
        h1, h2, h3, h4, h5, h6 { color: #FFFFFF !important; }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #121C26;
            border-right: 1px solid #263646;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p {
            color: #FFFFFF;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background-color: #18232F;
            border: 1px solid #2A3A4A;
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 3px 12px rgba(0, 0, 0, 0.35);
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
            color: #9FB0C0;
            font-size: 0.85rem;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: #FFFFFF;
            font-weight: 750;
        }

        /* Tabs */
        [data-testid="stTabs"] button {
            font-weight: 600;
            color: #C5D2DE;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: #4FC3D1;
        }
        [data-baseweb="tab-border"] { background-color: #2A3A4A; }

        /* Dropdowns, multiselects, inputs */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"] {
            background-color: #18232F;
            border-color: #2A3A4A;
            color: #FFFFFF;
        }
        div[data-baseweb="select"] input, div[data-baseweb="select"] span,
        div[data-baseweb="select"] div { color: #FFFFFF; }
        div[data-baseweb="select"] svg { fill: #C5D2DE; }
        span[data-baseweb="tag"] { background-color: #2A4A5C; color: #FFFFFF; }
        span[data-baseweb="tag"] span { color: #FFFFFF; }
        div[data-baseweb="popover"] ul, ul[role="listbox"] { background-color: #18232F; }
        li[role="option"] { color: #FFFFFF; background-color: #18232F; }
        li[role="option"]:hover, li[aria-selected="true"] { background-color: #263646; }

        /* Buttons */
        .stButton button, [data-testid="stDownloadButton"] button {
            background-color: #1F6F7C;
            color: #FFFFFF;
            border: 1px solid #2A8C9B;
        }
        .stButton button:hover, [data-testid="stDownloadButton"] button:hover {
            background-color: #278A9A;
            color: #FFFFFF;
            border-color: #4FC3D1;
        }

        /* Info / warning / success / error boxes */
        div[data-testid="stAlert"] {
            background-color: rgba(79, 195, 209, 0.10);
            border: 1px solid #2A3A4A;
            border-radius: 10px;
        }
        div[data-testid="stAlert"] p, div[data-testid="stAlert"] span { color: #FFFFFF; }

        /* Tables */
        div[data-testid="stDataFrame"] {
            border: 1px solid #2A3A4A;
            border-radius: 10px;
            overflow: hidden;
        }

        /* Expanders */
        [data-testid="stExpander"] {
            background-color: #18232F;
            border: 1px solid #2A3A4A;
            border-radius: 10px;
        }
        [data-testid="stExpander"] summary, [data-testid="stExpander"] p { color: #FFFFFF; }

        hr { border-color: #2A3A4A; }

        .dashboard-header {
            background: linear-gradient(135deg, #123B5D 0%, #0B7285 100%);
            border: 1px solid #2A3A4A;
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 22px;
            color: white;
        }
        .dashboard-title {
            color: #FFFFFF;
            font-size: 31px;
            font-weight: 800;
            margin: 0;
        }
        .dashboard-subtitle {
            color: #D9F2F7;
            font-size: 14px;
            margin-top: 8px;
        }
        .footer {
            border-top: 1px solid #2A3A4A;
            margin-top: 34px;
            padding-top: 16px;
            color: #9FB0C0;
            font-size: 0.78rem;
            text-align: center;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 3. LOAD DATA FROM SQLITE DATABASE
# ============================================================

@st.cache_data(ttl=30)
def load_database():
    """Load dashboard data from SQLite."""

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(str(DB_PATH))

    try:
        medicine_alerts = pd.read_sql(
            "SELECT * FROM medicine_alerts",
            conn
        )

        batch_alerts = pd.read_sql(
            "SELECT * FROM batch_alerts",
            conn
        )

        medicine_forecast = pd.read_sql(
            "SELECT * FROM medicine_forecast",
            conn
        )

        medicine_master = pd.read_sql(
            "SELECT * FROM medicine_master",
            conn
        )

    finally:
        conn.close()

    return (
        medicine_alerts,
        batch_alerts,
        medicine_forecast,
        medicine_master
    )


try:
    alerts, batch_alerts, forecast, medicines = load_database()

except Exception as error:
    st.error("The dashboard could not load the database.")
    st.code(str(error))

    st.info(
        "Check that database/hospital.db exists and that the "
        "forecasting and alert scripts have finished successfully."
    )

    st.stop()


# ============================================================
# 4. CLEAN COLUMN NAMES AND PREPARE DATA
# ============================================================

for dataframe in [
    alerts,
    batch_alerts,
    forecast,
    medicines
]:
    dataframe.columns = dataframe.columns.str.strip()


# Add medicine names if they are not already available.

if (
    "medicine_name" in medicines.columns
    and "medicine_name" not in alerts.columns
):
    alerts = alerts.merge(
        medicines[["medicine_id", "medicine_name"]],
        on="medicine_id",
        how="left"
    )


if (
    "medicine_name" in medicines.columns
    and "medicine_name" not in batch_alerts.columns
):
    batch_alerts = batch_alerts.merge(
        medicines[["medicine_id", "medicine_name"]],
        on="medicine_id",
        how="left"
    )


# Convert inventory columns to numeric values.

alert_numeric_columns = [
    "total_current_stock",
    "forecast_daily_demand",
    "days_of_stock_left",
    "reorder_lead_time_days",
    "projected_stock_at_replenishment",
    "suggested_reorder_qty",
    "avg90_daily_demand"
]

for column in alert_numeric_columns:
    if column in alerts.columns:
        alerts[column] = pd.to_numeric(
            alerts[column],
            errors="coerce"
        )


batch_numeric_columns = [
    "current_quantity",
    "days_to_expiry",
    "projected_unused",
    "wastage_risk_rs",
    "fefo_priority"
]

for column in batch_numeric_columns:
    if column in batch_alerts.columns:
        batch_alerts[column] = pd.to_numeric(
            batch_alerts[column],
            errors="coerce"
        )


if "expiry_date" in batch_alerts.columns:
    batch_alerts["expiry_date"] = pd.to_datetime(
        batch_alerts["expiry_date"],
        errors="coerce"
    )


# Check essential columns before continuing.

required_columns = [
    "medicine_id",
    "shortage_status",
    "trend_label"
]

missing_columns = [
    column
    for column in required_columns
    if column not in alerts.columns
]

if missing_columns:
    st.error(
        "The medicine_alerts table is missing: "
        + ", ".join(missing_columns)
    )

    st.info(
        "Run calculate_alerts.py again and refresh the dashboard."
    )

    st.stop()


# ============================================================
# 5. SIDEBAR FILTERS
# ============================================================

with st.sidebar:

    st.markdown('<a href="/" target="_self" style="display:inline-block; margin-bottom:12px; font-weight:700; text-decoration:none; color:#4FC3D1;">← Back to Master Console</a>', unsafe_allow_html=True)
    st.markdown("## Hospital Pharmacy")
    st.caption("Inventory analytics and decision support")

    st.divider()

    st.subheader("Dashboard Filters")

    medicine_options = sorted(
        alerts["medicine_id"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_medicines = st.multiselect(
        "Medicine",
        options=medicine_options,
        default=medicine_options
    )

    status_options = [
        "Critical",
        "Warning",
        "Safe"
    ]

    selected_statuses = st.multiselect(
        "Stock status",
        options=status_options,
        default=status_options
    )

    trend_options = [
        "↑ Rising",
        "→ Stable",
        "↓ Falling"
    ]

    selected_trends = st.multiselect(
        "Demand trend",
        options=trend_options,
        default=trend_options
    )

    expiry_window = st.selectbox(
        "Expiry period",
        options=[
            "All batches",
            "Next 7 days",
            "Next 30 days",
            "Next 60 days"
        ],
        index=2
    )

    st.divider()

    if st.button(
        "Refresh dashboard",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.rerun()

    st.caption("Database: SQLite")
    st.caption("UI version: dark theme v2")
    st.caption("Forecasting: Prophet")


# ============================================================
# 6. APPLY INVENTORY FILTERS
# ============================================================

filtered = alerts[
    alerts["medicine_id"].isin(selected_medicines)
    & alerts["shortage_status"].isin(selected_statuses)
    & alerts["trend_label"].isin(selected_trends)
].copy()


# ============================================================
# 7. DASHBOARD HEADER
# ============================================================

st.markdown(
    """
    <div class="dashboard-header">
        <div class="dashboard-title">
            Hospital Pharmacy Analytics
        </div>
        <div class="dashboard-subtitle">
            Medicine inventory, demand forecasting,
            expiry monitoring and replenishment decision support
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(
    "The overview shows all medicines. Sidebar filters apply "
    "to the charts and detailed analysis below."
)


# ============================================================
# 8. CALCULATE SUMMARY VALUES
# ============================================================

total_medicines = int(
    alerts["medicine_id"].nunique()
)

if "total_current_stock" in alerts.columns:
    total_stock = int(
        alerts["total_current_stock"].fillna(0).sum()
    )
else:
    total_stock = 0


critical_count = int(
    (alerts["shortage_status"] == "Critical").sum()
)

warning_count = int(
    (alerts["shortage_status"] == "Warning").sum()
)

safe_count = int(
    (alerts["shortage_status"] == "Safe").sum()
)


if "suggested_reorder_qty" in alerts.columns:
    total_reorder = int(
        alerts["suggested_reorder_qty"].fillna(0).sum()
    )
else:
    total_reorder = 0


if "wastage_risk_rs" in batch_alerts.columns:
    total_wastage = int(
        batch_alerts["wastage_risk_rs"].fillna(0).sum()
    )
else:
    total_wastage = 0


if "days_to_expiry" in batch_alerts.columns:
    expiring_30 = int(
        (
            (batch_alerts["days_to_expiry"] >= 0)
            & (batch_alerts["days_to_expiry"] <= 30)
        ).sum()
    )
else:
    expiring_30 = 0


# ============================================================
# 9. EXECUTIVE OVERVIEW
# ============================================================

st.subheader("Executive Overview")

row_one = st.columns(4)

with row_one[0]:
    st.metric(
        label="Medicines monitored",
        value=f"{total_medicines:,}"
    )

with row_one[1]:
    st.metric(
        label="Current stock",
        value=f"{total_stock:,}",
        help="Total current stock across the monitored medicines."
    )

with row_one[2]:
    st.metric(
        label="Critical medicines",
        value=f"{critical_count:,}",
        help=(
            "Stock is predicted to run out before supplier "
            "replenishment."
        )
    )

with row_one[3]:
    st.metric(
        label="Batches expiring within 30 days",
        value=f"{expiring_30:,}"
    )


row_two = st.columns(3)

with row_two[0]:
    st.metric(
        label="Warning medicines",
        value=f"{warning_count:,}"
    )

with row_two[1]:
    st.metric(
        label="Estimated wastage risk",
        value=f"₹{total_wastage:,}",
        help=(
            "Estimated financial value of projected unused "
            "batch stock."
        )
    )

with row_two[2]:
    st.metric(
        label="Suggested reorder quantity",
        value=f"{total_reorder:,}",
        help=(
            "Total units suggested by the current 30-day "
            "planning rule."
        )
    )


# ============================================================
# 10. PRIORITY MESSAGE
# ============================================================

if critical_count > 0:
    st.warning(
        f"{critical_count} medicine(s) are classified as critical. "
        "Review stock levels, supplier lead times and expected "
        "stockout dates."
    )
else:
    st.success(
        "No medicines are currently classified as critical."
    )


# ============================================================
# 11. INVENTORY OVERVIEW CHARTS
# ============================================================

st.subheader("Inventory Overview")

chart_left, chart_right = st.columns(2)


# ------------------------------------------------------------
# CHART 1: STOCK STATUS DISTRIBUTION
# ------------------------------------------------------------

with chart_left:

    st.markdown("#### Stock status distribution")

    status_data = pd.DataFrame({
        "Stock status": [
            "Critical",
            "Warning",
            "Safe"
        ],
        "Number of medicines": [
            critical_count,
            warning_count,
            safe_count
        ]
    })

    if total_medicines > 0:

        status_figure = px.pie(
            status_data,
            names="Stock status",
            values="Number of medicines",
            hole=0.58,
            color="Stock status",
            color_discrete_map={
                "Critical": "#C94C4C",
                "Warning": "#D99A22",
                "Safe": "#35966B"
            }
        )

        status_figure.update_traces(
            textposition="inside",
            textinfo="percent+label"
        )

        status_figure.update_layout(
            height=350,
            margin=dict(
                l=15,
                r=15,
                t=20,
                b=15
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False
        )

        st.plotly_chart(
            status_figure,
            use_container_width=True
        )

    else:
        st.info("No medicine records are available.")


# ------------------------------------------------------------
# CHART 2: TOP SUGGESTED REORDERS
# ------------------------------------------------------------

with chart_right:

    st.markdown("#### Highest suggested reorder quantities")

    reorder_data = filtered.copy()

    if "suggested_reorder_qty" in reorder_data.columns:
        reorder_data = reorder_data[
            reorder_data["suggested_reorder_qty"] > 0
        ].copy()

    if not reorder_data.empty:

        if "medicine_name" in reorder_data.columns:
            reorder_data["Medicine"] = (
                reorder_data["medicine_name"]
                .fillna(reorder_data["medicine_id"])
            )
        else:
            reorder_data["Medicine"] = (
                reorder_data["medicine_id"]
            )

        reorder_data = reorder_data.sort_values(
            "suggested_reorder_qty",
            ascending=False
        ).head(8)

        reorder_figure = px.bar(
            reorder_data,
            x="suggested_reorder_qty",
            y="Medicine",
            orientation="h",
            labels={
                "suggested_reorder_qty": "Suggested units",
                "Medicine": "Medicine"
            },
            color_discrete_sequence=["#287D8E"]
        )

        reorder_figure.update_layout(
            height=350,
            margin=dict(
                l=15,
                r=15,
                t=20,
                b=15
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(
                categoryorder="total ascending"
            ),
            showlegend=False
        )

        st.plotly_chart(
            reorder_figure,
            use_container_width=True
        )

    else:
        st.info(
            "No positive reorder quantities are available "
            "for the selected filters."
        )


# ============================================================
# 12. DEMAND TREND ANALYSIS
# ============================================================

st.subheader("Demand Trend Analysis")

st.caption(
    "Compare predicted daily demand with the recent "
    "90-day average for the selected medicines."
)


if (
    "forecast_daily_demand" in filtered.columns
    and "avg90_daily_demand" in filtered.columns
    and not filtered.empty
):

    trend_data = filtered.copy()

    if "medicine_name" in trend_data.columns:
        trend_data["Medicine"] = (
            trend_data["medicine_name"]
            .fillna(trend_data["medicine_id"])
        )
    else:
        trend_data["Medicine"] = trend_data["medicine_id"]

    trend_data = trend_data.sort_values(
        "forecast_daily_demand",
        ascending=False
    ).head(10)

    trend_long = trend_data[
        [
            "Medicine",
            "forecast_daily_demand",
            "avg90_daily_demand"
        ]
    ].melt(
        id_vars="Medicine",
        var_name="Demand measure",
        value_name="Units per day"
    )

    trend_long["Demand measure"] = (
        trend_long["Demand measure"].replace({
            "forecast_daily_demand": "Predicted demand",
            "avg90_daily_demand": "90-day average"
        })
    )

    trend_figure = px.bar(
        trend_long,
        x="Medicine",
        y="Units per day",
        color="Demand measure",
        barmode="group",
        color_discrete_map={
            "Predicted demand": "#287D8E",
            "90-day average": "#A8B5C0"
        }
    )

    trend_figure.update_layout(
        height=390,
        margin=dict(
            l=15,
            r=15,
            t=20,
            b=20
        ),
        template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_tickangle=-25,
        legend_title_text=""
    )

    st.plotly_chart(
        trend_figure,
        use_container_width=True
    )

else:
    st.info(
        "Forecast and 90-day average columns are not available."
    )


# ============================================================
# 13. DETAILED ANALYSIS TABS
# ============================================================

tab_inventory, tab_critical, tab_expiry, tab_forecast = st.tabs([
    "Inventory details",
    "Critical medicines",
    "Expiry and FEFO",
    "Demand forecast"
])


# ============================================================
# TAB 1: INVENTORY DETAILS
# ============================================================

with tab_inventory:

    st.subheader("Medicine Inventory")

    st.caption(
        "Medicine-level stock, forecast, supplier lead time "
        "and reorder recommendations."
    )

    if filtered.empty:

        st.info("No medicines match the selected filters.")

    else:

        inventory_columns = [
            "medicine_id",
            "medicine_name",
            "total_current_stock",
            "forecast_daily_demand",
            "days_of_stock_left",
            "reorder_lead_time_days",
            "projected_stock_at_replenishment",
            "expected_stockout_date",
            "suggested_reorder_qty",
            "shortage_status",
            "trend_label",
            "recommended_action"
        ]

        available_columns = [
            column
            for column in inventory_columns
            if column in filtered.columns
        ]

        inventory_display = filtered[
            available_columns
        ].copy()

        inventory_display = inventory_display.rename(
            columns={
                "medicine_id": "Medicine ID",
                "medicine_name": "Medicine name",
                "total_current_stock": "Current stock",
                "forecast_daily_demand": "Predicted daily demand",
                "days_of_stock_left": "Days of stock left",
                "reorder_lead_time_days": "Supplier lead time (days)",
                "projected_stock_at_replenishment": "Projected stock at delivery",
                "expected_stockout_date": "Expected stockout date",
                "suggested_reorder_qty": "Suggested reorder quantity",
                "shortage_status": "Stock status",
                "trend_label": "Demand trend",
                "recommended_action": "Recommended action"
            }
        )

        numeric_columns = [
            "Current stock",
            "Predicted daily demand",
            "Days of stock left",
            "Supplier lead time (days)",
            "Projected stock at delivery",
            "Suggested reorder quantity"
        ]

        for column in numeric_columns:

            if column in inventory_display.columns:
                inventory_display[column] = pd.to_numeric(
                    inventory_display[column],
                    errors="coerce"
                ).round(1)

        st.dataframe(
            inventory_display,
            use_container_width=True,
            hide_index=True,
            height=480
        )


# ============================================================
# TAB 2: CRITICAL MEDICINES
# ============================================================

with tab_critical:

    st.subheader("Critical Stock Monitor")

    critical_data = filtered[
        filtered["shortage_status"] == "Critical"
    ].copy()

    if critical_data.empty:

        st.success(
            "No critical medicines match the selected filters."
        )

    else:

        st.warning(
            f"{len(critical_data)} medicine(s) need priority review."
        )

        critical_columns = [
            "medicine_id",
            "medicine_name",
            "total_current_stock",
            "forecast_daily_demand",
            "days_of_stock_left",
            "reorder_lead_time_days",
            "projected_stock_at_replenishment",
            "expected_stockout_date",
            "suggested_reorder_qty",
            "recommended_action"
        ]

        available_columns = [
            column
            for column in critical_columns
            if column in critical_data.columns
        ]

        critical_display = critical_data[
            available_columns
        ].copy()

        critical_display = critical_display.rename(
            columns={
                "medicine_id": "Medicine ID",
                "medicine_name": "Medicine name",
                "total_current_stock": "Current stock",
                "forecast_daily_demand": "Predicted daily demand",
                "days_of_stock_left": "Days of stock left",
                "reorder_lead_time_days": "Supplier lead time (days)",
                "projected_stock_at_replenishment": "Projected stock at delivery",
                "expected_stockout_date": "Expected stockout date",
                "suggested_reorder_qty": "Suggested reorder quantity",
                "recommended_action": "Recommended action"
            }
        )

        st.dataframe(
            critical_display,
            use_container_width=True,
            hide_index=True,
            height=420
        )


# ============================================================
# TAB 3: EXPIRY AND FEFO
# ============================================================

with tab_expiry:

    st.subheader("Batch Expiry Risk")

    st.caption(
        "Batch-level expiry tracking. "
        "FEFO means First Expiry, First Out."
    )

    expiry_data = batch_alerts.copy()

    if "medicine_id" in expiry_data.columns:

        expiry_data = expiry_data[
            expiry_data["medicine_id"].isin(
                selected_medicines
            )
        ].copy()

    if "days_to_expiry" in expiry_data.columns:

        if expiry_window == "Next 7 days":

            expiry_data = expiry_data[
                (expiry_data["days_to_expiry"] >= 0)
                & (expiry_data["days_to_expiry"] <= 7)
            ]

        elif expiry_window == "Next 30 days":

            expiry_data = expiry_data[
                (expiry_data["days_to_expiry"] >= 0)
                & (expiry_data["days_to_expiry"] <= 30)
            ]

        elif expiry_window == "Next 60 days":

            expiry_data = expiry_data[
                (expiry_data["days_to_expiry"] >= 0)
                & (expiry_data["days_to_expiry"] <= 60)
            ]

    if expiry_data.empty:

        st.info(
            "No batches match the selected expiry period."
        )

    else:

        expiry_columns = [
            "batch_id",
            "medicine_id",
            "medicine_name",
            "current_quantity",
            "expiry_date",
            "days_to_expiry",
            "expiry_status",
            "expiry_action",
            "projected_unused",
            "wastage_risk_rs",
            "fefo_priority"
        ]

        available_columns = [
            column
            for column in expiry_columns
            if column in expiry_data.columns
        ]

        expiry_display = expiry_data[
            available_columns
        ].copy()

        expiry_display = expiry_display.rename(
            columns={
                "batch_id": "Batch ID",
                "medicine_id": "Medicine ID",
                "medicine_name": "Medicine name",
                "current_quantity": "Batch stock",
                "expiry_date": "Expiry date",
                "days_to_expiry": "Days to expiry",
                "expiry_status": "Expiry status",
                "expiry_action": "Expiry action",
                "projected_unused": "Projected unused units",
                "wastage_risk_rs": "Estimated wastage risk (₹)",
                "fefo_priority": "FEFO priority"
            }
        )

        if "Days to expiry" in expiry_display.columns:

            expiry_display = expiry_display.sort_values(
                "Days to expiry",
                na_position="last"
            )

        st.dataframe(
            expiry_display,
            use_container_width=True,
            hide_index=True,
            height=430
        )

        st.info(
            "Expired batches must be handled according to hospital "
            "policy. For unexpired stock, prioritize batches with the "
            "earliest expiry date when appropriate. Expiry does not "
            "automatically trigger a reorder."
        )


# ============================================================
# TAB 4: DEMAND FORECAST
# ============================================================

with tab_forecast:

    st.subheader("Medicine Demand Forecast")

    st.caption(
        "Predicted daily demand compared with the recent "
        "90-day average."
    )

    forecast_display = forecast.copy()

    if (
        "medicine_name" not in forecast_display.columns
        and "medicine_name" in medicines.columns
    ):

        forecast_display = forecast_display.merge(
            medicines[
                ["medicine_id", "medicine_name"]
            ],
            on="medicine_id",
            how="left"
        )

    if "medicine_id" in forecast_display.columns:

        forecast_display = forecast_display[
            forecast_display["medicine_id"].isin(
                selected_medicines
            )
        ].copy()

    forecast_display = forecast_display.rename(
        columns={
            "medicine_id": "Medicine ID",
            "medicine_name": "Medicine name",
            "forecast_daily_demand": "Predicted daily demand",
            "avg90_daily_demand": "90-day average demand"
        }
    )

    for column in [
        "Predicted daily demand",
        "90-day average demand"
    ]:

        if column in forecast_display.columns:

            forecast_display[column] = pd.to_numeric(
                forecast_display[column],
                errors="coerce"
            ).round(2)

    if forecast_display.empty:

        st.info(
            "No forecast rows match the selected medicines."
        )

    else:

        st.dataframe(
            forecast_display,
            use_container_width=True,
            hide_index=True,
            height=400
        )


# ============================================================
# 14. DECISION SUPPORT SUMMARY
# ============================================================

st.subheader("Decision Support")

decision_one, decision_two, decision_three = st.columns(3)

with decision_one:

    st.markdown("**Replenishment planning**")

    st.write(
        f"{total_reorder:,} units are suggested under the current "
        "30-day stock planning rule. Confirm orders against actual "
        "usage, supplier lead time and hospital policy."
    )


with decision_two:

    st.markdown("**Expiry management**")

    st.write(
        f"{expiring_30:,} batch(es) are expected to expire within "
        "30 days. Review these batches and prioritize FEFO where "
        "appropriate."
    )


with decision_three:

    st.markdown("**Financial risk**")

    st.write(
        f"The estimated value of projected unused batch stock is "
        f"₹{total_wastage:,}. This is an estimate, not a confirmed loss."
    )


# ============================================================
# 15. FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div class="footer">
        Hospital Pharmacy Analytics |
        Inventory Monitoring |
        Demand Forecasting |
        Expiry and FEFO Management |
        Replenishment Support
        <br><br>
        This dashboard supports pharmacy decisions and does not
        replace professional review or hospital policy.
    </div>
    """,
    unsafe_allow_html=True
)