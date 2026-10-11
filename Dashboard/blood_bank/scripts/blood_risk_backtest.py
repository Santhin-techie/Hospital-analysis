"""
Module 3 — Blood Bank Intelligence: Risk Engine Backtest
---------------------------------------------------------
Question: when the risk logic flags a hospital x blood group for the next 7 days,
does unmet demand actually happen?

Uses the 26 weekly forecast origins in the test period (2025 H2) that
blood_forecast.py already produced (outputs/blood_horizon7_predictions.csv),
plus the stock on each origin date from blood_daily_operations.csv.
Everything on the origin date uses only information available at that date.

Simplified status logic (no batch ledger exists for past dates, so no FIFO):
  projected  = stock + forecast donations - forecast demand
  stress     = stock + forecast donations - 7-day P90 demand
  SHORTAGE RISK : cover < 2 days or projected < 0
  LOW STOCK     : cover < COVER_LOW or stress < 0
  STABLE        : otherwise
Outcome: actual unmet units over the next 7 days (units_unmet in the simulation).
NOTE: the simulation DOES procure from the regional centre, the flags do not
count procurement, so some "false alarms" are rescued by procurement. Say so.

Run from the project root:   py scripts\\blood_risk_backtest.py
Outputs: outputs/blood_risk_backtest.csv, outputs/blood_risk_backtest_summary.txt
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"

COVER_SHORTAGE = 2.0
COVER_LOW = 3.0       # keep equal to COVER_LOW in blood_risk_engine.py

ev = pd.read_csv(OUT_DIR / "blood_horizon7_predictions.csv", parse_dates=["origin"])
ops = pd.read_csv(SIM_DIR / "blood_daily_operations.csv", parse_dates=["date"])
ops = ops.sort_values(["hospital_id", "blood_group", "date"])

stock = ops.set_index(["date", "hospital_id", "blood_group"])["closing_stock"]
ev["stock"] = [stock.get((o, h, g), np.nan)
               for o, h, g in zip(ev.origin, ev.hospital_id, ev.blood_group)]

# actual unmet in the 7 days after each origin
ops["key"] = list(zip(ops.hospital_id, ops.blood_group))
unmet = {k: s.set_index("date")["units_unmet"] for k, s in ops.groupby("key")}
ev["actual_unmet_7d"] = [
    unmet[(h, g)].loc[o + pd.Timedelta(days=1): o + pd.Timedelta(days=7)].sum()
    for o, h, g in zip(ev.origin, ev.hospital_id, ev.blood_group)]
ev["had_stockout"] = (ev.actual_unmet_7d > 0).astype(int)

avg_dem = ev.boost_dem_7d / 7
ev["cover"] = np.where(avg_dem > 0, ev.stock / avg_dem.where(avg_dem > 0, 1), 99.0)
ev["projected"] = ev.stock + ev.boost_don_7d - ev.boost_dem_7d
ev["stress"] = ev.stock + ev.boost_don_7d - ev.upper90_dem_7d

ev["status"] = np.where((ev.cover < COVER_SHORTAGE) | (ev.projected < 0), "SHORTAGE RISK",
                np.where((ev.cover < COVER_LOW) | (ev.stress < 0), "LOW STOCK", "STABLE"))
# baseline: a plain days-of-cover rule with no forecast
ev["baseline_flag"] = (ev.stock / ev.prevweek_dem_7d.div(7).replace(0, np.nan) < COVER_LOW).fillna(False)
ev["flag"] = ev.status != "STABLE"


def prf(flag, truth):
    tp = int((flag & (truth == 1)).sum())
    fp = int((flag & (truth == 0)).sum())
    fn = int((~flag & (truth == 1)).sum())
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if p and r else np.nan
    return p, r, f


lines = [f"Backtest: {ev.origin.nunique()} weekly origins x {ev[['hospital_id','blood_group']].drop_duplicates().shape[0]} "
         f"hospital-groups = {len(ev)} cases",
         f"Share of cases with any unmet demand in next 7 days: {100 * ev.had_stockout.mean():.1f}%", ""]

by = (ev.groupby("status")
        .agg(cases=("status", "size"), pct_with_stockout=("had_stockout", lambda s: 100 * s.mean()),
             avg_unmet_units=("actual_unmet_7d", "mean"))
        .reindex(["SHORTAGE RISK", "LOW STOCK", "STABLE"]).round(2))
lines += ["Outcome by predicted status (a good engine: SHORTAGE > LOW > STABLE):", by.to_string(), ""]

res = []
for name, flag in [("Risk engine (SHORTAGE or LOW)", ev.flag),
                   ("Risk engine (SHORTAGE only)", ev.status == "SHORTAGE RISK"),
                   ("Baseline: cover rule only", ev.baseline_flag.astype(bool))]:
    p, r, f = prf(flag, ev.had_stockout)
    res.append((name, int(flag.sum()), round(p, 3), round(r, 3), round(f, 3)))
lines += ["Flag quality vs actual stock-outs:",
          pd.DataFrame(res, columns=["rule", "flagged", "precision", "recall", "F1"]).to_string(index=False), ""]

grp = (ev.groupby("blood_group")
         .apply(lambda d: pd.Series({"cases": len(d), "stockout_%": 100 * d.had_stockout.mean(),
                                     "flagged_%": 100 * d.flag.mean(),
                                     "recall_%": 100 * (d.flag & (d.had_stockout == 1)).sum()
                                                 / max(d.had_stockout.sum(), 1)}))
         .round(1))
lines += ["By blood group:", grp.to_string()]

ev.to_csv(OUT_DIR / "blood_risk_backtest.csv", index=False, float_format="%.3f")
text = "\n".join(lines)
(OUT_DIR / "blood_risk_backtest_summary.txt").write_text(text, encoding="utf-8")
print(text)
