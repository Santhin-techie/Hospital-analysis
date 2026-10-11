"""
Module 3 — Blood Bank Intelligence: Simulated Dataset Generator
-----------------------------------------------------------------
Purpose : Hospital-level daily blood stock, donation and demand records are not
          public in India. This script simulates 3 years (2023-2025) of daily
          RBC (red cell) operations for the 12 hospitals in chennai_hospitals.csv,
          using the SAME hospital_id as Modules 1, 2 and 4.

Grounding (real inputs this script reads):
  1. data/simulated/chennai_hospitals.csv      -> hospital size (beds) and trauma tier
  2. data/simulated/chennai_simulated_accidents.csv -> trauma-driven demand
     (accident counts are scaled up to real Chennai City totals from
      data/raw/tn road accidents report.csv: 2023 = 3,654 accidents)
  3. ABO/Rh group shares for India (approximate, from published population
     surveys; O+ ~35%, B+ ~31%, A+ ~21%, AB+ ~7%, all Rh-negative ~5%)
  4. RBC shelf life 35 days (CPDA-1 whole blood / RBC, standard storage)
  5. Reference to be used for the calibration check: e-RaktKosh / NBTC
     annual collection figures (fill in README with the exact number you cite)

Simulated (assumption, documented): bed-to-demand rates, camp events,
festival effects, procurement fill rates.

Outputs (data/simulated/):
  blood_daily_operations.csv     one row per date x hospital x blood group
  blood_inventory_batches.csv    batches still in stock on the last day (FIFO)
  blood_calibration_report.txt   simulated vs reference sanity numbers
  blood_coverage_results.csv     Module 3 -> dashboard data contract
                                 (hospital_id, blood_group, stock_units,
                                  forecasted_demand, status + extras)
"""

import os
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

np.random.seed(2025)  # reproducible

# ---------------------------------------------------------------------------
# Paths (relative to repo root so it runs on any machine)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
RAW_DIR = ROOT / "data" / "raw"

START, END = "2023-01-01", "2025-12-31"
DATES = pd.date_range(START, END, freq="D")
N_DAYS = len(DATES)

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
# Approximate Indian population shares (sum = 1.0)
GROUP_SHARE = dict(zip(GROUPS, [0.215, 0.010, 0.315, 0.016, 0.065, 0.005, 0.355, 0.019]))
assert abs(sum(GROUP_SHARE.values()) - 1.0) < 1e-9

SHELF_LIFE_DAYS = 35            # RBC
PROCURED_AGE_DAYS = 2           # units from regional centre arrive 2 days old

# Emergency/trauma demand skews to O (universal donor used before typing)
TRAUMA_GROUP_SHARE = dict(zip(GROUPS, [0.20, 0.010, 0.29, 0.014, 0.060, 0.004, 0.37, 0.052]))
assert abs(sum(TRAUMA_GROUP_SHARE.values()) - 1.0) < 1e-9

# Supply side: how much of a shortfall the regional blood centre can fill
FILL_RATE = {g: (0.30 if g.endswith("-") else 0.60) for g in GROUPS}

# ---------------------------------------------------------------------------
# 1. Load real/shared inputs
# ---------------------------------------------------------------------------
hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv")
acc = pd.read_csv(SIM_DIR / "chennai_simulated_accidents.csv", parse_dates=["date"])
raw = pd.read_csv(RAW_DIR / "tn road accidents report.csv")
real_chennai = raw[raw["District"].str.contains("CHENNAI", na=False)].iloc[0]
REAL_ACC = {2023: int(real_chennai["Total Accidents 2023"]),
            2022: int(real_chennai["Total Accidents 2022"]),
            2021: int(real_chennai["Total Accidents 2021"])}

# Scale: each simulated accident point represents (real / simulated) accidents
sim_2023 = int((acc["date"].dt.year == 2023).sum())
ACC_SCALE = REAL_ACC[2023] / sim_2023

# RBC units transfused per accident by severity (assumption)
UNITS_PER_ACCIDENT = {"Fatal": 1.5, "Grievous": 3.0, "Minor": 0.2, "NonInjury": 0.0}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# Each accident is attributed to its nearest trauma-capable hospital (tier 1/2).
# (Module 4 replaces this straight-line step with real road travel time.)
trauma_h = hosp[hosp["trauma_tier"] <= 2].reset_index(drop=True)
dist = np.stack([haversine_km(acc["latitude"].values, acc["longitude"].values,
                              r.latitude, r.longitude) for r in trauma_h.itertuples()], axis=1)
acc["hospital_id"] = trauma_h["hospital_id"].values[dist.argmin(axis=1)]
acc["trauma_units"] = acc["severity"].map(UNITS_PER_ACCIDENT) * ACC_SCALE

trauma_daily = (acc.groupby(["hospital_id", "date"])["trauma_units"].sum()
                .unstack("hospital_id").reindex(DATES).fillna(0.0))

# ---------------------------------------------------------------------------
# 2. Calendar effects
# ---------------------------------------------------------------------------
# Festival dates (fixed, documented). Window = +/- 2 days.
FESTIVALS = ["2023-01-15", "2024-01-15", "2025-01-14",      # Pongal
             "2023-04-14", "2024-04-14", "2025-04-14",      # Tamil New Year
             "2023-08-15", "2024-08-15", "2025-08-15",      # Independence Day
             "2023-11-12", "2024-11-01", "2025-10-20"]      # Deepavali
is_festival = np.zeros(N_DAYS, dtype=bool)
for f in FESTIVALS:
    i = (pd.Timestamp(f) - DATES[0]).days
    is_festival[max(0, i - 2): i + 3] = True

dow = DATES.dayofweek.values            # 0 = Mon
month = DATES.month.values
is_weekend = dow >= 5

# Elective surgery / OPD driven demand: weekdays high, Sunday low
DOW_DEMAND = np.array([1.08, 1.08, 1.05, 1.05, 1.03, 0.92, 0.79])[dow]
# Donations: camps and free time on weekends; dip in peak summer (May-Jun)
DOW_DONATION = np.array([0.90, 0.90, 0.92, 0.95, 1.00, 1.35, 1.30])[dow]
SEASON_DONATION = np.where(np.isin(month, [5, 6]), 0.80, 1.0)
# Slow growth trend in demand (~4%/yr)
TREND = 1.0 + 0.04 * (np.arange(N_DAYS) / 365.0)

# ---------------------------------------------------------------------------
# 3. Hospital base demand from size (assumption: RBC units/day)
# ---------------------------------------------------------------------------
hosp["base_units_per_day"] = 0.04 * hosp["general_beds"] + 0.25 * hosp["icu_beds"]
BASE = hosp.set_index("hospital_id")["base_units_per_day"].to_dict()

# ---------------------------------------------------------------------------
# 4. Daily simulation with FIFO batches, expiry and procurement
# ---------------------------------------------------------------------------
rows = []
final_batches = []

for h in hosp["hospital_id"]:
    base = BASE[h]
    trauma = trauma_daily[h].values if h in trauma_daily else np.zeros(N_DAYS)

    # Pre-draw demand and donations for all groups (vectorised)
    demand = {}
    donate = {}
    for g in GROUPS:
        routine = base * GROUP_SHARE[g] * DOW_DEMAND * TREND
        trauma_part = trauma * TRAUMA_GROUP_SHARE[g]
        lam_d = (routine + trauma_part) * np.where(is_festival, 1.10, 1.0)
        demand[g] = np.random.poisson(lam_d)

        # Donations: ~ 0.97 of average demand in total, but negatives under-donate
        # relative to the (O-skewed) demand -> structural shortage for O-/B-.
        supply_ratio = 0.85 if g.endswith("-") else 0.98
        lam_don = (base * GROUP_SHARE[g] * supply_ratio * DOW_DONATION * SEASON_DONATION
                   * np.where(is_festival, 0.70, 1.0))
        d = np.random.poisson(lam_don)
        # Random donation camps: ~1.2% of days, +15-40 units spread by group share
        camp = np.random.rand(N_DAYS) < 0.012
        d = d + camp * np.random.poisson(np.random.uniform(15, 40, N_DAYS) * GROUP_SHARE[g])
        donate[g] = d

    for g in GROUPS:
        avg_daily = base * GROUP_SHARE[g]
        target = max(3, int(round(3 * avg_daily))) if not g.endswith("-") else max(2, int(round(5 * avg_daily)))
        batches = deque()  # [expiry_index, units]  oldest first
        opening_stock = int(round(4 * avg_daily)) + 2
        batches.append([SHELF_LIFE_DAYS - 10, opening_stock])

        for t in range(N_DAYS):
            # 1) expire
            expired = 0
            while batches and batches[0][0] <= t:
                expired += batches.popleft()[1]
            opening = sum(b[1] for b in batches)

            # 2) receive donations (collected today)
            don = int(donate[g][t])
            if don:
                batches.append([t + SHELF_LIFE_DAYS, don])

            # 3) issue FIFO
            need = int(demand[g][t])
            issued = 0
            while need > 0 and batches:
                take = min(need, batches[0][1])
                batches[0][1] -= take
                need -= take
                issued += take
                if batches[0][1] == 0:
                    batches.popleft()
            unmet = need

            # 4) procurement from regional centre if below target (arrives aged)
            on_hand = sum(b[1] for b in batches)
            procured = 0
            if on_hand < target:
                procured = int(round((target - on_hand) * FILL_RATE[g] * np.random.uniform(0.7, 1.0)))
                if procured:
                    # insert keeping oldest-first order
                    exp = t + SHELF_LIFE_DAYS - PROCURED_AGE_DAYS
                    pos = 0
                    for pos, b in enumerate(batches):
                        if b[0] > exp:
                            break
                    else:
                        pos = len(batches)
                    batches.insert(pos, [exp, procured])

            closing = sum(b[1] for b in batches)
            exp_in_3 = sum(b[1] for b in batches if b[0] - t <= 3)
            rows.append((DATES[t], h, g, opening, don, procured, int(demand[g][t]),
                         issued, unmet, expired, closing, exp_in_3))

        # keep the final batch ledger
        for exp_idx, units in batches:
            final_batches.append((h, g, DATES[-1] + pd.Timedelta(days=exp_idx - (N_DAYS - 1)) - pd.Timedelta(days=SHELF_LIFE_DAYS),
                                  DATES[-1] + pd.Timedelta(days=exp_idx - (N_DAYS - 1)), units))

ops = pd.DataFrame(rows, columns=[
    "date", "hospital_id", "blood_group", "opening_stock", "units_donated",
    "units_procured", "units_demanded", "units_issued", "units_unmet",
    "units_expired", "closing_stock", "units_expiring_3d"])

# Sanity checks (simulation bugs would show up here)
assert (ops["closing_stock"] >= 0).all(), "negative stock = simulation bug"
assert (ops["units_issued"] + ops["units_unmet"] == ops["units_demanded"]).all()
assert not ops.duplicated(["date", "hospital_id", "blood_group"]).any()

# ---------------------------------------------------------------------------
# 5. Save main outputs
# ---------------------------------------------------------------------------
SIM_DIR.mkdir(parents=True, exist_ok=True)
ops.to_csv(SIM_DIR / "blood_daily_operations.csv", index=False)

batches_df = pd.DataFrame(final_batches, columns=[
    "hospital_id", "blood_group", "collection_date", "expiry_date", "units"])
batches_df["days_to_expiry"] = (batches_df["expiry_date"] - pd.Timestamp(END)).dt.days
batches_df.to_csv(SIM_DIR / "blood_inventory_batches.csv", index=False)

# ---------------------------------------------------------------------------
# 6. Calibration / sanity report
# ---------------------------------------------------------------------------
ops["year"] = ops["date"].dt.year
yr = ops.groupby("year").agg(collected=("units_donated", "sum"),
                             procured=("units_procured", "sum"),
                             demanded=("units_demanded", "sum"),
                             unmet=("units_unmet", "sum"),
                             expired=("units_expired", "sum"))
yr["wastage_rate_%"] = (100 * yr["expired"] / (yr["collected"] + yr["procured"])).round(2)
yr["fill_rate_%"] = (100 * (1 - yr["unmet"] / yr["demanded"])).round(2)

grp = ops.groupby("blood_group").agg(demanded=("units_demanded", "sum"),
                                      donated=("units_donated", "sum"),
                                      unmet=("units_unmet", "sum"))
grp["demand_share_%"] = (100 * grp["demanded"] / grp["demanded"].sum()).round(2)
grp["donation_per_demand"] = (grp["donated"] / grp["demanded"]).round(3)
grp["unmet_%"] = (100 * grp["unmet"] / grp["demanded"]).round(2)

with open(SIM_DIR / "blood_calibration_report.txt", "w") as f:
    f.write("MODULE 3 - SIMULATION CALIBRATION REPORT\n")
    f.write(f"Period: {START} to {END}  |  Hospitals: {hosp.shape[0]}  |  Groups: {len(GROUPS)}\n\n")
    f.write(f"Accident scaling: sim 2023 = {sim_2023} points, real Chennai City 2023 = "
            f"{REAL_ACC[2023]} -> each point represents {ACC_SCALE:.1f} accidents\n\n")
    f.write("Yearly totals (units):\n" + yr.drop(columns=[]).to_string() + "\n\n")
    f.write("By blood group:\n" + grp.to_string() + "\n\n")
    f.write("TODO (manual): compare yearly 'collected' with the e-RaktKosh / NBTC figure you cite,\n"
            "scaled to a 12-hospital subset of Chennai, and paste the comparison here.\n")

# ---------------------------------------------------------------------------
# 7. Module 3 -> dashboard data contract (BASELINE forecast, to be replaced by
#    the Prophet / XGBoost forecast in the next stage)
# ---------------------------------------------------------------------------
last = ops[ops["date"] > pd.Timestamp(END) - pd.Timedelta(days=28)]
snap = ops[ops["date"] == pd.Timestamp(END)].set_index(["hospital_id", "blood_group"])
agg = last.groupby(["hospital_id", "blood_group"]).agg(
    avg_demand=("units_demanded", "mean"), avg_donation=("units_donated", "mean"))

contract = []
for (h, g), r in agg.iterrows():
    stock = int(snap.loc[(h, g), "closing_stock"])
    exp3 = int(snap.loc[(h, g), "units_expiring_3d"])
    fc7 = round(r["avg_demand"] * 7, 1)
    proj = stock + r["avg_donation"] * 7 - fc7 - exp3
    cover = round(stock / r["avg_demand"], 1) if r["avg_demand"] > 0 else 99.0
    if cover < 2 or proj < 0:
        status = "SHORTAGE RISK"
    elif cover < 4:
        status = "LOW STOCK"
    elif exp3 > 0 and exp3 > 0.5 * r["avg_demand"] * 3:
        status = "EXPIRY RISK"
    else:
        status = "STABLE"
    contract.append((h, g, stock, fc7, cover, exp3, round(proj, 1), status))

contract_df = pd.DataFrame(contract, columns=[
    "hospital_id", "blood_group", "stock_units", "forecasted_demand",
    "days_of_cover", "units_expiring_3d", "projected_stock_7d", "status"])
contract_df.to_csv(SIM_DIR / "blood_coverage_results.csv", index=False)

print(f"Generated {len(ops):,} daily records -> {SIM_DIR / 'blood_daily_operations.csv'}")
print(yr.to_string())
print()
print(grp.to_string())
print()
print(contract_df["status"].value_counts().to_string())
