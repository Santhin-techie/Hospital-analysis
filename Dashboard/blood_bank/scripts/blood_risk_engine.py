"""
Module 3 — Blood Bank Intelligence: Risk Engine
------------------------------------------------
Turns the 14-day forecast + today's FIFO stock into a shortage / expiry status
for every (hospital_id, blood_group). Replaces the BASELINE contract written by
generate_blood_data.py.

For each hospital x group the next 7 days are simulated twice:
  EXPECTED scenario : demand = forecast mean,  donations = forecast mean
  STRESS scenario   : demand = P90 upper bound, donations = forecast mean
Both use FIFO issue and expiry of the real batches (blood_inventory_batches.csv).
Regional-centre procurement is NOT counted (conservative: "what happens if we do
nothing"). `recommended_units` = what must be sourced to survive the stress case.

Inputs : outputs/blood_forecasts.csv
         data/simulated/blood_inventory_batches.csv
         data/simulated/blood_daily_operations.csv
Outputs: data/simulated/blood_coverage_results.csv           (dashboard contract)
         data/simulated/blood_coverage_results_baseline.csv  (backup of old file)
         outputs/blood_risk_summary.txt

Run from the project root:   py scripts\\blood_risk_engine.py
"""

from pathlib import Path
import shutil

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
WINDOW = 7            # days ahead the risk engine looks
SHELF_LIFE = 35       # new donations expire after this many days
Z90 = 1.2816          # normal z for P90

# Status thresholds (days of cover / units)
COVER_SHORTAGE = 2.0
COVER_LOW = 3.0
EXPIRY_WASTE_SHARE = 0.5   # expected waste > 50% of 3 days of demand -> EXPIRY RISK

fc = pd.read_csv(OUT_DIR / "blood_forecasts.csv", parse_dates=["date"])
batches = pd.read_csv(SIM_DIR / "blood_inventory_batches.csv")
ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
fc = fc[fc.horizon_day <= WINDOW].sort_values(["hospital_id", "blood_group", "horizon_day"])


def simulate(batch_list, demand, donation):
    """FIFO forward simulation. batch_list = [[days_to_expiry, units], ...].
    Returns (unmet_total, expired_total, closing_stock)."""
    b = sorted([list(x) for x in batch_list], key=lambda x: x[0])
    unmet = expired = 0.0
    for d, (dem, don) in enumerate(zip(demand, donation), start=1):
        # 1) expire (same rule as the generator: expiry <= today -> gone)
        while b and b[0][0] <= d:
            expired += b.pop(0)[1]
        # 2) donations collected today
        if don > 0:
            b.append([d + SHELF_LIFE, don])
            b.sort(key=lambda x: x[0])
        # 3) issue oldest first
        need = dem
        while need > 1e-9 and b:
            take = min(need, b[0][1])
            b[0][1] -= take
            need -= take
            if b[0][1] <= 1e-9:
                b.pop(0)
        unmet += max(need, 0.0)
    return unmet, expired, sum(x[1] for x in b)


rows = []
grp_b = {k: v for k, v in batches.groupby(["hospital_id", "blood_group"])}
for (h, g), s in fc.groupby(["hospital_id", "blood_group"]):
    bt = grp_b.get((h, g))
    blist = [] if bt is None else bt[["days_to_expiry", "units"]].values.tolist()
    stock = float(sum(u for _, u in blist))
    exp3 = float(sum(u for d, u in blist if d <= 3))

    mu = s["demand_forecast"].values
    p90 = s["demand_upper_p90"].values
    don = s["donation_forecast"].values

    # Stress demand: P90 each day is too pessimistic when summed, so use a
    # 7-day normal-approx upper bound and spread it in proportion to the mean.
    sigma_day = np.maximum((p90 - mu) / Z90, 0.0)
    up7 = mu.sum() + Z90 * np.sqrt(np.sum(sigma_day ** 2))
    stress = mu * (up7 / mu.sum()) if mu.sum() > 0 else mu

    unmet_e, expired_e, close_e = simulate(blist, mu, don)
    unmet_s, expired_s, close_s = simulate(blist, stress, don)

    avg_dem = mu.mean()
    cover = round(stock / avg_dem, 1) if avg_dem > 0 else 99.0

    if unmet_e > 0.5 or cover < COVER_SHORTAGE:
        status = "SHORTAGE RISK"
    elif unmet_s > 0.5 or cover < COVER_LOW:
        status = "LOW STOCK"
    elif expired_e > 0 and expired_e > EXPIRY_WASTE_SHARE * avg_dem * 3:
        status = "EXPIRY RISK"
    else:
        status = "STABLE"

    rows.append({
        "hospital_id": h, "blood_group": g,
        "stock_units": int(round(stock)),
        "forecasted_demand": round(mu.sum(), 1),
        "days_of_cover": cover,
        "units_expiring_3d": int(round(exp3)),
        "projected_stock_7d": round(stock + don.sum() - mu.sum() - expired_e, 1),
        "status": status,
        # extras
        "forecasted_donations_7d": round(don.sum(), 1),
        "demand_upper_7d": round(up7, 1),
        "expected_shortfall_7d": round(unmet_e, 1),
        "stress_shortfall_7d": round(unmet_s, 1),
        "expected_expiry_waste_7d": round(expired_e, 1),
        "recommended_units": int(np.ceil(unmet_s)),
    })

res = pd.DataFrame(rows)
res["blood_group"] = pd.Categorical(res["blood_group"], GROUPS, ordered=True)
res = res.sort_values(["hospital_id", "blood_group"]).reset_index(drop=True)

# Sanity checks
assert len(res) == fc[["hospital_id", "blood_group"]].drop_duplicates().shape[0]
assert (res["stock_units"] >= 0).all()
assert res["status"].isin(["SHORTAGE RISK", "LOW STOCK", "EXPIRY RISK", "STABLE"]).all()
# stock from batch ledger should match last-day closing stock in the operations table
last = ops[ops.date == ops.date.max()].set_index(["hospital_id", "blood_group"])["closing_stock"]
chk = res.assign(blood_group=res.blood_group.astype(str)).set_index(["hospital_id", "blood_group"])["stock_units"]
mism = int((chk != last.reindex(chk.index)).sum())

# Save (back up the old baseline first)
target = SIM_DIR / "blood_coverage_results.csv"
backup = SIM_DIR / "blood_coverage_results_baseline.csv"
if target.exists() and not backup.exists():
    shutil.copy(target, backup)
res.to_csv(target, index=False)

# Summary
lines = [f"Risk engine: {len(res)} hospital x group rows, window = next {WINDOW} days "
         f"({fc.date.min().date()} to {fc[fc.horizon_day <= WINDOW].date.max().date()})",
         f"Stock ledger vs closing_stock mismatches: {mism}", "",
         "Status counts:", res["status"].value_counts().to_string(), "",
         "Status by blood group:",
         pd.crosstab(res["blood_group"], res["status"]).to_string(), "",
         "Top 10 stress shortfalls (units):",
         res.sort_values("stress_shortfall_7d", ascending=False)
            .head(10)[["hospital_id", "blood_group", "stock_units", "forecasted_demand",
                       "stress_shortfall_7d", "recommended_units", "status"]].to_string(index=False),
         "", f"Total recommended units to source: {int(res.recommended_units.sum())}"]
text = "\n".join(lines)
(OUT_DIR / "blood_risk_summary.txt").write_text(text, encoding="utf-8")
print(text)
print(f"\nSaved contract -> {target}")