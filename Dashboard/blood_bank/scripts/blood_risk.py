"""
Module 3 — Blood Bank Intelligence: Shortage Risk Engine + Expiry Tracking
---------------------------------------------------------------------------
Turns the 14-day forecasts into an actionable risk view for the next 7 days.

Inputs : outputs/blood_forecasts.csv                 (blood_forecast.py)
         data/simulated/blood_daily_operations.csv   (closing stock, history)
         data/simulated/blood_inventory_batches.csv  (batches in stock on the last day)
         data/simulated/chennai_hospitals.csv        (hospital names)
Outputs: outputs/blood_risk.csv                      one row per hospital x blood group
         outputs/blood_expiry_risk.csv               batches that will expire unused
         outputs/blood_risk_summary.txt              numbers to quote in the report
         data/simulated/blood_coverage_results.csv   dashboard data contract, REWRITTEN
                                                     with real forecasts (the old
                                                     baseline file is saved as
                                                     blood_coverage_results_baseline.csv)

Run from the project root:   py scripts\\blood_risk.py
"""

import shutil
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Settings (same values as the simulation where they overlap)
# ---------------------------------------------------------------------------
HORIZON = 7                    # days used for the risk decision
SHELF_LIFE_DAYS = 35           # RBC, same as generate_blood_data.py
RARE_GROUPS = {"A-", "B-", "AB-", "O-"}
SAFETY_DAYS = {"common": 3, "rare": 5}   # = the simulation's own stock targets
HIGH_COVER, MED_COVER = 2.0, 4.0         # days of cover thresholds
UPPER_PHI = 1.5                # overdispersion, only used if no P90 column exists
Z90 = 1.2816

# ---------------------------------------------------------------------------
# 1. Load inputs
# ---------------------------------------------------------------------------
fc = pd.read_csv(OUT_DIR / "blood_forecasts.csv", parse_dates=["date"])
fc = fc.sort_values(["hospital_id", "blood_group", "date"])
fc = fc[fc["horizon_day"] <= HORIZON]
n_days = int(fc["horizon_day"].max())

ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
last_date = ops["date"].max()
cur = (ops[ops["date"] == last_date]
       .set_index(["hospital_id", "blood_group"])["closing_stock"])

batches = pd.read_csv(SIM_DIR / "blood_inventory_batches.csv",
                      parse_dates=["collection_date", "expiry_date"])
hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv")
hname = hosp.set_index("hospital_id")["name"].to_dict()

# The batch ledger IS the stock on the last day; check it agrees with closing_stock.
led = batches.groupby(["hospital_id", "blood_group"])["units"].sum()
gap = (cur.sub(led, fill_value=0)).abs().sum()
print(f"Last data date: {last_date.date()} | forecast: {fc.date.min().date()} to {fc.date.max().date()}")
print(f"Batch ledger vs closing stock, total difference: {gap:.0f} units (should be 0)")

BATCHES = {k: [[r.expiry_date, float(r.units)] for r in g.sort_values("expiry_date").itertuples()]
           for k, g in batches.groupby(["hospital_id", "blood_group"])}


# ---------------------------------------------------------------------------
# 2. Day-by-day FIFO projection
# ---------------------------------------------------------------------------
def project(batch_list, demand, donations, dates):
    """Expire, receive forecast donations, issue oldest first. Returns closing path,
    unmet units, expired units and which existing batches expired (with units)."""
    bl = [[e, u, True] for e, u in batch_list]          # True = existing batch
    closing, unmet, expired_total, detail = [], 0.0, 0.0, []
    for i, d in enumerate(dates):
        keep = []
        for e, u, existing in bl:
            if e <= d:                                  # same rule as the simulation
                expired_total += u
                if existing:
                    detail.append((e, u))
            else:
                keep.append([e, u, existing])
        bl = keep
        if donations[i] > 0:
            bl.append([d + timedelta(days=SHELF_LIFE_DAYS), donations[i], False])
        bl.sort(key=lambda x: x[0])
        need = demand[i]
        for item in bl:
            if need <= 0:
                break
            t = min(item[1], need)
            item[1] -= t
            need -= t
        bl = [x for x in bl if x[1] > 1e-9]
        unmet += max(need, 0.0)
        closing.append(sum(x[1] for x in bl))
    return np.array(closing), unmet, expired_total, detail


# ---------------------------------------------------------------------------
# 3. Risk per hospital x blood group
# ---------------------------------------------------------------------------
rows, expiry_rows = [], []
for (h, g), grp in fc.groupby(["hospital_id", "blood_group"]):
    dates = list(grp["date"])
    d_pt = grp["demand_forecast"].clip(lower=0).to_numpy(float)
    don = grp["donation_forecast"].clip(lower=0).to_numpy(float)

    # 7-day upper bound. Summing daily P90s over-covers (98.5% in blood_forecast.py),
    # so use the summed daily spread / sqrt(n): daily errors are roughly independent.
    D = d_pt.sum()
    spread = (grp["demand_upper_p90"].to_numpy(float) - d_pt).clip(min=0).sum()
    upper_total = D + spread / np.sqrt(len(d_pt))
    d_up = d_pt * (upper_total / D) if D > 1e-9 else np.full(len(d_pt), upper_total / len(d_pt))

    stock_now = float(cur.get((h, g), 0.0))
    blist = BATCHES.get((h, g), [])
    close_pt, unmet_pt, exp_pt, det_pt = project(blist, d_pt, don, dates)
    close_up, unmet_up, _, _ = project(blist, d_up, don, dates)

    mean_daily, upper_daily = d_pt.mean(), d_up.mean()
    cover = min(stock_now / upper_daily, 99.0) if upper_daily > 1e-9 else 99.0
    safety = (SAFETY_DAYS["rare"] if g in RARE_GROUPS else SAFETY_DAYS["common"]) * mean_daily
    end_pt = close_pt[-1]
    exp3 = sum(u for e, u in blist if (e - last_date).days <= 3)   # same rule as simulation

    # High  : < 2 days of cover (upper-bound demand), or the point forecast runs out
    # Medium: 2-4 days of cover, or the upper-bound case runs out, or ends below safety stock
    if cover < HIGH_COVER or unmet_pt > 0.5:
        risk = "High"
    elif cover < MED_COVER or unmet_up > 0.5 or end_pt < safety:
        risk = "Medium"
    else:
        risk = "Low"
    if D < 0.5 and unmet_pt <= 0.5 and risk != "Low":    # almost no demand expected
        risk = "Low"

    rows.append(dict(
        hospital_id=h, hospital_name=hname.get(h, ""), blood_group=g, as_of_date=last_date.date(),
        stock_now=round(stock_now, 1), forecast_demand_7d=round(D, 1),
        demand_upper_7d=round(upper_total, 1), forecast_donations_7d=round(don.sum(), 1),
        days_of_cover=round(cover, 1), safety_stock=round(safety, 1),
        projected_stock_end=round(end_pt, 1), projected_stock_end_upper=round(close_up[-1], 1),
        unmet_units_point=round(unmet_pt, 1), unmet_units_upper=round(unmet_up, 1),
        units_expiring_3d=round(exp3, 1), expiring_unused_7d=round(exp_pt, 1),
        surplus_units=round(max(end_pt - safety, 0.0), 1),
        deficit_units=round(max(safety - end_pt, 0.0) + unmet_pt, 1),
        avg_daily_demand=round(mean_daily, 2), risk_level=risk))

    for e, u in det_pt:
        expiry_rows.append(dict(hospital_id=h, hospital_name=hname.get(h, ""), blood_group=g,
                                expiry_date=pd.Timestamp(e).date(), units_wasted=round(u, 1)))

risk = pd.DataFrame(rows)


def reason(r):
    if r.risk_level == "High":
        parts = []
        if r.days_of_cover < HIGH_COVER:
            parts.append(f"only {r.days_of_cover:.1f} days of cover")
        if r.unmet_units_point > 0.5:
            parts.append(f"stock projected to run out ({r.unmet_units_point:.0f} units short)")
        return "; ".join(parts)
    if r.risk_level == "Medium":
        if r.days_of_cover >= MED_COVER and r.unmet_units_upper > 0.5:
            return "could run out if demand reaches the upper bound"
        return f"{r.days_of_cover:.1f} days of cover, below the comfort level"
    return ""


risk["reason"] = risk.apply(reason, axis=1)
order = {"High": 0, "Medium": 1, "Low": 2}
risk = risk.sort_values(["risk_level", "days_of_cover"],
                        key=lambda s: s.map(order) if s.name == "risk_level" else s).reset_index(drop=True)
exp_df = pd.DataFrame(expiry_rows, columns=["hospital_id", "hospital_name", "blood_group",
                                            "expiry_date", "units_wasted"])
exp_df = exp_df.sort_values("units_wasted", ascending=False)
risk.to_csv(OUT_DIR / "blood_risk.csv", index=False)
exp_df.to_csv(OUT_DIR / "blood_expiry_risk.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Dashboard data contract (same columns generate_blood_data.py wrote)
# ---------------------------------------------------------------------------
def status(r):
    if r.risk_level == "High":
        return "SHORTAGE RISK"
    if r.risk_level == "Medium":
        return "LOW STOCK"
    if r.units_expiring_3d > 0 and r.units_expiring_3d > 0.5 * r.avg_daily_demand * 3:
        return "EXPIRY RISK"
    return "STABLE"


contract = pd.DataFrame({
    "hospital_id": risk.hospital_id, "blood_group": risk.blood_group,
    "stock_units": risk.stock_now.round(0).astype(int),
    "forecasted_demand": risk.forecast_demand_7d,
    "days_of_cover": risk.days_of_cover,
    "units_expiring_3d": risk.units_expiring_3d.round(0).astype(int),
    "projected_stock_7d": risk.projected_stock_end,
    "status": risk.apply(status, axis=1),
    # extras (a dashboard that only reads the 8 contract columns can ignore these)
    "risk_level": risk.risk_level, "demand_upper_7d": risk.demand_upper_7d, "reason": risk.reason,
}).sort_values(["hospital_id", "blood_group"])

cov_path = SIM_DIR / "blood_coverage_results.csv"
base_path = SIM_DIR / "blood_coverage_results_baseline.csv"
if cov_path.exists() and not base_path.exists():
    shutil.copy(cov_path, base_path)          # keep the old baseline version once
contract.to_csv(cov_path, index=False)

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
lines = [f"RISK SUMMARY as of {last_date.date()} (next {n_days} days)", ""]
lines.append("Risk level counts (hospital x group rows):")
lines.append(risk["risk_level"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0).astype(int).to_string())
lines.append("\nDashboard status counts:\n" + contract["status"].value_counts().to_string())
hi = risk[risk.risk_level == "High"]
lines.append("\nHigh risk by blood group:\n" + (hi["blood_group"].value_counts().to_string() if len(hi) else "none"))
lines.append("\nHigh risk by hospital:\n" +
             (hi.groupby(["hospital_id", "hospital_name"]).size().sort_values(ascending=False).head(8).to_string()
              if len(hi) else "none"))
total_in = ops["units_donated"].sum() + ops["units_procured"].sum()
lines.append(f"\nHistorical wastage rate (expired / (donated + procured)): "
             f"{100 * ops['units_expired'].sum() / total_in:.2f}%")
lines.append(f"Forecast wastage, next {n_days} days: {exp_df['units_wasted'].sum():.0f} units "
             f"across {len(exp_df)} batches")
lines.append(f"Total surplus: {risk.surplus_units.sum():.0f} units | "
             f"total deficit: {risk.deficit_units.sum():.0f} units  (input to the redistribution step)")
lines.append("\nNotes: safety stock = 3 days of mean demand (common groups) / 5 days (A-, B-, AB-, O-), "
             "matching the simulation's targets.")
lines.append("Days of cover uses the upper-bound demand. The projection ignores regional-centre "
             "procurement, so it is deliberately cautious.")
text = "\n".join(lines)
print("\n" + text)
(OUT_DIR / "blood_risk_summary.txt").write_text(text, encoding="utf-8")
print("\nSaved outputs\\blood_risk.csv, blood_expiry_risk.csv, blood_risk_summary.txt")
print(f"Rewrote {cov_path} (old version kept as {base_path.name})")