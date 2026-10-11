"""
Module 3 — Blood Bank Intelligence: Threshold Sweep
----------------------------------------------------
Tries different COVER_LOW values (days of cover below which a row is LOW STOCK)
and reports how many rows get flagged, plus precision / recall / F1 against
actual stock-outs in the test period. Used to justify the chosen threshold.

Input  : outputs/blood_risk_backtest.csv   (made by blood_risk_backtest.py)
Output : outputs/blood_threshold_sweep.csv
         outputs/figures/risk_threshold_sweep.png

Run from the project root:   py scripts\\blood_threshold_sweep.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

COVER_SHORTAGE = 2.0
GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]

ev = pd.read_csv(OUT_DIR / "blood_risk_backtest.csv")
truth = ev["had_stockout"] == 1

rows = []
for c in GRID:
    shortage = (ev.cover < COVER_SHORTAGE) | (ev.projected < 0)
    low = (ev.cover < c) | (ev.stress < 0)
    flag = shortage | low
    tp = int((flag & truth).sum())
    fp = int((flag & ~truth).sum())
    fn = int((~flag & truth).sum())
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if (p + r) else float("nan")
    rows.append({"COVER_LOW": c, "flagged": int(flag.sum()),
                 "flagged_%": round(100 * flag.mean(), 1),
                 "precision": round(p, 3), "recall": round(r, 3), "F1": round(f, 3)})

res = pd.DataFrame(rows)
res.to_csv(OUT_DIR / "blood_threshold_sweep.csv", index=False)
print(res.to_string(index=False))

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].plot(res.recall, res.precision, marker="o", color="#1F618D")
for _, r_ in res.iterrows():
    ax[0].annotate(f"{r_.COVER_LOW:g}", (r_.recall, r_.precision), textcoords="offset points", xytext=(5, 5))
ax[0].set_xlabel("Recall (share of stock-outs flagged)")
ax[0].set_ylabel("Precision")
ax[0].set_title("Precision vs recall by COVER_LOW (days)")
ax[0].grid(alpha=0.25)
ax[1].plot(res.COVER_LOW, res["flagged_%"], marker="o", color="#C0392B")
ax[1].set_xlabel("COVER_LOW (days)")
ax[1].set_ylabel("Rows flagged (%)")
ax[1].set_title("Alert volume by COVER_LOW")
ax[1].grid(alpha=0.25)
fig.tight_layout()
fig.savefig(FIG_DIR / "risk_threshold_sweep.png")
print(f"\nSaved {OUT_DIR / 'blood_threshold_sweep.csv'} and the figure.")gg