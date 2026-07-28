"""
Simulated Chennai Accident Point Dataset Generator
----------------------------------------------------
Purpose : Public accident data in India is released only as yearly/district
          totals -- exact accident locations (lat/long) are not published.
          This script generates realistic point-level accident data by
          scattering simulated accidents around REAL, documented
          high-traffic / accident-prone Chennai junctions.

Calibration source (real data):
  Tamil Nadu Road Crashes 1993-2025 (data.opencity.in)
  2023 actuals: Fatal=17,526 | Grievous=23,686 | Minor=24,555 | Non-Injury=1,446
  -> severity ratios below are derived from this real yearly breakdown.

Output: chennai_simulated_accidents.csv
Columns: accident_id, latitude, longitude, date, severity, near_junction
"""

import random
import csv
from datetime import datetime, timedelta

random.seed(42)  # reproducible output

# ---------------------------------------------------------------------------
# 1. REAL, documented high-traffic / accident-prone Chennai junctions
#    (sourced from public references - Wikipedia / civic records)
# ---------------------------------------------------------------------------
JUNCTIONS = [
    {"name": "Kathipara Junction",       "lat": 13.00727, "lon": 80.20371, "weight": 1.3},
    {"name": "Retteri Junction",         "lat": 13.13024, "lon": 80.21379, "weight": 1.1},
    {"name": "Madhya Kailash Junction",  "lat": 13.00672, "lon": 80.24737, "weight": 1.0},
    {"name": "Perungudi (OMR)",          "lat": 12.96190, "lon": 80.24290, "weight": 1.4},  # IT corridor, high traffic
    {"name": "Tambaram (GST Road)",      "lat": 12.92490, "lon": 80.12700, "weight": 1.3},  # major NH stretch
    {"name": "Kelambakkam (ECR/OMR)",    "lat": 12.79000, "lon": 80.22000, "weight": 1.2},  # fast-growing, poor lighting
]

# ---------------------------------------------------------------------------
# 2. Real severity ratios, derived from actual 2023 Tamil Nadu totals
#    Fatal 17526 / Grievous 23686 / Minor 24555 / NonInjury 1446 = 67213 total
# ---------------------------------------------------------------------------
TOTAL_2023 = 17526 + 23686 + 24555 + 1446
SEVERITY_WEIGHTS = {
    "Fatal":      17526 / TOTAL_2023,
    "Grievous":   23686 / TOTAL_2023,
    "Minor":      24555 / TOTAL_2023,
    "NonInjury":   1446 / TOTAL_2023,
}
SEVERITIES = list(SEVERITY_WEIGHTS.keys())
SEVERITY_PROBS = list(SEVERITY_WEIGHTS.values())

# ---------------------------------------------------------------------------
# 3. Generation parameters
# ---------------------------------------------------------------------------
POINTS_PER_JUNCTION_BASE = 60     # base accident count per junction over 3 yrs
DATE_START = datetime(2023, 1, 1)
DATE_END   = datetime(2025, 12, 31)
SPREAD_DEG = 0.006                # ~600m scatter radius around each junction

def jittered_point(lat, lon, spread=SPREAD_DEG):
    """Scatter a point around a center, denser near the center (gaussian-like)."""
    dlat = random.gauss(0, spread / 2)
    dlon = random.gauss(0, spread / 2)
    return round(lat + dlat, 6), round(lon + dlon, 6)

def random_date():
    delta_days = (DATE_END - DATE_START).days
    return DATE_START + timedelta(days=random.randint(0, delta_days))

# ---------------------------------------------------------------------------
# 4. Generate rows
# ---------------------------------------------------------------------------
rows = []
accident_id = 1

for j in JUNCTIONS:
    n_points = int(POINTS_PER_JUNCTION_BASE * j["weight"])
    for _ in range(n_points):
        lat, lon = jittered_point(j["lat"], j["lon"])
        severity = random.choices(SEVERITIES, weights=SEVERITY_PROBS, k=1)[0]
        date = random_date().strftime("%Y-%m-%d")
        rows.append({
            "accident_id": f"ACC{accident_id:05d}",
            "latitude": lat,
            "longitude": lon,
            "date": date,
            "severity": severity,
            "near_junction": j["name"],
        })
        accident_id += 1

random.shuffle(rows)

# ---------------------------------------------------------------------------
# 5. Write CSV
# ---------------------------------------------------------------------------
out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_simulated_accidents.csv"
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "accident_id", "latitude", "longitude", "date", "severity", "near_junction"
    ])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} simulated accident records -> {out_path}")
print("\nSeverity distribution:")
for s in SEVERITIES:
    count = sum(1 for r in rows if r["severity"] == s)
    print(f"  {s:10s}: {count:4d}  ({count/len(rows)*100:.1f}%)")

print("\nRecords per junction:")
for j in JUNCTIONS:
    count = sum(1 for r in rows if r["near_junction"] == j["name"])
    print(f"  {j['name']:25s}: {count}")