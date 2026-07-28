"""
Approximate Travel-Time Coverage (FALLBACK, no internet needed)
--------------------------------------------------------------------
Use this to get working numbers TODAY. It is NOT real road routing --
it estimates travel time using straight-line distance x a traffic
multiplier calibrated to typical Chennai city-driving speeds.

Once you run compute_travel_time.py (the real osmnx version) on your
own laptop with internet, replace these numbers with the real ones --
the real version will be more accurate and is what your report should
ultimately cite as your methodology.

Input : chennai_hotspot_zones.csv, chennai_hospitals.csv
Output: chennai_coverage_results_APPROX.csv
"""

import pandas as pd
from math import radians, sin, cos, sqrt, atan2

zones = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hotspot_zones.csv")
hospitals = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hospitals.csv")

# ---------------------------------------------------------------------------
# Haversine straight-line distance (km)
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# ---------------------------------------------------------------------------
# Approximate travel time: assumes ~22 km/h effective city-traffic speed,
# plus a 1.4x "road isn't a straight line" detour factor.
# This is a rough stand-in ONLY -- real routing accounts for actual roads,
# one-ways, traffic signals, and congestion, which is why Step 4's real
# version will likely show LARGER gaps than this approximation.
# ---------------------------------------------------------------------------
AVG_SPEED_KMH = 22
DETOUR_FACTOR = 1.4

def approx_minutes(lat1, lon1, lat2, lon2):
    dist_km = haversine_km(lat1, lon1, lat2, lon2) * DETOUR_FACTOR
    return round((dist_km / AVG_SPEED_KMH) * 60, 1)

REQUIRED_MAX_TIER = 2
SAFE_WINDOW_MINUTES = 20

results = []
for _, zone in zones.iterrows():
    best_any = {"time": float("inf")}
    best_capable = {"time": float("inf")}

    for _, hosp in hospitals.iterrows():
        t = approx_minutes(zone["centroid_lat"], zone["centroid_lon"],
                            hosp["latitude"], hosp["longitude"])
        if t < best_any["time"]:
            best_any = {"time": t, "hospital": hosp["name"]}
        if hosp["trauma_tier"] <= REQUIRED_MAX_TIER and t < best_capable["time"]:
            best_capable = {"time": t, "hospital": hosp["name"]}

    covered = best_capable["time"] <= SAFE_WINDOW_MINUTES
    results.append({
        "zone_id": zone["zone_id"],
        "dominant_area": zone["dominant_area"],
        "risk_score": zone["risk_score"],
        "nearest_hospital_any": best_any["hospital"],
        "nearest_any_min_APPROX": best_any["time"],
        "nearest_capable_hospital": best_capable["hospital"],
        "nearest_capable_min_APPROX": best_capable["time"],
        "coverage_status": "COVERED" if covered else "GAP",
    })

results_df = pd.DataFrame(results).sort_values("risk_score", ascending=False)
out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_coverage_results_APPROX.csv"
results_df.to_csv(out_path, index=False)

print("*** APPROXIMATE results (straight-line x traffic factor) ***")
print("*** Replace with real osmnx routing before final submission ***\n")
print(results_df.to_string(index=False))
print(f"\nSaved -> {out_path}")