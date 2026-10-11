"""
Module 3 — Blood Bank Intelligence: Exploratory Data Analysis
--------------------------------------------------------------
Input  : data/simulated/blood_daily_operations.csv
Output : outputs/figures/eda_*.png
         outputs/blood_eda_summary.txt   (numbers to quote in the report)

Run from the project root:   py scripts\\blood_eda.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no window needed, just save files
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.25,
                     "axes.spines.top": False, "axes.spines.right": False})

ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv")
name = hosp.set_index("hospital_id")["name"].to_dict()

lines = []
def log(s=""):
    print(s)
    lines.append(str(s))

# ---------------------------------------------------------------------------
# 1. Data quality checks
# ---------------------------------------------------------------------------
log("=" * 60)
log("1. DATA QUALITY")
log("=" * 60)
log(f"Rows: {len(ops):,} | Hospitals: {ops.hospital_id.nunique()} | "
    f"Groups: {ops.blood_group.nunique()} | Days: {ops.date.nunique()}")
log(f"Date range: {ops.date.min().date()} to {ops.date.max().date()}")
log(f"Missing values: {int(ops.isna().sum().sum())}")
log(f"Duplicate (date, hospital, group) rows: {int(ops.duplicated(['date','hospital_id','blood_group']).sum())}")
log(f"Negative closing stock rows: {int((ops.closing_stock < 0).sum())}")
log(f"Rows where issued + unmet != demanded: {int((ops.units_issued + ops.units_unmet != ops.units_demanded).sum())}")
expected = ops.hospital_id.nunique() * ops.blood_group.nunique() * ops.date.nunique()
log(f"Complete panel (no missing dates): {len(ops) == expected}")

# ---------------------------------------------------------------------------
# 2. Blood group shares and structural shortage
# ---------------------------------------------------------------------------
log()
log("=" * 60)
log("2. BLOOD GROUP SUMMARY (3 years, all hospitals)")
log("=" * 60)
grp = ops.groupby("blood_group").agg(
    demanded=("units_demanded", "sum"), donated=("units_donated", "sum"),
    procured=("units_procured", "sum"), unmet=("units_unmet", "sum"),
    expired=("units_expired", "sum")).reindex(GROUPS)
grp["demand_share_%"] = (100 * grp.demanded / grp.demanded.sum()).round(2)
grp["donation_per_demand"] = (grp.donated / grp.demanded).round(3)
grp["unmet_%"] = (100 * grp.unmet / grp.demanded).round(2)
log(grp.to_string())
short = grp.sort_values("unmet_%", ascending=False).head(4).index.tolist()
log(f"\nStructurally short groups (highest unmet %): {', '.join(short)}")

# Fig 1: group share + donation/demand ratio + unmet %
fig, ax = plt.subplots(1, 3, figsize=(14, 4))
ax[0].bar(GROUPS, grp["demand_share_%"], color="#C0392B")
ax[0].set_title("Demand share by blood group (%)")
ax[1].bar(GROUPS, grp["donation_per_demand"], color="#2874A6")
ax[1].axhline(1, color="k", ls="--", lw=1)
ax[1].set_title("Donations per unit demanded")
ax[2].bar(GROUPS, grp["unmet_%"], color="#B7950B")
ax[2].set_title("Unmet demand (%)")
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_01_group_summary.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 3. Trend over time
# ---------------------------------------------------------------------------
daily = ops.groupby("date")[["units_demanded", "units_donated"]].sum()
monthly = daily.resample("MS").sum()

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(monthly.index, monthly.units_demanded, label="Demand", color="#C0392B", marker="o", ms=3)
ax.plot(monthly.index, monthly.units_donated, label="Donations", color="#2874A6", marker="o", ms=3)
ax.set_title("Monthly total demand vs donations (all hospitals)")
ax.set_ylabel("Units")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_02_monthly_trend.png")
plt.close(fig)

yearly = ops.assign(year=ops.date.dt.year).groupby("year")[["units_demanded", "units_donated"]].sum()
yearly["demand_growth_%"] = (100 * yearly.units_demanded.pct_change()).round(2)
log()
log("=" * 60)
log("3. YEARLY TOTALS")
log("=" * 60)
log(yearly.to_string())

# ---------------------------------------------------------------------------
# 4. Weekly seasonality
# ---------------------------------------------------------------------------
dow = daily.assign(dow=daily.index.dayofweek).groupby("dow").mean()
dow.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
fig, ax = plt.subplots(figsize=(8, 4))
x = np.arange(7)
ax.bar(x - 0.2, dow.units_demanded, 0.4, label="Avg demand", color="#C0392B")
ax.bar(x + 0.2, dow.units_donated, 0.4, label="Avg donations", color="#2874A6")
ax.set_xticks(x)
ax.set_xticklabels(dow.index)
ax.set_title("Weekly pattern (daily units, all hospitals)")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_03_weekly_pattern.png")
plt.close(fig)
log()
log("=" * 60)
log("4. WEEKLY PATTERN (avg units/day)")
log("=" * 60)
log(dow.round(1).to_string())

# Monthly seasonality (donation dip in May-Jun)
mon = daily.assign(m=daily.index.month).groupby("m").mean()
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(mon.index, mon.units_demanded, marker="o", label="Demand", color="#C0392B")
ax.plot(mon.index, mon.units_donated, marker="o", label="Donations", color="#2874A6")
ax.set_xticks(range(1, 13))
ax.set_title("Yearly pattern: average daily units by month")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_04_monthly_pattern.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 5. Hospital comparison
# ---------------------------------------------------------------------------
hosp_tot = ops.groupby("hospital_id").agg(demanded=("units_demanded", "sum"),
                                          unmet=("units_unmet", "sum"))
hosp_tot["unmet_%"] = (100 * hosp_tot.unmet / hosp_tot.demanded).round(2)
hosp_tot["name"] = hosp_tot.index.map(name)
log()
log("=" * 60)
log("5. DEMAND BY HOSPITAL")
log("=" * 60)
log(hosp_tot[["name", "demanded", "unmet", "unmet_%"]].to_string())

fig, ax = plt.subplots(figsize=(10, 5))
order = hosp_tot.sort_values("demanded")
ax.barh(order["name"], order["demanded"], color="#884EA0")
ax.set_title("Total units demanded by hospital (3 years)")
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_05_hospital_demand.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 6. Stock heatmap on the last day (days of cover)
# ---------------------------------------------------------------------------
last_day = ops.date.max()
recent = ops[ops.date > last_day - pd.Timedelta(days=28)]
avg_dem = recent.groupby(["hospital_id", "blood_group"]).units_demanded.mean()
stock = ops[ops.date == last_day].set_index(["hospital_id", "blood_group"]).closing_stock
cover = (stock / avg_dem.replace(0, np.nan)).unstack("blood_group")[GROUPS]
cover.index = [name[h].split(",")[0] for h in cover.index]

fig, ax = plt.subplots(figsize=(9, 6))
im = ax.imshow(cover.clip(upper=15).values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)
ax.set_xticks(range(len(GROUPS)))
ax.set_xticklabels(GROUPS)
ax.set_yticks(range(len(cover)))
ax.set_yticklabels(cover.index)
for i in range(cover.shape[0]):
    for j in range(cover.shape[1]):
        v = cover.values[i, j]
        ax.text(j, i, "-" if np.isnan(v) else f"{v:.1f}", ha="center", va="center", fontsize=8)
ax.grid(False)
ax.set_title(f"Days of cover on {last_day.date()} (stock / avg daily demand)")
fig.colorbar(im, ax=ax, label="Days")
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_06_stock_cover_heatmap.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 7. Count distribution (why rare groups need weekly / pooled forecasts)
# ---------------------------------------------------------------------------
zero_share = (ops.assign(zero=ops.units_demanded == 0)
              .groupby("blood_group").zero.mean().reindex(GROUPS) * 100).round(1)
log()
log("=" * 60)
log("6. % OF DAYS WITH ZERO DEMAND (per hospital-group-day)")
log("=" * 60)
log(zero_share.to_string())
log("-> High zero share for AB-/A-/B-/O- means plain MAPE breaks; use WAPE and "
    "pool or aggregate to weekly for the rare groups.")

fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(GROUPS, zero_share.values, color="#117A65")
ax.set_title("% of hospital-days with zero demand")
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_07_zero_demand_share.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 8. Correlation between groups' daily demand (all hospitals)
# ---------------------------------------------------------------------------
piv = ops.pivot_table(index="date", columns="blood_group", values="units_demanded", aggfunc="sum")[GROUPS]
corr = piv.corr()
fig, ax = plt.subplots(figsize=(6, 5))
im = ax.imshow(corr.values, cmap="Blues", vmin=0, vmax=1)
ax.set_xticks(range(8)); ax.set_xticklabels(GROUPS)
ax.set_yticks(range(8)); ax.set_yticklabels(GROUPS)
for i in range(8):
    for j in range(8):
        ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
ax.grid(False)
ax.set_title("Correlation of daily demand between groups")
fig.colorbar(im, ax=ax)
fig.tight_layout()
fig.savefig(FIG_DIR / "eda_08_group_correlation.png")
plt.close(fig)

# ---------------------------------------------------------------------------
# 9. Festival effect and expiry
# ---------------------------------------------------------------------------
FEST = ["2023-01-15", "2024-01-15", "2025-01-14", "2023-04-14", "2024-04-14", "2025-04-14",
        "2023-08-15", "2024-08-15", "2025-08-15", "2023-11-12", "2024-11-01", "2025-10-20"]
fest_days = set()
for f in FEST:
    for k in range(-2, 3):
        fest_days.add(pd.Timestamp(f) + pd.Timedelta(days=k))
d2 = daily.copy()
d2["festival"] = d2.index.isin(fest_days)
fe = d2.groupby("festival")[["units_demanded", "units_donated"]].mean().round(1)
fe.index = ["Normal days", "Festival days (+/-2)"]
log()
log("=" * 60)
log("7. FESTIVAL EFFECT (avg units/day, all hospitals)")
log("=" * 60)
log(fe.to_string())

exp_rate = 100 * ops.units_expired.sum() / (ops.units_donated.sum() + ops.units_procured.sum())
log()
log(f"Overall wastage rate (expired / collected+procured): {exp_rate:.2f}%")
log("NOTE: real RBC wastage is usually a few percent; this simulation is lower "
    "because stock turns over every 3-4 days. State this limitation in the report.")

(OUT_DIR / "blood_eda_summary.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"\nSaved {len(list(FIG_DIR.glob('eda_*.png')))} figures to {FIG_DIR}")
print(f"Saved summary to {OUT_DIR / 'blood_eda_summary.txt'}")
