"""
Module 3 — Blood Bank Intelligence: SHAP Explanations
-------------------------------------------------------
Explains WHY the demand model predicts what it predicts.

  1. Global view : summary (beeswarm) plot, bar plot, importance table, grouped importance
                   (computed on a sample of the test period).
  2. Alert view  : rebuilds the model's inputs for the first forecast day (2026-01-01)
                   for every hospital x group, explains the prediction, and writes a
                   plain-English reason for every High and Medium risk alert.
  3. Waterfall plots for the three most urgent High-risk alerts.

Inputs : models/blood_demand_model.json (xgboost) or .joblib (sklearn fallback)
         data/final/blood_features.csv, data/simulated/blood_daily_operations.csv,
         data/simulated/chennai_hospitals.csv, outputs/blood_risk.csv,
         outputs/blood_forecasts.csv  (only used for a consistency check)
Outputs: outputs/blood_alert_explanations.csv, outputs/shap_feature_importance.csv,
         outputs/figures/shap_*.png

Setup  : py -m pip install shap
Run    : py scripts\\blood_shap.py

NOTE on scale: the xgboost model uses a Poisson (log) link, so SHAP values are on the
log scale. exp(value) - 1 is the approximate % change in expected demand.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import shap
except ImportError:
    sys.exit("shap is not installed. Run:  py -m pip install shap")

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR, FINAL_DIR = ROOT / "data" / "simulated", ROOT / "data" / "final"
OUT_DIR, FIG_DIR, MODEL_DIR = ROOT / "outputs", ROOT / "outputs" / "figures", ROOT / "models"
FIG_DIR.mkdir(parents=True, exist_ok=True)
np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. Load model and data
# ---------------------------------------------------------------------------
feat = pd.read_csv(FINAL_DIR / "blood_features.csv", parse_dates=["date"])
NON_FEATURES = ["date", "hospital_id", "blood_group", "target_demand", "split"]
FEATURE_COLS = [c for c in feat.columns if c not in NON_FEATURES]   # same order as blood_forecast.py

if (MODEL_DIR / "blood_demand_model.json").exists():
    import xgboost as xgb
    model = xgb.XGBRegressor()
    model.load_model(str(MODEL_DIR / "blood_demand_model.json"))
    KIND = "xgboost"
elif (MODEL_DIR / "blood_demand_model.joblib").exists():
    import joblib
    model = joblib.load(MODEL_DIR / "blood_demand_model.joblib")
    KIND = "sklearn"
else:
    sys.exit("No saved demand model found in models\\. Run scripts\\blood_forecast.py first.")
print(f"Model: {KIND} | features: {len(FEATURE_COLS)}")

GLOBAL_N = 3000 if KIND == "xgboost" else 400      # permutation SHAP (sklearn) is much slower
test = feat[feat.split == "test"]
bg = feat[feat.split == "train"].sample(100, random_state=42)[FEATURE_COLS]
if KIND == "sklearn":
    perm = shap.PermutationExplainer(model.predict, bg)
else:
    tree = shap.TreeExplainer(model)


def explain(X):
    """Return a shap.Explanation for the rows of X (DataFrame with FEATURE_COLS)."""
    X = X[FEATURE_COLS]
    if KIND == "xgboost":
        sv = tree.shap_values(X)
        base = np.full(len(X), float(np.ravel(tree.expected_value)[0]))
        return shap.Explanation(values=sv, base_values=base, data=X.values, feature_names=FEATURE_COLS)
    return perm(X)


# ---------------------------------------------------------------------------
# 2. Global explanation
# ---------------------------------------------------------------------------
Xg = test.sample(min(GLOBAL_N, len(test)), random_state=42)[FEATURE_COLS]
eg = explain(Xg)
unit = "log-scale effect on expected demand" if KIND == "xgboost" else "effect on predicted demand (units)"

plt.figure(figsize=(9, 7))
shap.summary_plot(eg.values, Xg, max_display=15, show=False)
plt.gca().set_xlabel(f"SHAP value ({unit})")
plt.title("Which features drive demand predictions (test sample)")
plt.tight_layout()
plt.savefig(FIG_DIR / "shap_01_summary.png", dpi=130, bbox_inches="tight")
plt.close()

imp = (pd.Series(np.abs(eg.values).mean(axis=0), index=FEATURE_COLS)
       .sort_values(ascending=False).rename("mean_abs_shap"))
imp.reset_index().rename(columns={"index": "feature"}).to_csv(OUT_DIR / "shap_feature_importance.csv", index=False)

top = imp.head(15)[::-1]
plt.figure(figsize=(8, 6))
plt.barh(top.index, top.values, color="#1F618D")
plt.xlabel(f"Mean |SHAP value| ({unit})")
plt.title("Top 15 features by average impact")
plt.tight_layout()
plt.savefig(FIG_DIR / "shap_02_importance_bar.png", dpi=130)
plt.close()


def theme(f):
    if f.startswith("demand_lag") or f.startswith("demand_roll"):
        return "Recent demand (lags, rolling)"
    if f.startswith("donation") or f in ("procured_lag_1",):
        return "Donations / supply"
    if f in ("day_of_week", "is_weekend", "month", "day_of_year", "week_of_year", "is_festival", "is_summer_dip"):
        return "Calendar / festivals"
    if f.startswith("acc_"):
        return "Nearby accidents"
    if f in ("stock_prev_close", "expiring_3d_prev", "days_of_cover_prev", "unmet_lag_1"):
        return "Stock state"
    return "Hospital / blood group identity"


by_theme = imp.groupby(imp.index.map(theme)).sum().sort_values(ascending=False)
share = (100 * by_theme / by_theme.sum()).round(1)

# ---------------------------------------------------------------------------
# 3. Rebuild model inputs for the first forecast day (uses actual history only)
# ---------------------------------------------------------------------------
FESTIVALS = ["2023-01-15", "2024-01-15", "2025-01-14", "2023-04-14", "2024-04-14", "2025-04-14",
             "2023-08-15", "2024-08-15", "2025-08-15", "2023-11-12", "2024-11-01", "2025-10-20",
             "2026-01-15", "2026-04-14", "2026-08-15", "2026-11-08"]      # same list as blood_forecast.py
fest_days = {pd.Timestamp(f) + pd.Timedelta(days=k) for f in FESTIVALS for k in range(-2, 3)}
STATIC = ["trauma_tier", "icu_beds", "general_beds", "has_cath_lab", "blood_group_code",
          "is_rh_negative", "hospital_code", "acc_7d", "acc_30d", "acc_severe_30d"]

ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
LAST = ops.date.max()
day = LAST + pd.Timedelta(days=1)
stat = feat[feat.date == LAST].set_index(["hospital_id", "blood_group"])
rows = []
for (h, g), s in ops.sort_values("date").groupby(["hospital_id", "blood_group"]):
    dem, don = s["units_demanded"].to_numpy(float), s["units_donated"].to_numpy(float)
    stock = float(s["closing_stock"].iloc[-1])
    r = {"hospital_id": h, "blood_group": g,
         "demand_lag_1": dem[-1], "demand_lag_7": dem[-7], "demand_lag_14": dem[-14], "demand_lag_28": dem[-28],
         "donation_lag_1": don[-1], "donation_lag_7": don[-7],
         "unmet_lag_1": 0.0,                                # same convention as blood_forecast.py
         "demand_roll_mean_7": dem[-7:].mean(), "demand_roll_mean_14": dem[-14:].mean(),
         "demand_roll_mean_28": dem[-28:].mean(),
         "demand_roll_std_7": dem[-7:].std(ddof=1), "demand_roll_std_14": dem[-14:].std(ddof=1),
         "donation_roll_mean_7": don[-7:].mean(), "donation_roll_mean_28": don[-28:].mean(),
         "day_of_week": day.dayofweek, "is_weekend": int(day.dayofweek >= 5), "month": day.month,
         "day_of_year": day.dayofyear, "week_of_year": int(day.isocalendar().week),
         "is_festival": int(day in fest_days), "is_summer_dip": int(day.month in (5, 6)),
         "stock_prev_close": stock, "expiring_3d_prev": float(s["units_expiring_3d"].iloc[-1]),
         "procured_lag_1": float(s["units_procured"].iloc[-1])}
    r["days_of_cover_prev"] = min(60.0, stock / r["demand_roll_mean_7"]) if r["demand_roll_mean_7"] > 0 else 60.0
    for c in STATIC:
        r[c] = stat.loc[(h, g), c]
    rows.append(r)
live = pd.DataFrame(rows)
Xl = live[FEATURE_COLS].astype(float)
live["pred_day1"] = np.clip(model.predict(Xl), 0, None)

# Consistency check against the forecast file written by blood_forecast.py
fc = pd.read_csv(OUT_DIR / "blood_forecasts.csv", parse_dates=["date"])
d1 = fc[fc.horizon_day == 1][["hospital_id", "blood_group", "demand_forecast"]]
chk = live.merge(d1, on=["hospital_id", "blood_group"])
print(f"Consistency check vs blood_forecasts.csv (day 1): max abs difference = "
      f"{(chk.pred_day1 - chk.demand_forecast).abs().max():.4f} units (should be ~0)")

el = explain(Xl)

# ---------------------------------------------------------------------------
# 4. Plain-English reasons
# ---------------------------------------------------------------------------
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEDIAN = feat[feat.split == "train"][FEATURE_COLS].median()


def phrase(f, v):
    """Return (family, text) for a feature pushing demand UP, or None if it is not worth saying.
    Statements about 'high' values are only made when the value really is above the training median.
    Supply and stock features are skipped: they are not causes of demand."""
    high = v > MEDIAN[f]
    if f == "is_festival":
        return ("fest", "festival period") if v == 1 else None
    if f == "is_weekend":
        return ("dow", "weekend") if v == 1 else ("dow", "weekday (more elective surgery)")
    if f == "day_of_week":
        return ("dow", f"{DOW[int(v)]} is a busy day")
    if f == "is_summer_dip":
        return ("summer", "summer period") if v == 1 else None
    if f.startswith("demand_lag_"):
        k = int(f.split("_")[-1])
        if not high:
            return None
        if k == 1:
            return ("lag", f"yesterday's demand was high ({v:.0f} units)")
        if k == 7:
            return ("lag", f"same weekday last week was busy ({v:.0f} units)")
        return ("lag", f"demand {k} days ago was high ({v:.0f} units)")
    if f.startswith("demand_roll_mean"):
        return ("roll", f"recent average demand is high ({v:.1f} units/day)") if high else None
    if f.startswith("demand_roll_std"):
        return ("std", "demand has been volatile recently") if high else None
    if f.startswith("acc_"):
        win = {"acc_7d": "7", "acc_30d": "30", "acc_severe_30d": "30"}[f]
        kind = "serious accidents" if "severe" in f else "accidents"
        return ("acc", f"recent rise in nearby {kind} ({v:.0f} in the last {win} days)") if high else None
    if f in ("icu_beds", "general_beds", "trauma_tier", "has_cath_lab", "hospital_code"):
        return ("size", "large hospital with trauma capability")
    if f in ("blood_group_code", "is_rh_negative"):
        return ("grp", "this blood group's usual usage level")
    if f in ("month", "day_of_year", "week_of_year"):
        return ("season", "time of year")
    return None            # donations, procurement, stock, expiry: not demand drivers


def drivers(i, k=3):
    vals = el.values[i]
    out, seen = [], set()
    for j in np.argsort(-vals):
        if vals[j] <= 0 or len(out) == k:
            break
        p = phrase(FEATURE_COLS[j], Xl.iloc[i, j])
        if p and p[0] not in seen:
            seen.add(p[0])
            out.append(p[1])
    return out


risk = pd.read_csv(OUT_DIR / "blood_risk.csv")
name = pd.read_csv(SIM_DIR / "chennai_hospitals.csv").set_index("hospital_id")["name"].to_dict()
idx = {(r.hospital_id, r.blood_group): i for i, r in enumerate(live.itertuples())}
alerts = risk[risk.risk_level.isin(["High", "Medium"])].copy()
exp_rows = []
for r in alerts.itertuples():
    i = idx[(r.hospital_id, r.blood_group)]
    d = drivers(i)
    why = ("demand drivers: " + "; ".join(d)) if d else "demand is close to its usual level, so low stock is the main issue"
    exp_rows.append({
        "hospital_id": r.hospital_id, "hospital_name": name.get(r.hospital_id, ""),
        "blood_group": r.blood_group, "risk_level": r.risk_level,
        "days_of_cover": r.days_of_cover, "predicted_demand_day1": round(float(live.pred_day1[i]), 2),
        "top_demand_drivers": " | ".join(d),
        "explanation": (f"{r.risk_level} risk for {r.blood_group} at {name.get(r.hospital_id, r.hospital_id)}: "
                        f"{r.days_of_cover:.1f} days of cover; {why}.")})
ex = pd.DataFrame(exp_rows)
ex["_o"] = ex.risk_level.map({"High": 0, "Medium": 1})
ex = ex.sort_values(["_o", "days_of_cover"]).drop(columns="_o")
ex.to_csv(OUT_DIR / "blood_alert_explanations.csv", index=False)

# ---------------------------------------------------------------------------
# 5. Waterfall plots for the 3 most urgent High alerts
# ---------------------------------------------------------------------------
for rank, r in enumerate(ex[ex.risk_level == "High"].head(3).itertuples(), start=1):
    i = idx[(r.hospital_id, r.blood_group)]
    plt.figure(figsize=(9, 5))
    shap.plots.waterfall(el[i], max_display=10, show=False)
    plt.title(f"{r.blood_group} at {r.hospital_name}: why day-1 demand is {r.predicted_demand_day1:.1f}", fontsize=10)
    plt.savefig(FIG_DIR / f"shap_03_waterfall_{rank}_{r.hospital_id}_{r.blood_group}.png",
                dpi=130, bbox_inches="tight")
    plt.close()

# ---------------------------------------------------------------------------
# 6. Report numbers
# ---------------------------------------------------------------------------
print("\nTop 10 features (mean |SHAP|):")
print(imp.head(10).round(4).to_string())
print("\nShare of total impact by theme (%):")
print(share.to_string())
print(f"\nExplained {len(ex)} alerts. Examples:")
for t in ex.head(3).explanation:
    print(" -", t)
print("\nSaved outputs\\blood_alert_explanations.csv, shap_feature_importance.csv, figures\\shap_*.png")