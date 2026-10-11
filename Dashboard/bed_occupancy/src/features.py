from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "bed_occupancy_combined.csv"
OUTPUT_FILE = BASE_DIR / "data" / "bed_occupancy_features.csv"


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(INPUT_FILE)

print("Dataset loaded successfully.")
print("Original shape:", df.shape)


# ============================================================
# 3. DATE CONVERSION
# ============================================================

df["date"] = pd.to_datetime(df["date"])


# ============================================================
# 4. SORT TIME SERIES
# ============================================================

# Each hospital + department is its own time series.
df = df.sort_values(
    ["hospital_id", "department", "date"]
).reset_index(drop=True)


# ============================================================
# 5. CALENDAR FEATURES
# ============================================================

df["day"] = df["date"].dt.day
df["month"] = df["date"].dt.month
df["day_of_week"] = df["date"].dt.dayofweek
df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)

df["is_weekend"] = (
    df["day_of_week"] >= 5
).astype(int)


# ============================================================
# 6. GROUP EACH HOSPITAL + DEPARTMENT
# ============================================================

group_cols = ["hospital_id", "department"]

grouped = df.groupby(group_cols, group_keys=False)


# ============================================================
# 7. LEAKAGE-SAFE OCCUPANCY LAG FEATURES
# ============================================================

# Yesterday's occupancy
df["lag_1_occupancy"] = grouped[
    "occupancy_rate_pct_department"
].shift(1)

# Occupancy 7 days ago
df["lag_7_occupancy"] = grouped[
    "occupancy_rate_pct_department"
].shift(7)


# ============================================================
# 8. ROLLING OCCUPANCY FEATURES
# ============================================================

# IMPORTANT:
# shift(1) means today's occupancy is NOT included in
# the historical rolling calculation.

df["rolling_7d_occupancy"] = grouped[
    "occupancy_rate_pct_department"
].transform(
    lambda x: x.shift(1).rolling(7).mean()
)

df["rolling_14d_occupancy"] = grouped[
    "occupancy_rate_pct_department"
].transform(
    lambda x: x.shift(1).rolling(14).mean()
)


# ============================================================
# 9. RECENT ADMISSION / DISCHARGE FEATURES
# ============================================================

df["admissions_7d_avg"] = grouped[
    "admissions"
].transform(
    lambda x: x.shift(1).rolling(7).mean()
)

df["discharges_7d_avg"] = grouped[
    "discharges"
].transform(
    lambda x: x.shift(1).rolling(7).mean()
)


# ============================================================
# 10. OCCUPANCY TREND
# ============================================================

# Difference between recent 7-day and 14-day occupancy.
# Positive = occupancy has recently increased.

df["occupancy_trend_7d"] = (
    df["rolling_7d_occupancy"]
    - df["rolling_14d_occupancy"]
)


# ============================================================
# 11. CREATE REAL 7-DAY-AHEAD REGRESSION TARGET
# ============================================================

# Actual observed occupancy exactly 7 days in the future.
df["target_occupancy_7d"] = grouped[
    "occupancy_rate_pct_department"
].shift(-7)


# ============================================================
# 12. CREATE CAPACITY-BREACH TARGET
# ============================================================

# Here we define a future capacity warning as
# occupancy >= 90% seven days ahead.

BREACH_THRESHOLD = 90

df["target_breach_7d"] = np.where(
    df["target_occupancy_7d"].notna(),
    (
        df["target_occupancy_7d"] >= BREACH_THRESHOLD
    ).astype(int),
    np.nan
)


# ============================================================
# 13. REMOVE PRE-COMPUTED / LEAKAGE-PRONE COLUMNS
# ============================================================

# These fields already contain predictions/risk information.
# They must not be supplied to our model as predictors.

leakage_columns = [
    "predicted_7d_occupancy_pct",
    "capacity_breach_7d",
    "risk_score",
    "risk_level"
]

df = df.drop(
    columns=[
        col for col in leakage_columns
        if col in df.columns
    ]
)


# ============================================================
# 14. REMOVE ROWS WITHOUT REQUIRED HISTORY OR FUTURE TARGET
# ============================================================

required_columns = [
    "lag_1_occupancy",
    "lag_7_occupancy",
    "rolling_7d_occupancy",
    "rolling_14d_occupancy",
    "admissions_7d_avg",
    "discharges_7d_avg",
    "occupancy_trend_7d",
    "target_occupancy_7d",
    "target_breach_7d"
]

before_drop = len(df)

df = df.dropna(
    subset=required_columns
).reset_index(drop=True)

after_drop = len(df)


# ============================================================
# 15. FINAL VALIDATION
# ============================================================

df["target_breach_7d"] = df[
    "target_breach_7d"
].astype(int)

print("\nFeature engineering completed.")

print("Rows before removing unavailable history/targets:",
      before_drop)

print("Rows after cleaning:",
      after_drop)

print("Rows removed:",
      before_drop - after_drop)

print("\nFinal shape:", df.shape)

print("\n7-day target statistics:")
print(df["target_occupancy_7d"].describe())

print("\n7-day breach target distribution:")
print(df["target_breach_7d"].value_counts())

print("\n7-day breach percentage:")
print(
    df["target_breach_7d"]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)


# ============================================================
# 16. SAVE FEATURE DATASET
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nFeature dataset saved successfully:")
print(OUTPUT_FILE)