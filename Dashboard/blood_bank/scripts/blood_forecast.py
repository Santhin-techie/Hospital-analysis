"""
Module 3 — Blood Bank Intelligence: Demand & Donation Forecasting
------------------------------------------------------------------
What this script does
  1. Baselines: naive (yesterday), seasonal naive (same day last week),
     7-day moving average.
  2. Gradient-boosted count model (XGBoost, Poisson objective) for
     DEMAND and for DONATIONS. If xgboost is not installed it falls back to
     scikit-learn's HistGradientBoostingRegressor (also Poisson loss).
  3. Time-based evaluation (never a random split):
        train 2023-2024 | validation 2025 H1 | test 2025 H2
     Validation scores use a model trained on train only.
     Test scores use a model refit on train + validation.
  4. Metrics: MAE, RMSE, WAPE. MAPE is NOT used: rare groups have many
     zero-demand days. One-day-ahead scores are reported, PLUS a rolling
     7-day-ahead evaluation (the horizon the risk engine actually needs).
  5. Prediction intervals from a negative-binomial distribution around the
     predicted mean (dispersion estimated per blood group on validation).
     The UPPER bound (90th percentile) is what the risk engine uses.
  6. A 14-day-ahead forecast beyond the last data date (recursive).

Inputs : data/final/blood_features.csv
         data/simulated/blood_daily_operations.csv
Outputs: outputs/model_comparison_blood.csv
         outputs/blood_forecasts.csv           (next 14 days, with intervals)
         outputs/blood_test_predictions.csv    (test-period predictions)
         outputs/figures/forecast_*.png
         models/blood_demand_model.*  models/blood_donation_model.*

Run from the project root:   py scripts\\blood_forecast.py
"""

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_poisson_deviance

warnings.filterwarnings("ignore")
np.random.seed(42)

try:
    import xgboost as xgb
    BACKEND = "xgboost"
except ImportError:  # fallback so the pipeline still runs
    from sklearn.ensemble import HistGradientBoostingRegressor
    import joblib
    BACKEND = "sklearn-hist-gbm (xgboost not installed)"

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
FINAL_DIR = ROOT / "data" / "final"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
MODEL_DIR = ROOT / "models"
for d in (OUT_DIR, FIG_DIR, MODEL_DIR):
    d.mkdir(parents=True, exist_ok=True)

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
HORIZON = 14
LOWER_Q, UPPER_Q = 0.10, 0.90

print(f"Backend: {BACKEND}")

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
feat = pd.read_csv(FINAL_DIR / "blood_features.csv", parse_dates=["date"])
ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
feat = feat.merge(ops[["date", "hospital_id", "blood_group", "units_donated"]],
                  on=["date", "hospital_id", "blood_group"], how="left")
feat = feat.rename(columns={"units_donated": "target_donation"})

NON_FEATURES = ["date", "hospital_id", "blood_group", "target_demand",
                "target_donation", "split"]
FEATURE_COLS = [c for c in feat.columns if c not in NON_FEATURES]
print(f"Rows: {len(feat):,} | Features: {len(FEATURE_COLS)}")

train = feat[feat.split == "train"]
val = feat[feat.split == "validation"]
trval = feat[feat.split.isin(["train", "validation"])]
test = feat[feat.split == "test"]


# ---------------------------------------------------------------------------
# 2. Metrics
# ---------------------------------------------------------------------------
def wape(y, p):
    s = np.sum(y)
    return np.nan if s == 0 else np.sum(np.abs(y - p)) / s


def metrics(df, ycol, pcol):
    y, p = df[ycol].values.astype(float), df[pcol].values.astype(float)
    return {"MAE": np.mean(np.abs(y - p)),
            "RMSE": np.sqrt(np.mean((y - p) ** 2)),
            "WAPE_%": 100 * wape(y, p),
            "n": len(df)}


# ---------------------------------------------------------------------------
# 3. Model wrapper (XGBoost or sklearn fallback)
# ---------------------------------------------------------------------------
def fit_with_validation(Xtr, ytr, Xva, yva):
    """Train on train, pick number of trees on validation. Returns (model, best_n)."""
    if BACKEND == "xgboost":
        m = xgb.XGBRegressor(
            objective="count:poisson", n_estimators=1500, learning_rate=0.05,
            max_depth=6, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            reg_lambda=1.0, eval_metric="poisson-nloglik", early_stopping_rounds=50,
            tree_method="hist", n_jobs=-1, random_state=42)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        return m, int(m.best_iteration) + 1
    m = HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.05, max_iter=500, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0, early_stopping=False, random_state=42)
    m.fit(Xtr, ytr)
    devs = [mean_poisson_deviance(yva, np.clip(p, 1e-6, None)) for p in m.staged_predict(Xva)]
    return m, int(np.argmin(devs)) + 1


def refit(Xall, yall, best_n):
    if BACKEND == "xgboost":
        m = xgb.XGBRegressor(
            objective="count:poisson", n_estimators=best_n, learning_rate=0.05,
            max_depth=6, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            reg_lambda=1.0, tree_method="hist", n_jobs=-1, random_state=42)
    else:
        m = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.05, max_iter=best_n, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, early_stopping=False, random_state=42)
    m.fit(Xall, yall)
    return m


def predict(m, X, best_n=None):
    if BACKEND != "xgboost" and best_n is not None and hasattr(m, "staged_predict"):
        for i, p in enumerate(m.staged_predict(X), start=1):
            if i == best_n:
                return np.clip(p, 0, None)
    return np.clip(m.predict(X), 0, None)


def save_model(m, name):
    if BACKEND == "xgboost":
        m.save_model(str(MODEL_DIR / f"{name}.json"))
    else:
        joblib.dump(m, MODEL_DIR / f"{name}.joblib")


# ---------------------------------------------------------------------------
# 4. Train DEMAND and DONATION models
# ---------------------------------------------------------------------------
results = {}   # target -> dict of artefacts
for target, tcol in [("demand", "target_demand"), ("donation", "target_donation")]:
    print(f"\n--- {target.upper()} model ---")
    m_val, best_n = fit_with_validation(train[FEATURE_COLS], train[tcol],
                                        val[FEATURE_COLS], val[tcol])
    print(f"Best number of trees (chosen on validation): {best_n}")
    val_pred = predict(m_val, val[FEATURE_COLS], best_n)

    m_final = refit(trval[FEATURE_COLS], trval[tcol], best_n)
    test_pred = predict(m_final, test[FEATURE_COLS])
    save_model(m_final, f"blood_{target}_model")
    results[target] = dict(model=m_final, best_n=best_n, val_pred=val_pred, test_pred=test_pred)

val = val.assign(pred_demand=results["demand"]["val_pred"],
                 pred_donation=results["donation"]["val_pred"])
test = test.assign(pred_demand=results["demand"]["test_pred"],
                   pred_donation=results["donation"]["test_pred"])

# ---------------------------------------------------------------------------
# 5. Baselines (demand and donations)
# ---------------------------------------------------------------------------
def add_baselines(df):
    df = df.copy()
    df["naive"] = df["demand_lag_1"]
    df["seasonal_naive"] = df["demand_lag_7"]
    df["moving_avg_7"] = df["demand_roll_mean_7"]
    df["don_naive"] = df["donation_lag_1"]
    df["don_seasonal_naive"] = df["donation_lag_7"]
    df["don_moving_avg_7"] = df["donation_roll_mean_7"]
    return df

val, test = add_baselines(val), add_baselines(test)

# ---------------------------------------------------------------------------
# 6. Comparison table
# ---------------------------------------------------------------------------
MODELS_DEMAND = {"Naive (yesterday)": "naive", "Seasonal naive (last week)": "seasonal_naive",
                 "7-day moving average": "moving_avg_7", f"Boosted model ({BACKEND.split(' ')[0]})": "pred_demand"}
MODELS_DON = {"Naive (yesterday)": "don_naive", "Seasonal naive (last week)": "don_seasonal_naive",
              "7-day moving average": "don_moving_avg_7", f"Boosted model ({BACKEND.split(' ')[0]})": "pred_donation"}

rows = []
for split_name, df in [("validation", val), ("test", test)]:
    for target, ycol, models in [("demand", "target_demand", MODELS_DEMAND),
                                 ("donation", "target_donation", MODELS_DON)]:
        for mname, pcol in models.items():
            for scope in ["ALL"] + GROUPS:
                sub = df if scope == "ALL" else df[df.blood_group == scope]
                r = metrics(sub, ycol, pcol)
                rows.append({"target": target, "split": split_name, "model": mname,
                             "scope": scope, **r})
comp = pd.DataFrame(rows).round(3)
comp.to_csv(OUT_DIR / "model_comparison_blood.csv", index=False)

print("\n" + "=" * 78)
print("TEST SET (2025 H2) - overall, all hospitals & groups")
print("=" * 78)
for target in ["demand", "donation"]:
    t = comp[(comp.split == "test") & (comp.scope == "ALL") & (comp.target == target)]
    print(f"\n{target.upper()}")
    print(t[["model", "MAE", "RMSE", "WAPE_%"]].to_string(index=False))

print("\nDEMAND - test one-day-ahead WAPE_% by blood group")
piv = (comp[(comp.split == "test") & (comp.target == "demand") & (comp.scope != "ALL")]
       .pivot(index="scope", columns="model", values="WAPE_%").reindex(GROUPS))
print(piv.round(1).to_string())

# ---------------------------------------------------------------------------
# 7. Prediction intervals (negative binomial around predicted mean)
# ---------------------------------------------------------------------------
def estimate_alpha(df, ycol, pcol):
    """Dispersion alpha per blood group: Var = mu + alpha * mu^2 (method of moments)."""
    out = {}
    for g in GROUPS:
        s = df[df.blood_group == g]
        y, mu = s[ycol].values, s[pcol].values
        a = (np.sum((y - mu) ** 2 - mu)) / max(np.sum(mu ** 2), 1e-9)
        out[g] = float(np.clip(a, 0.0, 5.0))
    return out


def nb_quantile(q, mu, alpha):
    mu = np.asarray(mu, dtype=float)
    alpha = np.asarray(alpha, dtype=float)
    out = np.zeros_like(mu)
    pois = alpha < 1e-6
    out[pois] = stats.poisson.ppf(q, np.clip(mu[pois], 1e-9, None))
    nb = ~pois
    n = 1.0 / alpha[nb]
    p = n / (n + np.clip(mu[nb], 1e-9, None))
    out[nb] = stats.nbinom.ppf(q, n, p)
    return out


ALPHA_DEMAND = estimate_alpha(val, "target_demand", "pred_demand")
print("\nDispersion (alpha) per group, demand:", {k: round(v, 3) for k, v in ALPHA_DEMAND.items()})

test["alpha"] = test["blood_group"].map(ALPHA_DEMAND)
test["demand_lower"] = nb_quantile(LOWER_Q, test["pred_demand"], test["alpha"])
test["demand_upper"] = nb_quantile(UPPER_Q, test["pred_demand"], test["alpha"])
inside = (test.target_demand >= test.demand_lower) & (test.target_demand <= test.demand_upper)
below_upper = test.target_demand <= test.demand_upper
print(f"\nTest interval coverage (target 80% inside [P10, P90]): {100 * inside.mean():.1f}%")
print(f"Test: demand at or below the P90 upper bound: {100 * below_upper.mean():.1f}% of hospital-days")
print("(for a well-calibrated upper bound this should be close to 90%)")
cov_g = test.assign(ok=below_upper).groupby("blood_group")["ok"].mean().reindex(GROUPS) * 100
print("By group (% of days demand <= upper bound):", cov_g.round(1).to_dict())

test_out = test[["date", "hospital_id", "blood_group", "target_demand", "pred_demand",
                 "demand_lower", "demand_upper", "target_donation", "pred_donation"]].copy()
test_out.round(3).to_csv(OUT_DIR / "blood_test_predictions.csv", index=False)

# ---------------------------------------------------------------------------
# 8. Recursive multi-day forecasting (used for evaluation AND the live forecast)
# ---------------------------------------------------------------------------
FESTIVALS = ["2023-01-15", "2024-01-15", "2025-01-14", "2023-04-14", "2024-04-14", "2025-04-14",
             "2023-08-15", "2024-08-15", "2025-08-15", "2023-11-12", "2024-11-01", "2025-10-20",
             # 2026 (approximate public-holiday dates)
             "2026-01-15", "2026-04-14", "2026-08-15", "2026-11-08"]
fest_days = {pd.Timestamp(f) + pd.Timedelta(days=k) for f in FESTIVALS for k in range(-2, 3)}

START = ops.date.min()
LAST_DATE = ops.date.max()
ops_sorted = ops.sort_values(["hospital_id", "blood_group", "date"])
KEYS = list(ops_sorted[["hospital_id", "blood_group"]].drop_duplicates().itertuples(index=False, name=None))
FULL = {}
for k, s_ in ops_sorted.groupby(["hospital_id", "blood_group"]):
    FULL[k] = {c: s_[c].values.astype(float) for c in
               ["units_demanded", "units_donated", "closing_stock", "units_expiring_3d", "units_procured"]}
ALPHA_ARR = np.array([ALPHA_DEMAND[g] for _, g in KEYS])
STATIC = ["trauma_tier", "icu_beds", "general_beds", "has_cath_lab", "blood_group_code",
          "is_rh_negative", "hospital_code", "acc_7d", "acc_30d", "acc_severe_30d"]
feat_by_date = {d: df_.set_index(["hospital_id", "blood_group"])
                for d, df_ in feat[feat.date.isin(
                    [LAST_DATE] + [pd.Timestamp("2025-06-30") + pd.Timedelta(days=7 * i) for i in range(0, 26)])
                ].groupby("date")}


def recursive_forecast(origin, horizon):
    """Forecast `horizon` days after `origin`, using only data up to `origin`."""
    idx = (origin - START).days
    stat = feat_by_date[origin]
    dem_hist = {k: list(FULL[k]["units_demanded"][:idx + 1]) for k in KEYS}
    don_hist = {k: list(FULL[k]["units_donated"][:idx + 1]) for k in KEYS}
    stock = {k: FULL[k]["closing_stock"][idx] for k in KEYS}
    expiring = {k: FULL[k]["units_expiring_3d"][idx] for k in KEYS}
    procured_prev = {k: FULL[k]["units_procured"][idx] for k in KEYS}
    unmet_prev = {k: 0.0 for k in KEYS}
    out = []
    for step in range(1, horizon + 1):
        day = origin + pd.Timedelta(days=step)
        recs = []
        for k in KEYS:
            dem, don = dem_hist[k], don_hist[k]
            r = {
                "demand_lag_1": dem[-1], "demand_lag_7": dem[-7], "demand_lag_14": dem[-14],
                "demand_lag_28": dem[-28], "donation_lag_1": don[-1], "donation_lag_7": don[-7],
                "unmet_lag_1": unmet_prev[k],
                "demand_roll_mean_7": np.mean(dem[-7:]), "demand_roll_mean_14": np.mean(dem[-14:]),
                "demand_roll_mean_28": np.mean(dem[-28:]),
                "demand_roll_std_7": np.std(dem[-7:], ddof=1), "demand_roll_std_14": np.std(dem[-14:], ddof=1),
                "donation_roll_mean_7": np.mean(don[-7:]), "donation_roll_mean_28": np.mean(don[-28:]),
                "day_of_week": day.dayofweek, "is_weekend": int(day.dayofweek >= 5), "month": day.month,
                "day_of_year": day.dayofyear, "week_of_year": int(day.isocalendar().week),
                "is_festival": int(day in fest_days), "is_summer_dip": int(day.month in (5, 6)),
                "stock_prev_close": stock[k], "expiring_3d_prev": expiring[k],
                "procured_lag_1": procured_prev[k],
            }
            r["days_of_cover_prev"] = (min(60.0, stock[k] / r["demand_roll_mean_7"])
                                       if r["demand_roll_mean_7"] > 0 else 60.0)
            for c in STATIC:                      # held at last known value
                r[c] = stat.loc[k, c]
            recs.append(r)
        X = pd.DataFrame(recs)[FEATURE_COLS]
        mu_dem = predict(results["demand"]["model"], X)
        mu_don = predict(results["donation"]["model"], X)
        lo = nb_quantile(LOWER_Q, mu_dem, ALPHA_ARR)
        hi = nb_quantile(UPPER_Q, mu_dem, ALPHA_ARR)
        for i, k in enumerate(KEYS):
            out.append((day, k[0], k[1], step, mu_dem[i], lo[i], hi[i], mu_don[i]))
            dem_hist[k].append(float(mu_dem[i]))
            don_hist[k].append(float(mu_don[i]))
            stock[k] = max(0.0, stock[k] + mu_don[i] - mu_dem[i])   # rough running stock (no expiry)
            procured_prev[k] = 0.0
            unmet_prev[k] = 0.0
    return pd.DataFrame(out, columns=["date", "hospital_id", "blood_group", "horizon_day",
                                      "demand_forecast", "demand_lower_p10", "demand_upper_p90",
                                      "donation_forecast"])


# ---- 8a. Rolling-origin evaluation of the 7-day-ahead forecast (test period) ----
H_EVAL = 7
origins = [pd.Timestamp("2025-06-30") + pd.Timedelta(days=7 * i) for i in range(0, 26)]
eval_rows = []
step_rows = []
for o in origins:
    fc = recursive_forecast(o, H_EVAL)
    idx = (o - START).days
    for (h, g), sub in fc.groupby(["hospital_id", "blood_group"]):
        a_dem = FULL[(h, g)]["units_demanded"][idx + 1: idx + 1 + H_EVAL]
        a_don = FULL[(h, g)]["units_donated"][idx + 1: idx + 1 + H_EVAL]
        hist_dem = FULL[(h, g)]["units_demanded"][:idx + 1]
        hist_don = FULL[(h, g)]["units_donated"][:idx + 1]
        al = ALPHA_DEMAND[g]
        var_sum = float(np.sum(sub.demand_forecast + al * sub.demand_forecast ** 2))
        up7 = float(sub.demand_forecast.sum() + stats.norm.ppf(UPPER_Q) * np.sqrt(var_sum))
        eval_rows.append({
            "origin": o, "hospital_id": h, "blood_group": g,
            "actual_dem_7d": a_dem.sum(), "actual_don_7d": a_don.sum(),
            "boost_dem_7d": sub.demand_forecast.sum(), "boost_don_7d": sub.donation_forecast.sum(),
            "prevweek_dem_7d": hist_dem[-7:].sum(), "prevweek_don_7d": hist_don[-7:].sum(),
            "avg28_dem_7d": hist_dem[-28:].mean() * 7, "avg28_don_7d": hist_don[-28:].mean() * 7,
            "upper90_dem_7d": up7, "sumP90_dem_7d": sub.demand_upper_p90.sum()})
        for st, a_d, p_d in zip(sub.horizon_day, a_dem, sub.demand_forecast):
            step_rows.append((st, g, a_d, p_d))

ev = pd.DataFrame(eval_rows)
ev.to_csv(OUT_DIR / "blood_horizon7_predictions.csv", index=False)

hz_rows = []
for target, act, mods in [("demand", "actual_dem_7d", {"Previous week total": "prevweek_dem_7d",
                                                       "28-day average x 7": "avg28_dem_7d",
                                                       "Boosted model (recursive)": "boost_dem_7d"}),
                          ("donation", "actual_don_7d", {"Previous week total": "prevweek_don_7d",
                                                         "28-day average x 7": "avg28_don_7d",
                                                         "Boosted model (recursive)": "boost_don_7d"})]:
    for mname, pcol in mods.items():
        for scope in ["ALL"] + GROUPS:
            sub = ev if scope == "ALL" else ev[ev.blood_group == scope]
            y, p = sub[act].values, sub[pcol].values
            hz_rows.append({"target": target, "model": mname, "scope": scope,
                            "MAE_7d_units": np.mean(np.abs(y - p)),
                            "WAPE_7d_%": 100 * wape(y, p), "n": len(sub)})
hz = pd.DataFrame(hz_rows).round(3)
hz.to_csv(OUT_DIR / "horizon7_comparison_blood.csv", index=False)

print("\n" + "=" * 78)
print(f"7-DAY-AHEAD EVALUATION (rolling origin, {len(origins)} weekly origins in test period)")
print("=" * 78)
for target in ["demand", "donation"]:
    t = hz[(hz.target == target) & (hz.scope == "ALL")]
    print(f"\n{target.upper()} - total over next 7 days, per hospital x blood group")
    print(t[["model", "MAE_7d_units", "WAPE_7d_%"]].to_string(index=False))
print("\nDEMAND - 7-day WAPE_% by blood group")
pz = hz[(hz.target == "demand") & (hz.scope != "ALL")].pivot(index="scope", columns="model", values="WAPE_7d_%").reindex(GROUPS)
print(pz.round(1).to_string())

cov7 = (ev.actual_dem_7d <= ev.upper90_dem_7d).mean() * 100
covs = (ev.actual_dem_7d <= ev.sumP90_dem_7d).mean() * 100
print(f"\n7-day upper bound (normal approx, P90): actual demand <= bound in {cov7:.1f}% of cases")
print(f"Sum of daily P90 bounds (more conservative): actual demand <= bound in {covs:.1f}% of cases")

st_df = pd.DataFrame(step_rows, columns=["step", "g", "a", "p"])
by_step = st_df.groupby("step").apply(lambda d: 100 * wape(d.a.values, d.p.values)).round(1)
print("\nDaily WAPE_% by days-ahead (boosted, recursive):", by_step.to_dict())

# ---- 8b. Live forecast beyond the last data date ----
forecast = recursive_forecast(LAST_DATE, HORIZON).round(3)
forecast.to_csv(OUT_DIR / "blood_forecasts.csv", index=False)
print(f"\nSaved {HORIZON}-day forecast: {len(forecast):,} rows -> {OUT_DIR / 'blood_forecasts.csv'}")
print(f"Forecast window: {forecast.date.min().date()} to {forecast.date.max().date()}")

# ---------------------------------------------------------------------------
# 9. Figures
# ---------------------------------------------------------------------------
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.25,
                     "axes.spines.top": False, "axes.spines.right": False})

# 9a. Total daily demand: actual vs predicted on the test period
tot = test.groupby("date")[["target_demand", "pred_demand", "demand_lower", "demand_upper", "seasonal_naive"]].sum()
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(tot.index, tot.target_demand, color="#C0392B", label="Actual", lw=1.4)
ax.plot(tot.index, tot.pred_demand, color="#1F618D", label="Boosted model", lw=1.4)
ax.plot(tot.index, tot.seasonal_naive, color="grey", label="Seasonal naive", lw=1, ls="--")
ax.set_title("Test period: total daily blood demand (all hospitals, all groups)")
ax.set_ylabel("Units")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "forecast_01_test_total.png")
plt.close(fig)

# 9b. One busy hospital-group with intervals
ex = test[(test.hospital_id == "HOSP04") & (test.blood_group == "O+")].set_index("date")
fig, ax = plt.subplots(figsize=(11, 4))
ax.fill_between(ex.index, ex.demand_lower, ex.demand_upper, color="#AED6F1", alpha=0.6, label="P10-P90 interval")
ax.plot(ex.index, ex.target_demand, color="#C0392B", lw=1.2, label="Actual")
ax.plot(ex.index, ex.pred_demand, color="#1F618D", lw=1.4, label="Forecast")
ax.set_title("Test period: O+ demand at HOSP04 with prediction interval")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "forecast_02_interval_example.png")
plt.close(fig)

# 9c. 7-day WAPE by group: baselines vs boosted
w = pz[["28-day average x 7", "Boosted model (recursive)"]]
fig, ax = plt.subplots(figsize=(8, 4))
x = np.arange(len(GROUPS))
ax.bar(x - 0.2, w.iloc[:, 0], 0.4, label="28-day average x 7", color="grey")
ax.bar(x + 0.2, w.iloc[:, 1], 0.4, label="Boosted model", color="#1F618D")
ax.set_xticks(x)
ax.set_xticklabels(GROUPS)
ax.set_ylabel("7-day-ahead WAPE (%)")
ax.set_title("Test: 7-day-ahead demand error by blood group (lower is better)")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "forecast_03_wape_by_group.png")
plt.close(fig)

# 9d. Next-14-day forecast, total
f_tot = forecast.groupby("date")[["demand_forecast", "demand_upper_p90", "donation_forecast"]].sum()
hist_tot = ops[ops.date > LAST_DATE - pd.Timedelta(days=42)].groupby("date")[["units_demanded", "units_donated"]].sum()
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(hist_tot.index, hist_tot.units_demanded, color="#C0392B", label="Demand (actual)")
ax.plot(hist_tot.index, hist_tot.units_donated, color="#2874A6", label="Donations (actual)")
ax.plot(f_tot.index, f_tot.demand_forecast, color="#C0392B", ls="--", label="Demand (forecast)")
ax.plot(f_tot.index, f_tot.donation_forecast, color="#2874A6", ls="--", label="Donations (forecast)")
ax.axvline(LAST_DATE, color="k", lw=0.8)
ax.set_title("Last 6 weeks and next 14 days (all hospitals, all groups)")
ax.legend(ncol=2)
fig.tight_layout()
fig.savefig(FIG_DIR / "forecast_04_next14.png")
plt.close(fig)

print("\nDone. Figures saved to", FIG_DIR)
