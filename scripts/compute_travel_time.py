"""
LIVE Travel-Time Routing (Hotspot -> Nearest Capable Hospital)
-------------------------------------------------------------------
RUN THIS ON YOUR OWN LAPTOP -- IT NEEDS INTERNET.

Unlike compute_travel_time.py (static OSM road graph, no real-time
traffic), this version calls the TomTom Routing API for EVERY
zone->hospital pair, with traffic=true. That means the travel time
reflects actual current congestion at the moment you run the script --
this is genuinely "live," not a cached snapshot.

Get a free API key (no credit card needed):
    https://developer.tomtom.com/  -> Register -> create a key
    Free tier: 2,500 requests/day, which is plenty for
    (num_zones x num_hospitals) calls per run.

Install first (one-time):
    pip install requests pandas --break-system-packages

Input : chennai_hotspot_zones.csv   (from detect_hotspots.py)
        chennai_hospitals.csv       (from build_hospital_table.py)
Output: chennai_coverage_results_LIVE.csv
        -> for each hotspot zone: nearest hospital overall (any capability)
           AND nearest hospital that meets a required capability
           (e.g. trauma_tier <= 2), with LIVE traffic-aware travel
           time in minutes, plus the timestamp the data was pulled.
"""

import time
from datetime import datetime

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# 0. CONFIG -- put your TomTom API key here
# ---------------------------------------------------------------------------
TOMTOM_API_KEY = "JFxdWes04WdBXCLFA9JgkbGz7CyUtcZD"

REQUIRED_MAX_TIER = 2       # "capable" = trauma tier 1 or 2
SAFE_WINDOW_MINUTES = 20    # your coverage threshold
REQUEST_DELAY_SEC = 0.25    # be polite to the free tier / avoid rate limits

# ---------------------------------------------------------------------------
# 1. Load your zone + hospital data
# ---------------------------------------------------------------------------
zones = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hotspot_zones.csv")
hospitals = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hospitals.csv")

print(f"Loaded {len(zones)} hotspot zones and {len(hospitals)} hospitals")
print(f"Total live routing calls needed this run: {len(zones) * len(hospitals)}\n")

if TOMTOM_API_KEY == "PUT_YOUR_KEY_HERE":
    raise SystemExit(
        "Set TOMTOM_API_KEY at the top of this script before running.\n"
        "Get a free key at https://developer.tomtom.com/"
    )

# ---------------------------------------------------------------------------
# 2. Helper: live traffic-aware travel time (minutes) between two points
# ---------------------------------------------------------------------------
def live_travel_time_minutes(orig_lat, orig_lon, dest_lat, dest_lon):
    """
    Calls TomTom's Routing API with traffic=true, so the returned
    travelTimeInSeconds already accounts for current live congestion,
    not just speed limits.
    """
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{orig_lat},{orig_lon}:{dest_lat},{dest_lon}/json"
    )
    params = {
        "key": TOMTOM_API_KEY,
        "traffic": "true",
        "travelMode": "car",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        seconds = data["routes"][0]["summary"]["travelTimeInSeconds"]
        return round(seconds / 60, 1)
    except (requests.RequestException, KeyError, IndexError) as e:
        print(f"  [warn] routing failed for ({orig_lat},{orig_lon}) -> "
              f"({dest_lat},{dest_lon}): {e}")
        return None

# ---------------------------------------------------------------------------
# 3. For each zone: find (a) nearest hospital overall, (b) nearest hospital
#    that meets a minimum capability bar (trauma_tier 1 or 2)
#    -- using LIVE traffic conditions at the moment this script runs.
# ---------------------------------------------------------------------------
run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
results = []
calls_made = 0

for _, zone in zones.iterrows():
    best_any = {"time": float("inf")}
    best_capable = {"time": float("inf")}

    for _, hosp in hospitals.iterrows():
        t = live_travel_time_minutes(
            zone["centroid_lat"], zone["centroid_lon"],
            hosp["latitude"], hosp["longitude"]
        )
        calls_made += 1
        time.sleep(REQUEST_DELAY_SEC)

        if t is None:
            continue

        if t < best_any["time"]:
            best_any = {"time": t, "hospital": hosp["name"], "id": hosp["hospital_id"]}

        if hosp["trauma_tier"] <= REQUIRED_MAX_TIER and t < best_capable["time"]:
            best_capable = {"time": t, "hospital": hosp["name"], "id": hosp["hospital_id"]}

    covered = best_capable["time"] <= SAFE_WINDOW_MINUTES

    results.append({
        "zone_id": zone["zone_id"],
        "risk_score": zone["risk_score"],
        "nearest_hospital_any": best_any.get("hospital"),
        "nearest_hospital_any_min": best_any["time"],
        "nearest_capable_hospital": best_capable.get("hospital"),
        "nearest_capable_min": best_capable["time"],
        "hidden_delay_min": round(best_capable["time"] - best_any["time"], 1),
        "coverage_status": "COVERED" if covered else "GAP",
        "data_pulled_at": run_timestamp,
    })

    print(f"  {zone['zone_id']}: nearest capable = {best_capable.get('hospital')} "
          f"({best_capable['time']} min, live traffic)")

results_df = pd.DataFrame(results).sort_values("risk_score", ascending=False)
out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_coverage_results_LIVE.csv"
results_df.to_csv(out_path, index=False)

print(f"\nMade {calls_made} live routing calls (free tier limit: 2,500/day)")
print(results_df.to_string(index=False))
print(f"\nSaved -> {out_path}")
print(f"Data reflects live traffic conditions as of {run_timestamp}")