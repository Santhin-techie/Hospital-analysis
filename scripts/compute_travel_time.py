"""
Real Travel-Time Routing (Hotspot -> Nearest Capable Hospital)
-------------------------------------------------------------------
RUN THIS ON YOUR OWN LAPTOP -- IT NEEDS INTERNET.
(osmnx downloads live Chennai road-network data from OpenStreetMap.)

Input : chennai_hotspot_zones.csv   (from detect_hotspots.py)
        chennai_hospitals.csv       (from build_hospital_table.py)
Output: chennai_coverage_results.csv
        -> for each hotspot zone: nearest hospital overall (any capability)
           AND nearest hospital that meets a required capability
           (e.g. trauma_tier <= 2), with REAL road travel time in minutes.

Install first (one-time):
    pip install osmnx networkx pandas --break-system-packages

First run will be slow (~1-3 min) while it downloads Chennai's road graph.
It's cached locally after that (osmnx saves it), so later runs are fast.
"""

import pandas as pd  
import osmnx as ox
import networkx as nx

# ---------------------------------------------------------------------------
# 1. Load your zone + hospital data
# ---------------------------------------------------------------------------
zones = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hotspot_zones.csv")
hospitals = pd.read_csv(r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hospitals.csv")

print(f"Loaded {len(zones)} hotspot zones and {len(hospitals)} hospitals")

# ---------------------------------------------------------------------------
# 2. Download Chennai's drivable road network (cached after first run)
#    Bounding box covers the whole metro area including OMR/GST/ECR corridors.
# ---------------------------------------------------------------------------
print("Downloading Chennai road network (first run only takes a while)...")
G = ox.graph_from_place("Chennai, Tamil Nadu, India", network_type="drive")

# Add travel time to every road segment based on speed limits (osmnx helper)
G = ox.add_edge_speeds(G)      # assigns km/h to each road if missing
G = ox.add_edge_travel_times(G)  # computes travel_time (seconds) per edge

print("Road network ready.\n")

# ---------------------------------------------------------------------------
# 3. Helper: real travel time (minutes) between two lat/lon points
# ---------------------------------------------------------------------------
def real_travel_time_minutes(orig_lat, orig_lon, dest_lat, dest_lon):
    orig_node = ox.nearest_nodes(G, orig_lon, orig_lat)
    dest_node = ox.nearest_nodes(G, dest_lon, dest_lat)
    try:
        seconds = nx.shortest_path_length(G, orig_node, dest_node, weight="travel_time")
        return round(seconds / 60, 1)
    except nx.NetworkXNoPath:
        return None  # no route found (disconnected graph edge case)

# ---------------------------------------------------------------------------
# 4. For each zone: find (a) nearest hospital overall, (b) nearest hospital
#    that meets a minimum capability bar (trauma_tier 1 or 2, has_icu)
# ---------------------------------------------------------------------------
results = []
REQUIRED_MAX_TIER = 2       # "capable" = trauma tier 1 or 2
SAFE_WINDOW_MINUTES = 20    # your coverage threshold

for _, zone in zones.iterrows():
    best_any = {"time": float("inf")}
    best_capable = {"time": float("inf")}

    for _, hosp in hospitals.iterrows():
        t = real_travel_time_minutes(
            zone["centroid_lat"], zone["centroid_lon"],
            hosp["latitude"], hosp["longitude"]
        )
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
    })

results_df = pd.DataFrame(results).sort_values("risk_score", ascending=False)
out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_coverage_results.csv"
results_df.to_csv(out_path, index=False)

print(results_df.to_string(index=False))
print(f"\nSaved -> {out_path}")