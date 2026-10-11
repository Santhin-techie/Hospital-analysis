from pathlib import Path
from datetime import datetime
import pandas as pd
import random


# ============================================================
# 1. PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INITIAL_FILE = (
    BASE_DIR
    / "outputs"
    / "latest_department_availability.csv"
)

LIVE_FILE = (
    BASE_DIR
    / "outputs"
    / "simulated_live_availability.csv"
)

HOSPITAL_LIVE_FILE = (
    BASE_DIR
    / "outputs"
    / "simulated_live_hospital_summary.csv"
)


# ============================================================
# 2. LOAD CURRENT SIMULATION STATE
# ============================================================

# If simulated data already exists, continue from that state.
# Otherwise start from the latest department availability.

if LIVE_FILE.exists():

    df = pd.read_csv(LIVE_FILE)

    print("Continuing from previous simulated state.")

else:

    df = pd.read_csv(INITIAL_FILE)

    print("Starting new simulated state.")


print("Department rows:", len(df))


# ============================================================
# 3. PRESERVE LAST ACTUAL EVENT
# ============================================================

# Create the event column only when starting for the first time.
# Existing departments keep their previous actual event.
if "simulated_event" not in df.columns:
    df["simulated_event"] = "NO EVENT YET"


# ============================================================
# 4. CHOOSE 2–5 DEPARTMENTS FOR NEW EVENTS
# ============================================================

number_of_events = random.randint(6, 10)

number_of_events = min(
    number_of_events,
    len(df)
)

selected_indices = random.sample(
    list(df.index),
    number_of_events
)


# ============================================================
# 5. SIMULATE ADMISSIONS / DISCHARGES
# ============================================================

for index in selected_indices:

    capacity = int(
        df.at[index, "department_bed_capacity"]
    )

    occupied = int(
        df.at[index, "occupied_beds"]
    )

    # Choose either admission or discharge
    event = random.choice(
        ["ADMISSION", "DISCHARGE"]
    )

    # ----------------------------------------
    # ADMISSION
    # ----------------------------------------

    if event == "ADMISSION":

        if occupied < capacity:

            df.at[index, "occupied_beds"] = (
                occupied + 1
            )

            df.at[
                index,
                "simulated_event"
            ] = "ADMISSION"

        else:

            df.at[
                index,
                "simulated_event"
            ] = "NO CHANGE - FULL"

    # ----------------------------------------
    # DISCHARGE
    # ----------------------------------------

    elif event == "DISCHARGE":

        if occupied > 0:

            df.at[index, "occupied_beds"] = (
                occupied - 1
            )

            df.at[
                index,
                "simulated_event"
            ] = "DISCHARGE"

        else:

            df.at[
                index,
                "simulated_event"
            ] = "NO CHANGE - EMPTY"


# ============================================================
# 6. RECALCULATE AVAILABLE BEDS
# ============================================================

df["available_beds"] = (
    df["department_bed_capacity"]
    - df["occupied_beds"]
)


# ============================================================
# 7. RECALCULATE OCCUPANCY
# ============================================================

df["current_occupancy_pct"] = (
    df["occupied_beds"]
    / df["department_bed_capacity"]
    * 100
).round(2)


# ============================================================
# 8. VACANCY STATUS
# ============================================================

df["vacancy_status"] = df[
    "available_beds"
].apply(
    lambda beds:
    "AVAILABLE" if beds > 0 else "FULL"
)


# ============================================================
# 9. UPDATE TIMESTAMP
# ============================================================

current_time = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

df["simulation_timestamp"] = current_time


# ============================================================
# SAFE / ATOMIC FILE SAVE
# ============================================================

TEMP_LIVE_FILE = LIVE_FILE.with_name(
    "simulated_live_availability_temp.csv"
)

# Write the complete dataframe to a temporary file first
df.to_csv(
    TEMP_LIVE_FILE,
    index=False
)

# Only after writing is complete,
# replace the previous live file
TEMP_LIVE_FILE.replace(LIVE_FILE)


# ============================================================
# 11. CREATE HOSPITAL SUMMARY
# ============================================================

hospital_summary = (
    df.groupby(
        "hospital_name_department"
    )
    .agg(
        total_capacity=(
            "department_bed_capacity",
            "sum"
        ),
        total_occupied=(
            "occupied_beds",
            "sum"
        ),
        total_available=(
            "available_beds",
            "sum"
        )
    )
    .reset_index()
)


hospital_summary[
    "current_occupancy_pct"
] = (
    hospital_summary["total_occupied"]
    / hospital_summary["total_capacity"]
    * 100
).round(2)


hospital_summary[
    "vacancy_status"
] = hospital_summary[
    "total_available"
].apply(
    lambda beds:
    "AVAILABLE" if beds > 0 else "FULL"
)


hospital_summary = (
    hospital_summary
    .sort_values(
        "current_occupancy_pct",
        ascending=False
    )
    .reset_index(drop=True)
)


hospital_summary[
    "simulation_timestamp"
] = current_time


TEMP_HOSPITAL_FILE = HOSPITAL_LIVE_FILE.with_name(
    "simulated_live_hospital_summary_temp.csv"
)

hospital_summary.to_csv(
    TEMP_HOSPITAL_FILE,
    index=False
)

TEMP_HOSPITAL_FILE.replace(
    HOSPITAL_LIVE_FILE
)

TEMP_LIVE_FILE = LIVE_FILE.with_name(
    "simulated_live_availability_temp.csv"
)

df.to_csv(
    TEMP_LIVE_FILE,
    index=False
)

TEMP_LIVE_FILE.replace(
    LIVE_FILE
)


# ============================================================
# 12. DISPLAY THIS CYCLE'S EVENTS
# ============================================================

changed_rows = df.loc[
    selected_indices,
    [
        "hospital_name_department",
        "department",
        "department_bed_capacity",
        "occupied_beds",
        "available_beds",
        "simulated_event",
    ]
]


print("\n" + "=" * 70)
print("SIMULATED LIVE UPDATE")
print("=" * 70)

print(
    "Update time:",
    current_time
)

print(
    "Departments selected:",
    number_of_events
)

print("\nEvents this cycle:")

print(
    changed_rows.to_string(
        index=False
    )
)


# ============================================================
# 13. SYSTEM SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("CURRENT SYSTEM SUMMARY")
print("=" * 70)

print(
    "Hospitals:",
    len(hospital_summary)
)

print(
    "Total beds:",
    int(
        hospital_summary[
            "total_capacity"
        ].sum()
    )
)

print(
    "Occupied beds:",
    int(
        hospital_summary[
            "total_occupied"
        ].sum()
    )
)

print(
    "Available beds:",
    int(
        hospital_summary[
            "total_available"
        ].sum()
    )
)

print("\nSimulation update completed successfully.")