from pathlib import Path
from datetime import datetime
import subprocess
import sys


import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SIMULATION_SCRIPT = (
    BASE_DIR
    / "src"
    / "simulate_live.py"
)

HOSPITAL_FILE = (
    BASE_DIR
    / "outputs"
    / "simulated_live_hospital_summary.csv"
)

DEPARTMENT_FILE = (
    BASE_DIR
    / "outputs"
    / "simulated_live_availability.csv"
)

FORECAST_FILE = (
    BASE_DIR
    / "outputs"
    / "dept_forecast_results.csv"
)



ALERT_EXPLANATIONS_FILE = (
    BASE_DIR
    / "outputs"
    / "alert_explanations.csv"
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Hospital Resource Intelligence",
    page_icon="🏥",
    layout="wide"
)

# ============================================================
# DASHBOARD STYLE
# ============================================================

st.markdown(
    """
    <style>

    /* Main dashboard container */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }

    /* Reduce vertical gaps between dashboard sections */
    div[data-testid="stVerticalBlock"] {
        gap: 0.55rem;
    }

    /* Compact metric cards */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #dbe5ee;
        border-radius: 8px;
        padding: 5px 12px;
        box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.06);
    }

    /* Metric label */
    div[data-testid="stMetricLabel"] {
        font-size: 13px;
    }

    /* Metric value */
    div[data-testid="stMetricValue"] {
        font-size: 22px;
    }

    /* Compact headings */
    h2 {
        margin-top: 0.4rem !important;
        margin-bottom: 0.4rem !important;
    }

    h3 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }

    /* Make horizontal dividers compact */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* Compact dataframe area */
    div[data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        border-right: 1px solid #dbe5ee;
    }
    /* Compact select boxes */
div[data-baseweb="select"] > div {
    min-height: 38px;
}

/* Reduce paragraph/caption spacing */
p {
    margin-bottom: 0.25rem;
}
/* Reduce paragraph/caption spacing */
p {
    margin-bottom: 0.25rem;
}


/* ===== FINAL COMPACT DASHBOARD SPACING ===== */

/* Smaller section headings */
h2 {
    font-size: 24px !important;
    margin-top: 0.15rem !important;
    margin-bottom: 0.20rem !important;
}

h3 {
    font-size: 20px !important;
    margin-top: 0.15rem !important;
    margin-bottom: 0.20rem !important;
}

h5 {
    font-size: 16px !important;
    margin-top: 0.15rem !important;
    margin-bottom: 0.15rem !important;
}

/* Reduce general vertical spacing */
div[data-testid="stVerticalBlock"] {
    gap: 0.35rem;
}

/* Smaller normal text */
p {
    font-size: 13px;
    margin-top: 0 !important;
    margin-bottom: 0.15rem !important;
}

/* Compact dropdown labels */
label {
    font-size: 13px !important;
}

/* Compact dropdown boxes */
div[data-baseweb="select"] > div {
    min-height: 34px !important;
    font-size: 13px !important;
}

/* Compact KPI values */
div[data-testid="stMetric"] {
    padding: 4px 10px !important;
}

div[data-testid="stMetricLabel"] {
    font-size: 12px !important;
}

div[data-testid="stMetricValue"] {
    font-size: 20px !important;
}

/* Smaller divider gaps */
hr {
    margin-top: 0.25rem !important;
    margin-bottom: 0.25rem !important;
}
/* ===== FINAL HEIGHT COMPACTION ===== */

/* Main page top/bottom space */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 0.3rem !important;
}

/* Reduce spacing between Streamlit elements */
div[data-testid="stVerticalBlock"] {
    gap: 0.20rem !important;
}

/* Compact headings */
h1 {
    font-size: 25px !important;
    margin-top: 0.1rem !important;
    margin-bottom: 0.15rem !important;
}

h2 {
    font-size: 21px !important;
    margin-top: 0.1rem !important;
    margin-bottom: 0.15rem !important;
}

h3 {
    font-size: 18px !important;
    margin-top: 0.1rem !important;
    margin-bottom: 0.15rem !important;
}

/* Very small divider spacing */
hr {
    margin-top: 0.15rem !important;
    margin-bottom: 0.15rem !important;
}

/* Compact captions and normal text */
p {
    margin-top: 0 !important;
    margin-bottom: 0.1rem !important;
}

</style>
""",
unsafe_allow_html=True
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🏥 HRI")
    st.caption("Hospital Resource Intelligence")

    st.divider()

    st.markdown("### Navigation")

    selected_page = st.radio(
        "Go to",
        [
            "🏠 Dashboard Overview",
            "🏥 Hospital Details",
            "🛏️ Department Details",
        ],
        label_visibility="collapsed",
        key="sidebar_navigation"
    )

    st.divider()

    st.markdown("### System")

    st.success("● Simulation Active")
    st.caption("Auto-update every 30 sec")


# ============================================================
# AUTOMATIC LIVE UPDATE
# ============================================================

refresh_count = st_autorefresh(
    interval=30 * 1000,
    limit=None,
    key="live_dashboard_refresh"
)


# ============================================================
# RUN SIMULATION ONLY ON A NEW TIMER REFRESH
# ============================================================

if "last_simulated_refresh" not in st.session_state:
    st.session_state.last_simulated_refresh = 0


if refresh_count > st.session_state.last_simulated_refresh:

    result = subprocess.run(
        [sys.executable, str(SIMULATION_SCRIPT)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True
    )

    if result.returncode == 0:

        st.session_state.last_simulated_refresh = refresh_count

    else:

        st.error("Simulation update failed.")



# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    hospital_df = pd.read_csv(HOSPITAL_FILE)
    department_df = pd.read_csv(DEPARTMENT_FILE)
    forecast_df = pd.read_csv(FORECAST_FILE)
    alert_df = pd.read_csv(ALERT_EXPLANATIONS_FILE)

    return hospital_df, department_df, forecast_df, alert_df


hospital_df, department_df, forecast_df, alert_df = load_data()


# ============================================================
# PREPARE LATEST ML FORECAST
# ============================================================

forecast_df["date"] = pd.to_datetime(
    forecast_df["date"]
)

latest_forecast_date = forecast_df[
    "date"
].max()

latest_forecast = forecast_df[
    forecast_df["date"] == latest_forecast_date
].copy()


# The model predicts occupancy 7 days after the forecast origin
forecast_target_date = (
    latest_forecast_date
    + pd.Timedelta(days=7)
)


# Dashboard risk categories
def get_risk_level(probability):

    if probability >= 0.70:
        return "HIGH"

    elif probability >= 0.40:
        return "MEDIUM"

    else:
        return "LOW"


latest_forecast["risk_level"] = (
    latest_forecast[
        "breach_probability"
    ].apply(get_risk_level)
)


# ============================================================
# LAST UPDATED TIME
# ============================================================

if "simulation_timestamp" in hospital_df.columns:
    last_update = hospital_df[
        "simulation_timestamp"
    ].iloc[0]
else:
    last_update = "Not available"

def get_capacity_status(row):

    occupancy = row["current_occupancy_pct"]
    available = row["available_beds"]

    # Critical comes first because it has highest priority
    if occupancy >= 90 or available == 0:
        return "🔴 CRITICAL"

    # Very limited remaining capacity
    elif occupancy >= 85 or available == 1:
        return "🟠 HIGH"

    # Capacity beginning to tighten
    elif occupancy >= 70 or available <= 3:
        return "🟡 MODERATE"

    # Comfortable current capacity
    else:
        return "🟢 AVAILABLE"


# ============================================================
# PAGE ROUTING
# ============================================================

if selected_page == "🏠 Dashboard Overview":

    # ============================================================
    # DASHBOARD HEADER
    # ============================================================

    st.markdown(
        f"""
    <div style="background:#123f63;padding:8px 16px;border-radius:7px;color:white;display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
    <div style="font-size:21px;font-weight:700;">🏥 Hospital Resource Intelligence</div>
    <div style="font-size:12px;font-weight:500;">{last_update} &nbsp;&nbsp; 🟢 Live Simulation</div>
    </div>
    """,
        unsafe_allow_html=True
    )


    # ============================================================
    # TOP METRICS
    # ============================================================

    total_hospitals = len(hospital_df)

    total_capacity = hospital_df[
        "total_capacity"
    ].sum()

    total_occupied = hospital_df[
        "total_occupied"
    ].sum()

    total_available = hospital_df[
        "total_available"
    ].sum()


    # ------------------------------------------------------------
    # KPI CARDS
    # ------------------------------------------------------------

    st.markdown("### 📊 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🏥 Hospitals",
            value=f"{total_hospitals}"
        )

    with col2:
        st.metric(
            label="🛏️ Total Beds",
            value=f"{int(total_capacity):,}"
        )

    with col3:
        st.metric(
            label="🔴 Occupied Beds",
            value=f"{int(total_occupied):,}"
        )

    with col4:
        st.metric(
            label="🟢 Available Beds",
            value=f"{int(total_available):,}"
        )
    # ============================================================
    # FORECAST + CAPACITY RISK OVERVIEW
    # ============================================================

    st.divider()

    # ------------------------------------------------------------
    # FORECAST SUMMARY CALCULATIONS
    # ------------------------------------------------------------

    high_risk_count = (
        latest_forecast["risk_level"] == "HIGH"
    ).sum()

    medium_risk_count = (
        latest_forecast["risk_level"] == "MEDIUM"
    ).sum()

    low_risk_count = (
        latest_forecast["risk_level"] == "LOW"
    ).sum()

    average_predicted_occupancy = (
        latest_forecast["predicted_occupancy_7d"].mean()
    )

    highest_forecast_row = (
        latest_forecast
        .sort_values(
            "predicted_occupancy_7d",
            ascending=False
        )
        .iloc[0]
    )

    highest_risk_row = (
        latest_forecast
        .sort_values(
            "breach_probability",
            ascending=False
        )
        .iloc[0]
    )

    # ============================================================
    # FORECAST VS CAPACITY
    # ============================================================

    current_date = datetime.now()
    next_7_days = current_date + pd.Timedelta(days=7)

    st.subheader(
        f"📈 Forecast vs Capacity (Next 7 Days) — "
        f"{current_date.strftime('%d %b %Y')} → "
        f"{next_7_days.strftime('%d %b %Y')}"
    )

    # ------------------------------------------------------------
    # FORECAST SUMMARY
    # ------------------------------------------------------------
    forecast_col1, forecast_col2, forecast_col3, forecast_col4 = st.columns(4)

    with forecast_col1:
        st.markdown(
            f"**{average_predicted_occupancy:.1f}%**  \n"
            "<small>Average Predicted</small>",
            unsafe_allow_html=True
        )

    with forecast_col2:
        st.markdown(
            f"**{highest_forecast_row['predicted_occupancy_7d']:.1f}%**  \n"
            "<small>Highest Predicted</small>",
            unsafe_allow_html=True
        )

    with forecast_col3:
        st.markdown(
            f"**🔴 {int(high_risk_count)}**  \n"
            "<small>High Risk</small>",
            unsafe_allow_html=True
        )

    with forecast_col4:
        st.markdown(
            f"**🟠 {int(medium_risk_count)}**  \n"
            "<small>Medium Risk</small>",
            unsafe_allow_html=True
        )



    # ============================================================
    # CURRENT CAPACITY + RISK EXPLANATION
    # ============================================================

    st.divider()

    capacity_panel, explanation_panel = st.columns([1.45, 1])

    with capacity_panel:

        st.subheader("🏥 Current Capacity Overview")

        # ------------------------------------------------------------
        # FILTERS
        # ------------------------------------------------------------

        filter_col1, filter_col2 = st.columns(2)
        hospitals = sorted(
            department_df["hospital_name_department"]
            .dropna()
            .unique()
        )

        departments = sorted(
            department_df["department"]
            .dropna()
            .unique()
        )


    with filter_col1:

        selected_hospital = st.selectbox(
            "Select Hospital",
            ["All Hospitals"] + hospitals,
            key="capacity_hospital_filter"
        )


    with filter_col2:

        selected_department = st.selectbox(
            "Select Department",
            ["All Departments"] + departments,
            key="capacity_department_filter"
        )


    # ------------------------------------------------------------
    # APPLY FILTERS
    # ------------------------------------------------------------

    capacity_df = department_df.copy()


    if selected_hospital != "All Hospitals":

        capacity_df = capacity_df[
            capacity_df["hospital_name_department"]
            == selected_hospital
        ]


    if selected_department != "All Departments":

        capacity_df = capacity_df[
            capacity_df["department"]
            == selected_department
        ]


    # ------------------------------------------------------------
    # CALCULATE CURRENT OCCUPANCY
    # ------------------------------------------------------------

    capacity_df["current_occupancy_pct"] = (
        capacity_df["occupied_beds"]
        / capacity_df["department_bed_capacity"]
        * 100
    ).round(1)


    # ------------------------------------------------------------
    # CURRENT CAPACITY STATUS
    # Uses both occupancy % and available beds
    # ------------------------------------------------------------




    capacity_df["Current Status"] = capacity_df.apply(
        get_capacity_status,
        axis=1
    )


    # ------------------------------------------------------------
    # PREPARE DISPLAY TABLE
    # ------------------------------------------------------------

    capacity_display = capacity_df[
        [
            "hospital_name_department",
            "department",
            "department_bed_capacity",
            "occupied_beds",
            "available_beds",
            "current_occupancy_pct",
            "Current Status",
        ]
    ].copy()


    capacity_display = capacity_display.rename(
        columns={
            "hospital_name_department": "Hospital",
            "department": "Department",
            "department_bed_capacity": "Capacity",
            "occupied_beds": "Occupied",
            "available_beds": "Available",
            "current_occupancy_pct": "Occupancy %",
        }
    )


    # Highest current occupancy first
    capacity_display = capacity_display.sort_values(
        "Occupancy %",
        ascending=False
    )


    # ------------------------------------------------------------
    # COMPACT TABLE
    # ------------------------------------------------------------

    with capacity_panel:

        st.dataframe(
            capacity_display,
            width="stretch",
            hide_index=True,
            height=135,
            column_config={
                "Hospital": st.column_config.TextColumn(
                    "Hospital",
                    width="medium"
                ),
                "Department": st.column_config.TextColumn(
                    "Department",
                    width="small"
                ),
                "Capacity": st.column_config.NumberColumn(
                    "Capacity",
                    width="small"
                ),
                "Occupied": st.column_config.NumberColumn(
                    "Occupied",
                    width="small"
                ),
                "Available": st.column_config.NumberColumn(
                    "Available",
                    width="small"
                ),
                "Occupancy %": st.column_config.NumberColumn(
                    "Occupancy %",
                    format="%.1f%%",
                    width="small"
                ),
                "Current Status": st.column_config.TextColumn(
                    "Status",
                    width="small"
                ),
            }
        )


    # ============================================================
    # RIGHT — MODEL EXPLANATION
    # ============================================================

    with explanation_panel:

        st.subheader("🧠 Risk Explanation")


        # Convert date column
        alert_df["date"] = pd.to_datetime(
            alert_df["date"]
        )

        # Latest explanation date
        latest_alert_date = alert_df["date"].max()

        latest_alerts = alert_df[
            alert_df["date"] == latest_alert_date
        ].copy()

        # Highest breach probability first
        latest_alerts = latest_alerts.sort_values(
            "breach_probability",
            ascending=False
        )

        # Create alert selector label
        latest_alerts["alert_label"] = (
            latest_alerts["hospital_name"]
            + " — "
            + latest_alerts["department"]
        )

        selected_alert = st.selectbox(
            "Select Capacity Alert",
            latest_alerts["alert_label"].tolist(),
            key="shap_alert_selector"
        )

        selected_row = latest_alerts[
            latest_alerts["alert_label"]
            == selected_alert
        ].iloc[0]


        # --------------------------------------------------------
        # PREDICTION SUMMARY
        # --------------------------------------------------------

        prediction_col1, prediction_col2 = st.columns(2)

        prediction_col1.metric(
            "Predicted Occupancy",
            f"{selected_row['predicted_occupancy_7d']:.1f}%"
        )

        prediction_col2.metric(
            "Breach Probability",
            f"{selected_row['breach_probability'] * 100:.1f}%"
        )

    # ============================================================
    # TOP MODEL DRIVERS - FULL WIDTH
    # ============================================================

    st.markdown("### 🧠 Top Model Drivers")

    feature_name_map = {
        "rolling_14d_occupancy": "14-Day Average Occupancy",
        "rolling_7d_occupancy": "7-Day Average Occupancy",
        "department_bed_capacity": "Department Bed Capacity",
        "admissions_7d_avg": "7-Day Average Admissions",
        "discharges_7d_avg": "7-Day Average Discharges",
        "lag_1_occupancy": "Previous Day Occupancy",
        "lag_7_occupancy": "Occupancy 7 Days Ago",
        "occupancy_trend_7d": "7-Day Occupancy Trend",
        "avg_temperature_c": "Average Temperature",
        "rainfall_mm": "Rainfall",
        "accident_cases": "Accident Cases",
        "holiday_flag": "Holiday",
        "month": "Month",
        "day_of_week": "Day of Week",
        "week_of_year": "Week of Year",
        "is_weekend": "Weekend",
    }

    driver_data = pd.DataFrame(
        {
            "Rank": [1, 2, 3],
            "Feature": [
                feature_name_map.get(
                    selected_row["driver_1_feature"],
                    selected_row["driver_1_feature"]
                ),
                feature_name_map.get(
                    selected_row["driver_2_feature"],
                    selected_row["driver_2_feature"]
                ),
                feature_name_map.get(
                    selected_row["driver_3_feature"],
                    selected_row["driver_3_feature"]
                ),
            ],
            "Value": [
                selected_row["driver_1_value"],
                selected_row["driver_2_value"],
                selected_row["driver_3_value"],
            ],
            "Contribution": [
                selected_row["driver_1_shap"],
                selected_row["driver_2_shap"],
                selected_row["driver_3_shap"],
            ],
        }
    )

    st.dataframe(
        driver_data,
        width="stretch",
        hide_index=True,
        height=140
    )


# ============================================================
# HOSPITAL DETAILS PAGE
# ============================================================

if selected_page == "🏥 Hospital Details":
    st.divider()
    st.header("🏥 Hospital Details")

    selected_detail_hospital = st.selectbox(
        "Select Hospital",
        sorted(
            department_df["hospital_name_department"]
            .dropna()
            .unique()
        ),
        key="hospital_details_selector"
    )

    hospital_detail_df = department_df[
        department_df["hospital_name_department"]
        == selected_detail_hospital
        ].copy()

    # ============================================================
    # RECENT BED EVENTS
    # ============================================================

    st.divider()
    st.subheader("📋 Recent Bed Events")

    hospital_events = hospital_detail_df[
        hospital_detail_df["simulated_event"].isin(
            ["ADMISSION", "DISCHARGE"]
        )
    ].copy()

    event_display = hospital_events[
        [
            "hospital_name_department",
            "department",
            "simulated_event"
        ]
    ].copy()

    event_display = event_display.rename(
        columns={
            "hospital_name_department": "Hospital",
            "department": "Department",
            "simulated_event": "Latest Event"
        }
    )

    event_display["Latest Event"] = event_display["Latest Event"].map({
        "ADMISSION": "🔴 ADMISSION",
        "DISCHARGE": "🟢 DISCHARGE"
    })

    if not event_display.empty:
        st.dataframe(
            event_display,
            width="stretch",
            hide_index=True,
            height=150
        )
    else:
        st.info(
            "No recent admission or discharge event for this hospital."
        )

    # ------------------------------------------------------------
    # HOSPITAL SUMMARY
    # ------------------------------------------------------------

    hospital_total_capacity = (
        hospital_detail_df["department_bed_capacity"].sum()
    )

    hospital_total_occupied = (
        hospital_detail_df["occupied_beds"].sum()
    )

    hospital_total_available = (
        hospital_detail_df["available_beds"].sum()
    )

    hospital_occupancy_pct = (
            hospital_total_occupied
            / hospital_total_capacity
            * 100
    )

    h_col1, h_col2, h_col3, h_col4 = st.columns(4)

    h_col1.metric(
        "🛏️ Total Beds",
        f"{int(hospital_total_capacity)}"
    )

    h_col2.metric(
        "🔴 Occupied",
        f"{int(hospital_total_occupied)}"
    )

    h_col3.metric(
        "🟢 Available",
        f"{int(hospital_total_available)}"
    )

    h_col4.metric(
        "📊 Occupancy",
        f"{hospital_occupancy_pct:.1f}%"
    )

    # Calculate department occupancy
    hospital_detail_df["current_occupancy_pct"] = (
            hospital_detail_df["occupied_beds"]
            / hospital_detail_df["department_bed_capacity"]
            * 100
    ).round(1)

    # Add current capacity status
    hospital_detail_df["Current Status"] = hospital_detail_df.apply(
        get_capacity_status,
        axis=1
    )

    # Prepare department table
    hospital_department_display = hospital_detail_df[
        [
            "department",
            "department_bed_capacity",
            "occupied_beds",
            "available_beds",
            "current_occupancy_pct",
            "Current Status",
        ]
    ].copy()

    hospital_department_display = hospital_department_display.rename(
        columns={
            "department": "Department",
            "department_bed_capacity": "Capacity",
            "occupied_beds": "Occupied",
            "available_beds": "Available",
            "current_occupancy_pct": "Occupancy %",
        }
    )

    # Highest occupancy first
    hospital_department_display = hospital_department_display.sort_values(
        "Occupancy %",
        ascending=False
    )

    st.dataframe(
        hospital_department_display,
        width="stretch",
        hide_index=True,
        height=260
    )

# ============================================================
# DEPARTMENT DETAILS PAGE
# ============================================================

if selected_page == "🛏️ Department Details":

    st.header("🛏️ Department Details")
    st.caption(
        "Compare current bed capacity for a department across hospitals."
    )

    # Department selector
    selected_detail_department = st.selectbox(
        "Select Department",
        sorted(
            department_df["department"]
            .dropna()
            .unique()
        ),
        key="department_details_selector"
    )

    # Filter selected department
    department_detail_df = department_df[
        department_df["department"]
        == selected_detail_department
    ].copy()

    # Calculate current occupancy
    department_detail_df["current_occupancy_pct"] = (
        department_detail_df["occupied_beds"]
        / department_detail_df["department_bed_capacity"]
        * 100
    ).round(1)

    # Current capacity status
    department_detail_df["Current Status"] = department_detail_df.apply(
        get_capacity_status,
        axis=1
    )

    # Prepare display table
    department_display = department_detail_df[
        [
            "hospital_name_department",
            "department_bed_capacity",
            "occupied_beds",
            "available_beds",
            "current_occupancy_pct",
            "Current Status",
        ]
    ].copy()

    department_display = department_display.rename(
        columns={
            "hospital_name_department": "Hospital",
            "department_bed_capacity": "Capacity",
            "occupied_beds": "Occupied",
            "available_beds": "Available",
            "current_occupancy_pct": "Occupancy %",
        }
    )

    # Highest occupancy first
    department_display = department_display.sort_values(
        "Occupancy %",
        ascending=False
    )

    st.dataframe(
        department_display,
        width="stretch",
        hide_index=True
    )