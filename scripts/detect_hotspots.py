"""
Accident Hotspot Detection using DBSCAN
------------------------------------------
Input : chennai_simulated_accidents.csv (from generate_accident_data.py)
Output: chennai_hotspot_zones.csv
        -> one row per detected hotspot zone, with accident count,
           severity-weighted risk score, and zone centroid (for use
           in the travel-time routing step later).

How it works:
  1. Load accident points (lat/long).
  2. Run DBSCAN on the coordinates -> groups nearby points into "zones".
     Points that don't belong to any dense cluster are marked as noise (-1)
     and excluded from the hotspot list (isolated one-off accidents).
  3. For each zone: compute accident count, severity-weighted risk score,
     and the centroid (average lat/long) -> this centroid is what you'll
     feed into the routing step to find "nearest capable hospital".
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
df = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_simulated_accidents.csv")
print(f"Loaded {len(df)} accident records\n")

# ---------------------------------------------------------------------------
# 2. Severity weighting -- fatal accidents matter more than minor ones
#    when deciding how "risky" a zone is, not just how many accidents.
# ---------------------------------------------------------------------------
SEVERITY_SCORE = {
    "Fatal": 4,
    "Grievous": 3,
    "Minor": 1,
    "NonInjury": 0.5,
}
df["severity_score"] = df["severity"].map(SEVERITY_SCORE)

# ---------------------------------------------------------------------------
# 3. Run DBSCAN on coordinates
#    eps is in degrees -- ~0.005 deg is roughly 500m at this latitude.
#    min_samples = minimum accidents required to call something a "hotspot".
# ---------------------------------------------------------------------------
coords = df[["latitude", "longitude"]].values
db = DBSCAN(eps=0.005, min_samples=8).fit(coords)
df["zone_label"] = db.labels_

n_zones = len(set(df["zone_label"])) - (1 if -1 in df["zone_label"].values else 0)
n_noise = (df["zone_label"] == -1).sum()
print(f"Detected {n_zones} hotspot zone(s)")
print(f"{n_noise} isolated accident(s) not part of any hotspot (excluded)\n")

# ---------------------------------------------------------------------------
# 4. Summarize each zone
# ---------------------------------------------------------------------------
zones = []
for label, group in df[df["zone_label"] != -1].groupby("zone_label"):
    centroid_lat = group["latitude"].mean()
    centroid_lon = group["longitude"].mean()
    accident_count = len(group)
    risk_score = round(group["severity_score"].sum(), 1)
    fatal_count = (group["severity"] == "Fatal").sum()
    # most common real junction this zone formed around (for readability/QA)
    dominant_junction = group["near_junction"].mode()[0]

    zones.append({
        "zone_id": f"ZONE-{label+1:02d}",
        "centroid_lat": round(centroid_lat, 6),
        "centroid_lon": round(centroid_lon, 6),
        "accident_count": accident_count,
        "fatal_count": fatal_count,
        "risk_score": risk_score,
        "dominant_area": dominant_junction,
    })

zones_df = pd.DataFrame(zones).sort_values("risk_score", ascending=False).reset_index(drop=True)
zones_df["priority_rank"] = zones_df.index + 1

# ---------------------------------------------------------------------------
# 5. Save + print
# ---------------------------------------------------------------------------
out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hotspot_zones.csv"
zones_df.to_csv(out_path, index=False)

print("Hotspot zones (ranked by risk score):\n")
print(zones_df.to_string(index=False))
print(f"\nSaved -> {out_path}")