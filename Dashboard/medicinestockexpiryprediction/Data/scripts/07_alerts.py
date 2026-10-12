import sqlite3
import pandas as pd
import numpy as np

# Connect to SQLite database
conn = sqlite3.connect("../database/hospital.db")

# Read tables from database
meds = pd.read_sql("SELECT * FROM medicine_master", conn)
batch = pd.read_sql("SELECT * FROM batch_stock", conn)
forecast = pd.read_sql("SELECT * FROM medicine_forecast", conn)

# Merge medicine, batch and forecast information
df = batch.merge(
    meds,
    on="medicine_id",
    how="left"
).merge(
    forecast,
    on="medicine_id",
    how="left"
)

# Convert expiry date to datetime
df["expiry_date"] = pd.to_datetime(
    df["expiry_date"],
    errors="coerce"
)

# Calculate days until expiry
df["days_to_expiry"] = (
    df["expiry_date"] - pd.Timestamp.today()
).dt.days.clip(lower=0)

# Calculate how many days the current stock will last
df["days_of_stock_left"] = (
    df["current_quantity"]
    / df["forecast_daily_demand"].replace(0, np.nan)
)

df["days_of_stock_left"] = df["days_of_stock_left"].fillna(0)

# Determine shortage status
df["shortage_status"] = np.select(
    [
        df["days_of_stock_left"] < 3,
        df["days_of_stock_left"] < df["reorder_lead_time_days"]
    ],
    [
        "Critical",
        "Warning"
    ],
    default="Safe"
)

# Calculate projected unused stock before expiry
df["projected_unused"] = (
    df["current_quantity"]
    - df["forecast_daily_demand"] * df["days_to_expiry"]
).clip(lower=0)

# Calculate potential wastage value
df["wastage_risk_rs"] = (
    df["projected_unused"] * df["unit_price"]
).round(0)

# Calculate suggested quantity to order for 30 days
df["suggested_reorder_qty"] = (
    df["forecast_daily_demand"] * 30
    - df["current_quantity"]
).clip(lower=0).round(0)

# Calculate demand trend
df["trend_ratio"] = (
    df["forecast_daily_demand"]
    / df["avg90_daily_demand"].replace(0, np.nan)
).fillna(1.0)

# Label the trend
df["trend_label"] = np.select(
    [
        df["trend_ratio"] > 1.2,
        df["trend_ratio"] < 0.8
    ],
    [
        "↑ Rising",
        "↓ Falling"
    ],
    default="→ Stable"
)

# Recommend an action
df["recommended_action"] = np.select(
    [
        df["trend_ratio"] > 1.2,
        df["trend_ratio"] < 0.8
    ],
    [
        "Order more",
        "Order less"
    ],
    default="Maintain"
)

# Save alerts to SQLite
df.to_sql(
    "medicine_alerts",
    conn,
    if_exists="replace",
    index=False
)

# Close database connection
conn.close()

print("Alerts computed:", df.shape)
print(df[
    [
        "medicine_id",
        "current_quantity",
        "forecast_daily_demand",
        "days_of_stock_left",
        "shortage_status",
        "wastage_risk_rs",
        "suggested_reorder_qty",
        "trend_label",
        "recommended_action"
    ]
])  