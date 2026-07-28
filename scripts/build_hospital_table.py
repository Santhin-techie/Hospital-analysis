"""
Hospital Capability Table Builder
------------------------------------
Purpose: Build the hospital-side dataset that Modules 1, 3, and 4 all share.

Real parts   : hospital names + approximate real locations (public knowledge)
Simulated part: exact equipment/bed counts (not publicly available, so
                simulated but grounded in each hospital's known real
                specialty, e.g. MIOT is known for trauma/ortho -> trauma_tier=1)

Output: chennai_hospitals.csv
Columns: hospital_id, name, latitude, longitude, trauma_tier,
         has_icu, has_cath_lab, has_ventilator_bank, icu_beds, general_beds
"""

import csv

# ---------------------------------------------------------------------------
# Real, well-known Chennai hospitals with approximate real locations.
# trauma_tier: 1 = full trauma center, 2 = partial/general emergency, 3 = basic
# Capability flags are simulated (real internal capacity isn't public) but
# anchored to each hospital's known, publicly stated specialties.
# ---------------------------------------------------------------------------
HOSPITALS = [
    {"name": "Apollo Hospitals, Greams Road",      "lat": 13.0604, "lon": 80.2496,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 60, "general_beds": 500},
    {"name": "MIOT International, Manapakkam",     "lat": 13.0088, "lon": 80.1657,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 55, "general_beds": 1000},
    {"name": "Kauvery Hospital, Alwarpet",          "lat": 13.0343, "lon": 80.2545,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 40, "general_beds": 300},
    {"name": "Rajiv Gandhi Govt. General Hospital", "lat": 13.0878, "lon": 80.2785,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 70, "general_beds": 1600},
    {"name": "Stanley Medical College Hospital",    "lat": 13.1097, "lon": 80.2886,
     "trauma_tier": 2, "has_icu": True,  "has_cath_lab": False, "has_ventilator_bank": True,  "icu_beds": 30, "general_beds": 800},
    {"name": "Sri Ramachandra Medical Centre",      "lat": 13.0355, "lon": 80.1565,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 50, "general_beds": 1800},
    {"name": "Fortis Malar Hospital, Adyar",        "lat": 13.0067, "lon": 80.2570,
     "trauma_tier": 2, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": False, "icu_beds": 25, "general_beds": 200},
    {"name": "Tulips Multispeciality, OMR",         "lat": 12.9010, "lon": 80.2270,
     "trauma_tier": 3, "has_icu": True,  "has_cath_lab": False, "has_ventilator_bank": False, "icu_beds": 10, "general_beds": 80},
    {"name": "Chettinad Hospital, Kelambakkam",     "lat": 12.7965, "lon": 80.2210,
     "trauma_tier": 2, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 35, "general_beds": 700},
    {"name": "Government Hospital, Tambaram",       "lat": 12.9230, "lon": 80.1180,
     "trauma_tier": 2, "has_icu": True,  "has_cath_lab": False, "has_ventilator_bank": True,  "icu_beds": 20, "general_beds": 350},
    {"name": "Prashanth Hospitals, Chromepet",      "lat": 12.9500, "lon": 80.1420,
     "trauma_tier": 2, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": False, "icu_beds": 20, "general_beds": 150},
    {"name": "SIMS Hospital, Vadapalani",           "lat": 13.0500, "lon": 80.2130,
     "trauma_tier": 1, "has_icu": True,  "has_cath_lab": True,  "has_ventilator_bank": True,  "icu_beds": 45, "general_beds": 400},
]

rows = []
for i, h in enumerate(HOSPITALS, start=1):
    row = {"hospital_id": f"HOSP{i:02d}", **h}
    rows.append(row)

out_path = r"C:\Users\santhin kumar k\mini\data\simulated\chennai_hospitals.csv"
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "hospital_id", "name", "latitude", "longitude", "trauma_tier",
        "has_icu", "has_cath_lab", "has_ventilator_bank", "icu_beds", "general_beds"
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "hospital_id": r["hospital_id"], "name": r["name"],
            "latitude": r["lat"], "longitude": r["lon"],
            "trauma_tier": r["trauma_tier"], "has_icu": r["has_icu"],
            "has_cath_lab": r["has_cath_lab"], "has_ventilator_bank": r["has_ventilator_bank"],
            "icu_beds": r["icu_beds"], "general_beds": r["general_beds"],
        })

print(f"Saved {len(rows)} hospitals -> {out_path}")
for r in rows:
    print(f"  {r['hospital_id']}: {r['name']} (tier {r['trauma_tier']})")