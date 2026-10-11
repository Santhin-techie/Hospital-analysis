"""
Travel-Time Routing at Several Times of Day (Hotspot -> Nearest Capable Hospital)
-----------------------------------------------------------------------------------
A single traffic snapshot is not reliable: the same zone can look "covered" at
midday and be a "gap" in the evening peak. This script measures every
zone -> hospital route at five time points and judges each zone by its
WORST time of day.

Time points:
  now      live traffic at the moment you run the script
  morning  predicted traffic, next Tuesday 08:30
  midday   predicted traffic, next Tuesday 13:00
  evening  predicted traffic, next Tuesday 18:00
  night    predicted traffic, next Tuesday 23:00

The predicted slots use TomTom's departAt option (historical traffic patterns
for a future departure time), so one run covers the whole day.

THE API KEY IS NOT STORED IN THIS FILE. Set it once, then reopen PowerShell:
    setx TOMTOM_API_KEY "your-new-key-here"

Requests per run: zones x hospitals x 5 slots (6 x 12 x 5 = 360).
Free tier allows 2,500 per day.

Input : chennai_hotspot_zones.csv, chennai_hospitals.csv
Output: chennai_coverage_results_LIVE.csv
          one row per zone, judged at its WORST time of day. Same columns as
          before (so recommend_actions.py and the dashboard keep working) plus
          worst_slot, best_capable_min, slots_over_limit, slots_checked and
          one capable_min_<slot> column per time point.
        chennai_coverage_by_timeslot.csv
          every zone at every time point (for charts and the report).
"""

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# 0. CONFIG
# ---------------------------------------------------------------------------
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")
if not TOMTOM_API_KEY:
    raise SystemExit(
        "TOMTOM_API_KEY is not set.\n"
        "Run:  setx TOMTOM_API_KEY \"your-new-key-here\"\n"
        "Then close and reopen PowerShell and run this script again."
    )

REQUIRED_MAX_TIER = 2       # "capable" = trauma tier 1 or 2
SAFE_WINDOW_MINUTES = 20    # coverage limit
REQUEST_DELAY_SEC = 0.25    # stay within free-tier rate limits

IST = timezone(timedelta(hours=5, minutes=30))

def next_tuesday():
    """A typical working day, always in the future (TomTom rejects past times)."""
    d = datetime.now(IST).date() + timedelta(days=1)
    while d.weekday() != 1:          # 1 = Tuesday
        d += timedelta(days=1)
    return d

TUESDAY = next_tuesday()

# key, label shown in the dashboard, (hour, minute) or None for "live now"
SLOTS = [
    ("now",     "Now (live)",          None),
    ("morning", "Morning peak 08:30",  (8, 30)),
    ("midday",  "Midday 13:00",        (13, 0)),
    ("evening", "Evening peak 18:00",  (18, 0)),
    ("night",   "Night 23:00",         (23, 0)),
]

def depart_at(hm):
    return datetime(TUESDAY.year, TUESDAY.month, TUESDAY.day, hm[0], hm[1], tzinfo=IST).isoformat()

# ---------------------------------------------------------------------------
# 1. Load data (relative paths)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")

zones = pd.read_csv(os.path.join(DATA_DIR, "chennai_hotspot_zones.csv"))
hospitals = pd.read_csv(os.path.join(DATA_DIR, "chennai_hospitals.csv"))

total_calls = len(zones) * len(hospitals) * len(SLOTS)
print(f"Loaded {len(zones)} zones and {len(hospitals)} hospitals")
print(f"Time points: {', '.join(s[1] for s in SLOTS)}")
print(f"Predicted slots use Tuesday {TUESDAY}")
print(f"Routing calls this run: {total_calls} (free tier: 2,500/day)\n")

# ---------------------------------------------------------------------------
# 2. One routing call
# ---------------------------------------------------------------------------
_reported = set()

def travel_minutes(orig_lat, orig_lon, dest_lat, dest_lon, hm, slot_key):
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
           f"{orig_lat},{orig_lon}:{dest_lat},{dest_lon}/json")
    params = {"key": TOMTOM_API_KEY, "traffic": "true", "travelMode": "car"}
    if hm is not None:
        params["departAt"] = depart_at(hm)
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            # Show the API's own message once per slot (it never contains the key)
            if slot_key not in _reported:
                _reported.add(slot_key)
                print(f"  [warn] {slot_key}: HTTP {resp.status_code} - {resp.text[:200]}")
            return None
        seconds = resp.json()["routes"][0]["summary"]["travelTimeInSeconds"]
        return round(seconds / 60, 1)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        if slot_key not in _reported:
            _reported.add(slot_key)
            print(f"  [warn] {slot_key}: {type(e).__name__}")
        return None

# ---------------------------------------------------------------------------
# 3. Every zone x every hospital x every time point
# ---------------------------------------------------------------------------
run_timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
long_rows = []

for key, label, hm in SLOTS:
    print(f"--- {label} ---")
    for _, zone in zones.iterrows():
        best_any = {"time": float("inf")}
        best_capable = {"time": float("inf")}
        for _, hosp in hospitals.iterrows():
            t = travel_minutes(zone["centroid_lat"], zone["centroid_lon"],
                               hosp["latitude"], hosp["longitude"], hm, key)
            time.sleep(REQUEST_DELAY_SEC)
            if t is None:
                continue
            if t < best_any["time"]:
                best_any = {"time": t, "hospital": hosp["name"]}
            if hosp["trauma_tier"] <= REQUIRED_MAX_TIER and t < best_capable["time"]:
                best_capable = {"time": t, "hospital": hosp["name"]}

        have = best_capable["time"] != float("inf")
        long_rows.append({
            "zone_id": zone["zone_id"], "slot": key, "slot_label": label,
            "nearest_hospital_any": best_any.get("hospital"),
            "nearest_hospital_any_min": best_any["time"] if best_any["time"] != float("inf") else None,
            "nearest_capable_hospital": best_capable.get("hospital"),
            "nearest_capable_min": best_capable["time"] if have else None,
            "coverage_status": ("COVERED" if best_capable["time"] <= SAFE_WINDOW_MINUTES else "GAP"),
        })
        shown = f"{best_capable['time']} min" if have else "no data"
        print(f"  {zone['zone_id']}: {shown}")

long_df = pd.DataFrame(long_rows)
if long_df["nearest_capable_min"].notna().sum() == 0:
    raise SystemExit("No routing results came back. Check the key, and that Routing API is ticked for it.")

# ---------------------------------------------------------------------------
# 4. One row per zone, judged at its WORST time of day
# ---------------------------------------------------------------------------
final_rows = []
for _, zone in zones.iterrows():
    zdf = long_df[long_df["zone_id"] == zone["zone_id"]]
    valid = zdf[zdf["nearest_capable_min"].notna()]
    row = {"zone_id": zone["zone_id"], "risk_score": zone["risk_score"]}

    if valid.empty:
        row.update({"nearest_hospital_any": None, "nearest_hospital_any_min": None,
                    "nearest_capable_hospital": None, "nearest_capable_min": None,
                    "hidden_delay_min": None, "coverage_status": "GAP",
                    "data_pulled_at": run_timestamp, "worst_slot": None,
                    "best_capable_min": None, "slots_over_limit": 0, "slots_checked": 0})
    else:
        w = valid.loc[valid["nearest_capable_min"].idxmax()]
        any_min = w["nearest_hospital_any_min"]
        row.update({
            "nearest_hospital_any": w["nearest_hospital_any"],
            "nearest_hospital_any_min": any_min,
            "nearest_capable_hospital": w["nearest_capable_hospital"],
            "nearest_capable_min": w["nearest_capable_min"],
            "hidden_delay_min": round(w["nearest_capable_min"] - any_min, 1) if pd.notna(any_min) else None,
            "coverage_status": "COVERED" if w["nearest_capable_min"] <= SAFE_WINDOW_MINUTES else "GAP",
            "data_pulled_at": run_timestamp,
            "worst_slot": w["slot_label"],
            "best_capable_min": valid["nearest_capable_min"].min(),
            "slots_over_limit": int((valid["nearest_capable_min"] > SAFE_WINDOW_MINUTES).sum()),
            "slots_checked": int(len(valid)),
        })

    for key, _, _ in SLOTS:
        m = zdf[zdf["slot"] == key]["nearest_capable_min"]
        row[f"capable_min_{key}"] = m.iloc[0] if len(m) and pd.notna(m.iloc[0]) else None
    final_rows.append(row)

final_df = pd.DataFrame(final_rows).sort_values("risk_score", ascending=False)

out_live = os.path.join(DATA_DIR, "chennai_coverage_results_LIVE.csv")
out_slots = os.path.join(DATA_DIR, "chennai_coverage_by_timeslot.csv")
final_df.to_csv(out_live, index=False)
long_df.to_csv(out_slots, index=False)

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
print("\nTravel time to the nearest capable hospital (minutes):\n")
cols = ["zone_id"] + [f"capable_min_{k}" for k, _, _ in SLOTS] + ["worst_slot", "coverage_status"]
print(final_df[cols].to_string(index=False))
print(f"\nA zone is a GAP if it is over {SAFE_WINDOW_MINUTES} min at its worst time of day.")
print(f"Saved -> {out_live}")
print(f"Saved -> {out_slots}")