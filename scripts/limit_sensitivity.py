"""
Limit Sensitivity Check (Module 4)
-----------------------------------
The 20-minute limit is a planning choice, not a fixed fact. This script shows
how the result changes if the limit is stricter or looser, and what difference
it makes to judge zones at their WORST time of day instead of one snapshot.

Input : chennai_coverage_by_timeslot.csv   (from compute_travel_time.py)
        chennai_hotspot_zones.csv          (zone names)
Output: chennai_limit_sensitivity.csv      (one row per limit)
        chennai_zone_time_range.csv        (fastest / slowest time per zone)

No routing calls are made, so no API key is needed.

How to read it:
  gaps_at_worst_time   zones that are over the limit at their slowest time of day
  gaps_live_now_only   zones that would be called gaps if you had only measured
                       the single "now" snapshot (this is what the old method did)
"""

import os

import pandas as pd

LIMITS = [10, 15, 20, 25, 30, 40]
CURRENT_LIMIT = 20

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")

slots = pd.read_csv(os.path.join(DATA_DIR, "chennai_coverage_by_timeslot.csv"))
zones = pd.read_csv(os.path.join(DATA_DIR, "chennai_hotspot_zones.csv"))
area = zones.set_index("zone_id")["dominant_area"].to_dict()

valid = slots[slots["nearest_capable_min"].notna()]
per_zone = valid.groupby("zone_id")["nearest_capable_min"].agg(fastest="min", slowest="max")
now_only = valid[valid["slot"] == "now"].set_index("zone_id")["nearest_capable_min"]

# ---------------------------------------------------------------------------
# 1. How many gaps at each limit
# ---------------------------------------------------------------------------
rows = []
for limit in LIMITS:
    worst_gap_ids = per_zone.index[per_zone["slowest"] > limit].tolist()
    now_gap_ids = now_only.index[now_only > limit].tolist()
    rows.append({
        "limit_min": limit,
        "gaps_at_worst_time": len(worst_gap_ids),
        "gaps_live_now_only": len(now_gap_ids),
        "gap_zones_at_worst_time": "; ".join(area.get(z, z) for z in worst_gap_ids),
    })
sens = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# 2. Each zone's range across the day
# ---------------------------------------------------------------------------
rng = per_zone.reset_index()
rng["area"] = rng["zone_id"].map(area)
rng["swing_min"] = (rng["slowest"] - rng["fastest"]).round(1)
rng["gap_flips_with_time"] = (rng["fastest"] <= CURRENT_LIMIT) & (rng["slowest"] > CURRENT_LIMIT)
rng = rng[["zone_id", "area", "fastest", "slowest", "swing_min", "gap_flips_with_time"]]

sens.to_csv(os.path.join(DATA_DIR, "chennai_limit_sensitivity.csv"), index=False)
rng.to_csv(os.path.join(DATA_DIR, "chennai_zone_time_range.csv"), index=False)

# ---------------------------------------------------------------------------
# 3. Print
# ---------------------------------------------------------------------------
print("Gap zones at different limits:\n")
print(sens.to_string(index=False))

flip = rng[rng["gap_flips_with_time"]]
print(f"\nZones that are covered at some times of day and a gap at others (limit {CURRENT_LIMIT} min):")
if flip.empty:
    print("  none")
else:
    for _, r in flip.iterrows():
        print(f"  {r['area']}: {r['fastest']:.1f} min at best, {r['slowest']:.1f} min at worst")

cur = sens[sens["limit_min"] == CURRENT_LIMIT].iloc[0]
print(f"\nAt {CURRENT_LIMIT} min: {cur['gaps_at_worst_time']} gap(s) judged at the worst time of day, "
      f"versus {cur['gaps_live_now_only']} if only the live snapshot had been used.")
print("\nSaved -> chennai_limit_sensitivity.csv and chennai_zone_time_range.csv")