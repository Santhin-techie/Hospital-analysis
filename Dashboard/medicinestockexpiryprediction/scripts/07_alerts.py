import sqlite3
import pandas as pd
import numpy as np


# ============================================================
# 1. CONNECT TO DATABASE
# ============================================================

conn = sqlite3.connect("../database/hospital.db")


# ============================================================
# 2. READ TABLES FROM DATABASE
# ============================================================

meds = pd.read_sql(
    "SELECT * FROM medicine_master",
    conn
)

batch = pd.read_sql(
    "SELECT * FROM batch_stock",
    conn
)

forecast = pd.read_sql(
    "SELECT * FROM medicine_forecast",
    conn
)


# ============================================================
# 3. CLEAN COLUMN NAMES
# ============================================================

meds.columns = meds.columns.str.strip()
batch.columns = batch.columns.str.strip()
forecast.columns = forecast.columns.str.strip()


# ============================================================
# 4. CONVERT IMPORTANT COLUMNS TO CORRECT DATA TYPES
# ============================================================

batch["current_quantity"] = pd.to_numeric(
    batch["current_quantity"],
    errors="coerce"
).fillna(0)

forecast["forecast_daily_demand"] = pd.to_numeric(
    forecast["forecast_daily_demand"],
    errors="coerce"
).fillna(0)

forecast["avg90_daily_demand"] = pd.to_numeric(
    forecast["avg90_daily_demand"],
    errors="coerce"
).fillna(0)

meds["reorder_lead_time_days"] = pd.to_numeric(
    meds["reorder_lead_time_days"],
    errors="coerce"
).fillna(0)

meds["unit_price"] = pd.to_numeric(
    meds["unit_price"],
    errors="coerce"
).fillna(0)


# ============================================================
# 5. BATCH-LEVEL EXPIRY ANALYSIS
# ============================================================
#
# Expiry is checked separately for every batch.
#
# Example:
#
# M01
#   B001 -> expires in 5 days
#   B002 -> expires in 60 days
#
# These batches must NOT be given one common expiry date.
# ============================================================

batch["expiry_date"] = pd.to_datetime(
    batch["expiry_date"],
    errors="coerce"
)

today = pd.Timestamp.today().normalize()


# ============================================================
# MERGE BATCH + MEDICINE + FORECAST INFORMATION
# ============================================================

batch_alerts = (
    batch
    .merge(
        meds,
        on="medicine_id",
        how="left"
    )
    .merge(
        forecast,
        on="medicine_id",
        how="left"
    )
)


# ============================================================
# 6. DAYS TO EXPIRY
# ============================================================

batch_alerts["days_to_expiry"] = (
    batch_alerts["expiry_date"] - today
).dt.days


# ============================================================
# 7. EXPIRY STATUS
# ============================================================
#
# Expired       -> already expired
# Critical      -> expires within 7 days
# Expiring Soon -> expires within 30 days
# Safe          -> more than 30 days
# ============================================================

batch_alerts["expiry_status"] = np.select(
    [
        batch_alerts["days_to_expiry"] < 0,

        batch_alerts["days_to_expiry"] <= 7,

        batch_alerts["days_to_expiry"] <= 30
    ],
    [
        "Expired",

        "Critical",

        "Expiring Soon"
    ],
    default="Safe"
)


# ============================================================
# 8. EXPIRY MANAGEMENT ACTION
# ============================================================
#
# IMPORTANT:
# EXPIRY DOES NOT AUTOMATICALLY CAUSE REORDER.
#
# Expiry decisions are handled separately:
#
# Expired       -> Remove / Dispose
# Critical      -> Use First - FEFO
# Expiring Soon -> Prioritize Usage
# Safe          -> Normal
# ============================================================

batch_alerts["expiry_action"] = np.select(
    [
        batch_alerts["expiry_status"] == "Expired",

        batch_alerts["expiry_status"] == "Critical",

        batch_alerts["expiry_status"] == "Expiring Soon"
    ],
    [
        "Remove / Dispose",

        "Use First - FEFO",

        "Prioritize Usage"
    ],
    default="Normal"
)


# ============================================================
# 9. DAYS AVAILABLE BEFORE EXPIRY
# ============================================================

batch_alerts["days_available"] = (
    batch_alerts["days_to_expiry"]
    .clip(lower=0)
)


# ============================================================
# 10. PROJECTED UNUSED STOCK
# ============================================================
#
# This estimates how much stock may remain unused
# when the batch reaches its expiry date.
#
# If the batch is already expired:
# all remaining stock is considered at risk.
# ============================================================

batch_alerts["projected_unused"] = np.where(
    batch_alerts["days_to_expiry"] < 0,

    batch_alerts["current_quantity"],

    (
        batch_alerts["current_quantity"]
        -
        (
            batch_alerts["forecast_daily_demand"]
            *
            batch_alerts["days_available"]
        )
    ).clip(lower=0)
)


# ============================================================
# 11. WASTAGE RISK VALUE
# ============================================================
#
# Wastage Risk =
# Projected Unused Stock × Unit Price
# ============================================================

batch_alerts["wastage_risk_rs"] = (
    batch_alerts["projected_unused"]
    *
    batch_alerts["unit_price"]
).round(0)


# ============================================================
# 12. FEFO PRIORITY
# ============================================================
#
# FEFO = First Expiry, First Out
#
# The batch with the earliest expiry date
# receives the highest priority.
# ============================================================

batch_alerts = batch_alerts.sort_values(
    [
        "medicine_id",
        "expiry_date"
    ]
)

batch_alerts["fefo_priority"] = (
    batch_alerts
    .groupby("medicine_id")
    .cumcount()
    + 1
)


# ============================================================
# 13. MEDICINE-LEVEL STOCK CALCULATION
# ============================================================
#
# IMPORTANT:
#
# Reorder decisions are made at MEDICINE level.
#
# Example:
#
# M01:
# B001 = 100
# B002 = 200
# B003 = 150
#
# Total M01 stock = 450
#
# Therefore:
#
# Reorder calculations use 450,
# NOT 100, 200 and 150 separately.
# ============================================================

medicine_stock = (
    batch
    .groupby(
        "medicine_id",
        as_index=False
    )
    .agg(
        total_current_stock=(
            "current_quantity",
            "sum"
        ),

        batch_count=(
            "batch_id",
            "count"
        )
    )
)


# ============================================================
# 14. MERGE MEDICINE STOCK WITH MASTER DATA
# AND FORECAST DATA
# ============================================================

medicine_alerts = (
    medicine_stock
    .merge(
        meds,
        on="medicine_id",
        how="left"
    )
    .merge(
        forecast,
        on="medicine_id",
        how="left"
    )
)


# ============================================================
# 15. DAYS OF STOCK LEFT
# ============================================================
#
# Formula:
#
# Days of Stock =
# Total Current Stock / Forecast Daily Demand
#
# Example:
#
# Stock = 500
# Daily demand = 50
#
# Days of stock = 500 / 50 = 10 days
# ============================================================

medicine_alerts["days_of_stock_left"] = np.where(
    medicine_alerts["forecast_daily_demand"] > 0,

    medicine_alerts["total_current_stock"]
    /
    medicine_alerts["forecast_daily_demand"],

    np.nan
)


# Round to one decimal place

medicine_alerts["days_of_stock_left"] = (
    medicine_alerts["days_of_stock_left"]
    .round(1)
)


# ============================================================
# 16. PROJECTED STOCK WHEN NEW ORDER ARRIVES
# ============================================================
#
# Formula:
#
# Projected Stock =
# Current Stock
# -
# (Daily Demand × Supplier Lead Time)
#
# This tells us how much stock may remain
# when the new order arrives.
# ============================================================

medicine_alerts["projected_stock_at_replenishment"] = (
    medicine_alerts["total_current_stock"]
    -
    (
        medicine_alerts["forecast_daily_demand"]
        *
        medicine_alerts["reorder_lead_time_days"]
    )
)


medicine_alerts["projected_stock_at_replenishment"] = (
    medicine_alerts["projected_stock_at_replenishment"]
    .round(1)
)


# ============================================================
# 17. EXPECTED STOCKOUT DATE
# ============================================================
#
# Formula:
#
# Stockout Date =
# Today + Days of Stock Left
# ============================================================

medicine_alerts["expected_stockout_date"] = pd.NaT


stockout_mask = (
    medicine_alerts["forecast_daily_demand"] > 0
)


medicine_alerts.loc[
    stockout_mask,
    "expected_stockout_date"
] = (
    today
    +
    pd.to_timedelta(
        medicine_alerts.loc[
            stockout_mask,
            "days_of_stock_left"
        ],
        unit="D"
    )
)


# Convert to date only

medicine_alerts["expected_stockout_date"] = (
    pd.to_datetime(
        medicine_alerts["expected_stockout_date"]
    ).dt.date
)


# ============================================================
# 18. STOCK STATUS
# ============================================================
#
# Critical:
# Stock will finish before supplier replenishment.
#
# Warning:
# Stock is relatively low.
#
# Safe:
# Enough stock available.
# ============================================================

medicine_alerts["shortage_status"] = np.select(
    [
        medicine_alerts["days_of_stock_left"]
        <
        medicine_alerts["reorder_lead_time_days"],

        medicine_alerts["days_of_stock_left"] <= 14
    ],
    [
        "Critical",

        "Warning"
    ],
    default="Safe"
)


# ============================================================
# 19. SUGGESTED REORDER QUANTITY
# ============================================================
#
# Simple 30-day planning target.
#
# Target Stock =
# Forecast Daily Demand × 30
#
# Reorder Quantity =
# Target Stock - Current Total Stock
#
# Reorder is calculated at MEDICINE level.
#
# EXPIRY DOES NOT AUTOMATICALLY INCREASE REORDER.
# ============================================================

medicine_alerts["suggested_reorder_qty"] = (
    (
        medicine_alerts["forecast_daily_demand"]
        *
        30
    )
    -
    medicine_alerts["total_current_stock"]
).clip(lower=0)


medicine_alerts["suggested_reorder_qty"] = (
    medicine_alerts["suggested_reorder_qty"]
    .round(0)
)


# ============================================================
# 20. DEMAND TREND
# ============================================================
#
# Compare:
#
# Forecast Daily Demand
# with
# 90-Day Average Demand
#
# Ratio > 1.2  -> Rising
# Ratio < 0.8  -> Falling
# Otherwise    -> Stable
# ============================================================

medicine_alerts["trend_ratio"] = np.where(
    medicine_alerts["avg90_daily_demand"] > 0,

    medicine_alerts["forecast_daily_demand"]
    /
    medicine_alerts["avg90_daily_demand"],

    1.0
)


# ============================================================
# 21. TREND LABEL
# ============================================================

medicine_alerts["trend_label"] = np.select(
    [
        medicine_alerts["trend_ratio"] > 1.2,

        medicine_alerts["trend_ratio"] < 0.8
    ],
    [
        "↑ Rising",

        "↓ Falling"
    ],
    default="→ Stable"
)


# ============================================================
# 22. RECOMMENDED ACTION
# ============================================================
#
# This is a MEDICINE-LEVEL STOCK/REORDER decision.
#
# Expiry actions are stored separately in batch_alerts.
# ============================================================

medicine_alerts["recommended_action"] = np.select(
    [
        medicine_alerts["shortage_status"] == "Critical",

        medicine_alerts["shortage_status"] == "Warning",

        medicine_alerts["trend_ratio"] > 1.2,

        medicine_alerts["trend_ratio"] < 0.8
    ],
    [
        "Reorder Immediately",

        "Plan Replenishment",

        "Monitor Rising Demand",

        "Monitor Falling Demand"
    ],
    default="Maintain Stock"
)


# ============================================================
# 23. SAVE MEDICINE-LEVEL ALERTS
# ============================================================

medicine_alerts.to_sql(
    "medicine_alerts",
    conn,
    if_exists="replace",
    index=False
)


# ============================================================
# 24. SAVE BATCH-LEVEL EXPIRY ALERTS
# ============================================================

batch_alerts.to_sql(
    "batch_alerts",
    conn,
    if_exists="replace",
    index=False
)


# ============================================================
# 25. CLOSE DATABASE
# ============================================================

conn.close()


# ============================================================
# 26. DISPLAY RESULTS
# ============================================================

print("\n==========================================")
print("ALERT CALCULATION COMPLETED")
print("==========================================")


# ============================================================
# MEDICINE-LEVEL RESULTS
# ============================================================

print("\nMedicine-level inventory analysis:")

print(
    medicine_alerts[
        [
            "medicine_id",
            "total_current_stock",
            "forecast_daily_demand",
            "days_of_stock_left",
            "reorder_lead_time_days",
            "projected_stock_at_replenishment",
            "expected_stockout_date",
            "shortage_status",
            "suggested_reorder_qty",
            "trend_label",
            "recommended_action"
        ]
    ].to_string(index=False)
)


# ============================================================
# BATCH-LEVEL RESULTS
# ============================================================

print("\n==========================================")
print("BATCH-LEVEL EXPIRY ANALYSIS")
print("==========================================")

print(
    batch_alerts[
        [
            "batch_id",
            "medicine_id",
            "current_quantity",
            "expiry_date",
            "days_to_expiry",
            "expiry_status",
            "expiry_action",
            "projected_unused",
            "wastage_risk_rs",
            "fefo_priority"
        ]
    ].to_string(index=False)
)


# ============================================================
# SUMMARY
# ============================================================

print("\n==========================================")
print("SUMMARY")
print("==========================================")

print(
    "Total medicines analyzed:",
    medicine_alerts["medicine_id"].nunique()
)

print(
    "Critical medicines:",
    (
        medicine_alerts["shortage_status"] == "Critical"
    ).sum()
)

print(
    "Warning medicines:",
    (
        medicine_alerts["shortage_status"] == "Warning"
    ).sum()
)

print(
    "Safe medicines:",
    (
        medicine_alerts["shortage_status"] == "Safe"
    ).sum()
)

print(
    "Expired batches:",
    (
        batch_alerts["expiry_status"] == "Expired"
    ).sum()
)

print(
    "Batches expiring within 7 days:",
    (
        batch_alerts["expiry_status"] == "Critical"
    ).sum()
)

print(
    "Batches expiring within 30 days:",
    (
        batch_alerts["expiry_status"] == "Expiring Soon"
    ).sum()
)

print(
    "Estimated wastage risk (₹):",
    int(batch_alerts["wastage_risk_rs"].sum())
)

print(
    "Total suggested reorder quantity:",
    int(medicine_alerts["suggested_reorder_qty"].sum())
)

print("\n==========================================")
print("DATABASE TABLES UPDATED")
print("==========================================")
print("medicine_alerts")
print("batch_alerts")
print("==========================================")