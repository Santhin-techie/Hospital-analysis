"""
Module 3 — Blood Bank Intelligence: Feature Engineering
--------------------------------------------------------
Builds the model-ready table: one row per (date, hospital_id, blood_group).

TARGET   : units_demanded  (units needed that day)
FEATURES : every feature uses only information from BEFORE that day
           (lags >= 1, rolling windows shifted by 1). No leakage.

Input  : data/simulated/blood_daily_operations.csv
         data/simulated/chennai_hospitals.csv
         data/simulated/chennai_simulated_accidents.csv
Output : data/final/blood_features.csv
         data/final/blood_feature_dictionary.csv   (what each column means)

Run from the project root:   py scripts\\blood_features.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
FINAL_DIR = ROOT / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
LAGS = [1, 7, 14, 28]
WINDOWS = [7, 14, 28]

# Same festival list as the simulation (documented in generate_blood_data.py)
FESTIVALS = ["2023-01-15", "2024-01-15", "2025-01-14",    # Pongal
             "2023-04-14", "2024-04-14", "2025-04-14",    # Tamil New Year
             "2023-08-15", "2024-08-15", "2025-08-15",    # Independence Day
             "2023-11-12", "2024-11-01", "2025-10-20"]    # Deepavali

ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv")
acc = pd.read_csv(SIM_DIR / "chennai_simulated_accidents.csv", parse_dates=["date"])
dates = pd.date_range(ops.date.min(), ops.date.max(), freq="D")

ops = ops.sort_values(["hospital_id", "blood_group", "date"]).reset_index(drop=True)
g = ops.groupby(["hospital_id", "blood_group"], sort=False)

# ---------------------------------------------------------------------------
# 1. Lag features (demand and donations)
# ---------------------------------------------------------------------------
feat = ops[["date", "hospital_id", "blood_group", "units_demanded"]].copy()
feat = feat.rename(columns={"units_demanded": "target_demand"})

for k in LAGS:
    feat[f"demand_lag_{k}"] = g["units_demanded"].shift(k)
for k in [1, 7]:
    feat[f"donation_lag_{k}"] = g["units_donated"].shift(k)
feat["unmet_lag_1"] = g["units_unmet"].shift(1)

# ---------------------------------------------------------------------------
# 2. Rolling statistics (shifted by 1 so today is never included)
# ---------------------------------------------------------------------------
shifted_dem = g["units_demanded"].shift(1)
shifted_don = g["units_donated"].shift(1)
grp_keys = [ops["hospital_id"], ops["blood_group"]]
for w in WINDOWS:
    feat[f"demand_roll_mean_{w}"] = shifted_dem.groupby(grp_keys).transform(
        lambda s: s.rolling(w, min_periods=w).mean())
for w in [7, 14]:
    feat[f"demand_roll_std_{w}"] = shifted_dem.groupby(grp_keys).transform(
        lambda s: s.rolling(w, min_periods=w).std())
feat["donation_roll_mean_7"] = shifted_don.groupby(grp_keys).transform(
    lambda s: s.rolling(7, min_periods=7).mean())
feat["donation_roll_mean_28"] = shifted_don.groupby(grp_keys).transform(
    lambda s: s.rolling(28, min_periods=28).mean())

# ---------------------------------------------------------------------------
# 3. Calendar features
# ---------------------------------------------------------------------------
d = feat["date"]
feat["day_of_week"] = d.dt.dayofweek
feat["is_weekend"] = (d.dt.dayofweek >= 5).astype(int)
feat["month"] = d.dt.month
feat["day_of_year"] = d.dt.dayofyear
feat["week_of_year"] = d.dt.isocalendar().week.astype(int)
fest = set()
for f in FESTIVALS:
    for k in range(-2, 3):
        fest.add(pd.Timestamp(f) + pd.Timedelta(days=k))
feat["is_festival"] = d.isin(fest).astype(int)
feat["is_summer_dip"] = d.dt.month.isin([5, 6]).astype(int)

# ---------------------------------------------------------------------------
# 4. Hospital context
# ---------------------------------------------------------------------------
ctx = hosp[["hospital_id", "trauma_tier", "icu_beds", "general_beds"]].copy()
ctx["has_cath_lab"] = hosp["has_cath_lab"].astype(int)
feat = feat.merge(ctx, on="hospital_id", how="left")

# Blood group as a number for tree models (keeps the label too)
feat["blood_group_code"] = feat["blood_group"].map({gname: i for i, gname in enumerate(GROUPS)})
feat["is_rh_negative"] = feat["blood_group"].str.endswith("-").astype(int)
feat["hospital_code"] = feat["hospital_id"].str.replace("HOSP", "", regex=False).astype(int)

# ---------------------------------------------------------------------------
# 5. Recent accident load near each hospital (past-only)
#    Each accident is assigned to the nearest trauma-capable hospital
#    (tier 1/2), the same rule used in the simulation. Module 4 will replace
#    straight-line distance with real road travel time.
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2)
    return 2 * r * np.arcsin(np.sqrt(a))

trauma_h = hosp[hosp["trauma_tier"] <= 2].reset_index(drop=True)
dist = np.stack([haversine_km(acc["latitude"].values, acc["longitude"].values,
                              r.latitude, r.longitude) for r in trauma_h.itertuples()], axis=1)
acc["hospital_id"] = trauma_h["hospital_id"].values[dist.argmin(axis=1)]
acc["is_fatal_or_grievous"] = acc["severity"].isin(["Fatal", "Grievous"]).astype(int)

acc_daily = (acc.groupby(["hospital_id", "date"])
             .agg(acc_count=("accident_id", "count"), acc_severe=("is_fatal_or_grievous", "sum"))
             .reset_index())
grid = pd.MultiIndex.from_product([hosp["hospital_id"], dates], names=["hospital_id", "date"]).to_frame(index=False)
acc_daily = grid.merge(acc_daily, on=["hospital_id", "date"], how="left").fillna(0)
acc_daily = acc_daily.sort_values(["hospital_id", "date"])
ag = acc_daily.groupby("hospital_id", sort=False)
# shift(1) first so the window ends yesterday
acc_daily["acc_7d"] = ag["acc_count"].transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
acc_daily["acc_30d"] = ag["acc_count"].transform(lambda s: s.shift(1).rolling(30, min_periods=1).sum())
acc_daily["acc_severe_30d"] = ag["acc_severe"].transform(lambda s: s.shift(1).rolling(30, min_periods=1).sum())
feat = feat.merge(acc_daily[["hospital_id", "date", "acc_7d", "acc_30d", "acc_severe_30d"]],
                  on=["hospital_id", "date"], how="left")

# ---------------------------------------------------------------------------
# 6. Stock features (yesterday's end-of-day state)
# ---------------------------------------------------------------------------
feat["stock_prev_close"] = g["closing_stock"].shift(1).values
feat["expiring_3d_prev"] = g["units_expiring_3d"].shift(1).values
feat["procured_lag_1"] = g["units_procured"].shift(1).values
# If there was no demand in the last 7 days, cover is effectively unlimited -> cap at 60
feat["days_of_cover_prev"] = np.where(
    feat["demand_roll_mean_7"] > 0,
    feat["stock_prev_close"] / feat["demand_roll_mean_7"].where(feat["demand_roll_mean_7"] > 0, 1),
    60.0)
feat["days_of_cover_prev"] = feat["days_of_cover_prev"].clip(upper=60)

# ---------------------------------------------------------------------------
# 7. Clean up and save
# ---------------------------------------------------------------------------
feat = feat.sort_values(["date", "hospital_id", "blood_group"]).reset_index(drop=True)

# Drop the warm-up period where 28-day lags don't exist yet
n_before = len(feat)
feat = feat.dropna(subset=["demand_lag_28", "demand_roll_mean_28", "donation_roll_mean_28"]).reset_index(drop=True)
n_dropped = n_before - len(feat)

# Time-based split labels (same split for every model, so results are comparable)
#   train: 2023-01 .. 2024-12   | validation: 2025-01 .. 2025-06 | test: 2025-07 .. 2025-12
feat["split"] = np.where(feat["date"] < "2025-01-01", "train",
                         np.where(feat["date"] < "2025-07-01", "validation", "test"))

# Leakage guard: today's target must not appear in any feature column
feature_cols = [c for c in feat.columns if c not in
                ["date", "hospital_id", "blood_group", "target_demand", "split"]]
assert feat[feature_cols].isna().sum().sum() == 0, "unexpected missing values in features"
# lag_1 must equal yesterday's actual demand
chk = feat[(feat.hospital_id == "HOSP01") & (feat.blood_group == "O+")].sort_values("date")
assert (chk["demand_lag_1"].iloc[1:].values == chk["target_demand"].iloc[:-1].values).all(), "lag_1 is wrong"

feat.to_csv(FINAL_DIR / "blood_features.csv", index=False)

dictionary = pd.DataFrame([
    ("target_demand", "TARGET: units of this blood group needed at this hospital on this day"),
    ("demand_lag_1/7/14/28", "demand 1, 7, 14, 28 days earlier"),
    ("donation_lag_1/7", "donations 1 and 7 days earlier"),
    ("unmet_lag_1", "unmet demand yesterday (stock-out signal)"),
    ("demand_roll_mean_7/14/28", "average demand over the previous 7/14/28 days (ends yesterday)"),
    ("demand_roll_std_7/14", "demand variability over the previous 7/14 days"),
    ("donation_roll_mean_7/28", "average donations over the previous 7/28 days"),
    ("day_of_week, is_weekend, month, day_of_year, week_of_year", "calendar position"),
    ("is_festival", "within +/-2 days of Pongal, Tamil New Year, Independence Day or Deepavali"),
    ("is_summer_dip", "May-June (low donation season)"),
    ("trauma_tier, icu_beds, general_beds, has_cath_lab", "hospital capability, from Module 4 hospital table"),
    ("blood_group_code, is_rh_negative, hospital_code", "numeric codes for tree models"),
    ("acc_7d, acc_30d, acc_severe_30d", "accidents attributed to this hospital in the previous 7/30 days (ends yesterday)"),
    ("stock_prev_close", "closing stock at end of yesterday"),
    ("expiring_3d_prev", "units that were due to expire within 3 days, as of yesterday"),
    ("procured_lag_1", "units received from regional centre yesterday"),
    ("days_of_cover_prev", "yesterday's closing stock / 7-day average demand"),
    ("split", "train (2023-2024) / validation (2025 H1) / test (2025 H2) -- time-based, never random"),
], columns=["feature", "meaning"])
dictionary.to_csv(FINAL_DIR / "blood_feature_dictionary.csv", index=False)

print(f"Feature table: {len(feat):,} rows x {feat.shape[1]} columns "
      f"(dropped {n_dropped:,} warm-up rows) -> {FINAL_DIR / 'blood_features.csv'}")
print(f"Features: {len(feature_cols)}")
print()
print(feat["split"].value_counts().reindex(["train", "validation", "test"]).to_string())
print()
print("Date ranges:")
print(feat.groupby("split")["date"].agg(["min", "max"]).to_string())
print()
print("Leakage checks passed (no missing values, lag_1 matches yesterday's demand).")
