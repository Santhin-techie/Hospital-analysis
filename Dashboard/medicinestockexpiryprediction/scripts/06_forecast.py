import sqlite3
import pandas as pd
from prophet import Prophet

# Connect to SQLite database
conn = sqlite3.connect("../database/hospital.db")

# Read data from database
usage = pd.read_sql("SELECT * FROM usage_history", conn)
meds = pd.read_sql("SELECT * FROM medicine_master", conn)

# Remove extra spaces from column names
usage.columns = usage.columns.str.strip()
meds.columns = meds.columns.str.strip()

# Check columns
print("Usage columns:", usage.columns.tolist())

# Convert date column
if "date" in usage.columns:
    usage["date"] = pd.to_datetime(usage["date"])
elif "datum" in usage.columns:
    usage.rename(columns={"datum": "date"}, inplace=True)
    usage["date"] = pd.to_datetime(usage["date"])
else:
    print("ERROR: No date column found in usage_history.")
    print(usage.columns.tolist())
    conn.close()
    exit()

results = []

# Create forecast for each medicine
for med_id in meds["medicine_id"]:

    d = usage[
        usage["medicine_id"] == med_id
    ][["date", "quantity_used"]].copy()

    if d.empty:
        continue

    # Prophet requires ds and y
    d.columns = ["ds", "y"]

    # Sort by date
    d = d.sort_values("ds")

    # Remove missing values
    d = d.dropna()

    if len(d) < 2:
        continue

    # Create Prophet model
    m = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True
    )

    # Train model
    m.fit(d)

    # Create next 30 days
    future = m.make_future_dataframe(periods=30)

    # Generate forecast
    fc = m.predict(future)

    # Average predicted demand for next 30 days
    forecast_daily_demand = fc["yhat"].tail(30).mean()

    # Average demand from last 90 records
    avg90_daily_demand = d["y"].tail(90).mean()

    results.append({
        "medicine_id": med_id,
        "forecast_daily_demand": max(0, forecast_daily_demand),
        "avg90_daily_demand": max(0, avg90_daily_demand)
    })

# Convert results to DataFrame
forecast_df = pd.DataFrame(results)

# Save forecast to database
forecast_df.to_sql(
    "medicine_forecast",
    conn,
    if_exists="replace",
    index=False
)

# Close database
conn.close()

print("Forecast complete.")
print(forecast_df)