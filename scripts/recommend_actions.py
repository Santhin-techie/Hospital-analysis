"""
Recommend Fixes for Coverage Gaps (Module 4, final analysis step)
-------------------------------------------------------------------
Input : chennai_coverage_results_LIVE.csv   (from compute_travel_time.py)
        chennai_hotspot_zones.csv           (zone names + coordinates)
        chennai_hospitals.csv               (trauma tiers)
Output: chennai_recommendations.csv         (one row per zone)

For every GAP zone, two fixes are tested:

  FIX A - UPGRADE: the nearest hospital (any tier) is upgraded to tier 2.
          Uses the live travel time you already measured, so no new API calls.
          Applies only if that hospital is currently tier 3 and closer than
          the nearest capable one.

  FIX B - AMBULANCE / STABILISATION POST: a post placed near the zone.
          This shortens time to FIRST trauma care, not time to hospital.
          POST_FIRST_CARE_MIN is an ASSUMPTION -- state it in your report.

Rule: if Fix A alone brings the zone under the safe window -> UPGRADE.
      If Fix A helps but not enough -> UPGRADE + POST.
      If no hospital upgrade helps -> POST + NEW FACILITY NEEDED.
"""

import os
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SAFE_WINDOW_MINUTES = 20
REQUIRED_MAX_TIER = 2
POST_FIRST_CARE_MIN = 8   # ASSUMPTION: ambulance post reaches the scene/patient in ~8 min

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")

cov = pd.read_csv(os.path.join(DATA_DIR, "chennai_coverage_results_LIVE.csv"))
zones = pd.read_csv(os.path.join(DATA_DIR, "chennai_hotspot_zones.csv"))
hosp = pd.read_csv(os.path.join(DATA_DIR, "chennai_hospitals.csv"))

tier_of = hosp.set_index("name")["trauma_tier"].to_dict()
area_of = zones.set_index("zone_id")["dominant_area"].to_dict()

# ---------------------------------------------------------------------------
# BUILD ONE RECOMMENDATION PER ZONE
# ---------------------------------------------------------------------------
rows = []
for _, z in cov.sort_values("risk_score", ascending=False).iterrows():
    base = {
        "zone_id": z["zone_id"],
        "area": area_of.get(z["zone_id"], ""),
        "risk_score": z["risk_score"],
        "current_status": z["coverage_status"],
        "current_capable_hospital": z["nearest_capable_hospital"],
        "current_min": z["nearest_capable_min"],
    }

    # Zones already covered: no action
    if z["coverage_status"] == "COVERED":
        rows.append({**base,
                     "upgrade_candidate": "", "upgrade_min": "",
                     "post_first_care_min": "",
                     "recommended_action": "No action needed",
                     "projected_definitive_min": z["nearest_capable_min"],
                     "projected_status": "COVERED",
                     "minutes_saved": 0.0})
        continue

    # Fix A: is the nearest hospital (any tier) a lower-tier one worth upgrading?
    any_name = z["nearest_hospital_any"]
    any_min = z["nearest_hospital_any_min"]
    can_upgrade = (tier_of.get(any_name, 1) > REQUIRED_MAX_TIER
                   and any_min < z["nearest_capable_min"])

    if can_upgrade and any_min <= SAFE_WINDOW_MINUTES:
        action = f"Upgrade {any_name} to trauma tier 2"
        projected, status = any_min, "COVERED"
        post = ""
    elif can_upgrade:
        action = (f"Upgrade {any_name} to trauma tier 2 "
                  f"+ ambulance post near {area_of.get(z['zone_id'], 'zone')}")
        projected, status = any_min, "IMPROVED"
        post = POST_FIRST_CARE_MIN
    else:
        action = (f"Ambulance post near {area_of.get(z['zone_id'], 'zone')} "
                  f"+ new trauma-capable facility needed")
        projected, status = z["nearest_capable_min"], "GAP (needs new facility)"
        post = POST_FIRST_CARE_MIN

    rows.append({**base,
                 "upgrade_candidate": any_name if can_upgrade else "",
                 "upgrade_min": any_min if can_upgrade else "",
                 "post_first_care_min": post,
                 "recommended_action": action,
                 "projected_definitive_min": projected,
                 "projected_status": status,
                 "minutes_saved": round(z["nearest_capable_min"] - projected, 1)})

out = pd.DataFrame(rows)
# gaps first, then by risk
out["_gap"] = (out["current_status"] != "GAP").astype(int)
out = out.sort_values(["_gap", "risk_score"], ascending=[True, False]).drop(columns="_gap")
out.insert(0, "priority", range(1, len(out) + 1))

out_path = os.path.join(DATA_DIR, "chennai_recommendations.csv")
out.to_csv(out_path, index=False)

# ---------------------------------------------------------------------------
# PRINT SUMMARY
# ---------------------------------------------------------------------------
print("Recommendations (gaps first):\n")
print(out[["priority", "zone_id", "area", "current_status", "current_min",
           "recommended_action", "projected_definitive_min",
           "projected_status"]].to_string(index=False))
print(f"\nPost first-care time ({POST_FIRST_CARE_MIN} min) is an ASSUMPTION.")
print(f"Saved -> {out_path}")