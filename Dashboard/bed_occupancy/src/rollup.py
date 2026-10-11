from pathlib import Path
import pandas as pd


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "dept_forecast_results.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "hospital_risk_rollup.csv"
)


# ============================================================
# 2. LOAD DEPARTMENT FORECAST RESULTS
# ============================================================

df = pd.read_csv(INPUT_FILE)

df["date"] = pd.to_datetime(df["date"])

print("Department forecast results loaded successfully.")
print("Shape:", df.shape)


# ============================================================
# 3. KEEP THE LATEST DATE
# ============================================================

# For the operational hospital summary we want the
# latest available prediction for each department.

latest_date = df["date"].max()

latest_df = df[
    df["date"] == latest_date
].copy()

print("\nLatest forecast date:", latest_date.date())
print("Rows on latest date:", len(latest_df))


# ============================================================
# 4. DEPARTMENT-LEVEL AVAILABILITY
# ============================================================

# Current vacancy status based on available beds.

latest_df["vacancy_status"] = (
    latest_df["available_beds"] > 0
).map({
    True: "AVAILABLE",
    False: "FULL"
})


# ============================================================
# 5. FORECAST RISK LEVEL
# ============================================================

def assign_risk(probability):

    if probability >= 0.70:
        return "HIGH"

    elif probability >= 0.40:
        return "MEDIUM"

    else:
        return "LOW"


latest_df["forecast_risk_level"] = (
    latest_df["breach_probability"]
    .apply(assign_risk)
)


# ============================================================
# 6. FIND HIGHEST-RISK DEPARTMENT
# ============================================================

risk_index = (
    latest_df
    .groupby("hospital_id")["breach_probability"]
    .idxmax()
)

highest_risk_dept = (
    latest_df.loc[
        risk_index,
        [
            "hospital_id",
            "department",
            "breach_probability",
            "predicted_occupancy_7d"
        ]
    ]
    .rename(
        columns={
            "department":
                "highest_risk_department",

            "breach_probability":
                "max_breach_probability",

            "predicted_occupancy_7d":
                "highest_risk_predicted_occupancy"
        }
    )
)


# ============================================================
# 7. HOSPITAL-LEVEL CAPACITY SUMMARY
# ============================================================

hospital_summary = (
    latest_df
    .groupby(
        [
            "hospital_id",
            "hospital_name_department"
        ],
        as_index=False
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
        ),

        departments_with_vacancy=(
            "available_beds",
            lambda x: (x > 0).sum()
        ),

        departments_at_risk=(
            "predicted_breach_7d",
            "sum"
        )
    )
)


# ============================================================
# 8. ADD HIGHEST-RISK DEPARTMENT INFORMATION
# ============================================================

hospital_summary = hospital_summary.merge(
    highest_risk_dept,
    on="hospital_id",
    how="left"
)


# ============================================================
# 9. HOSPITAL OCCUPANCY
# ============================================================

hospital_summary[
    "current_occupancy_pct"
] = (

    hospital_summary["total_occupied"]
    / hospital_summary["total_capacity"]
    * 100
)


# ============================================================
# 10. HOSPITAL RISK LEVEL
# ============================================================

hospital_summary["hospital_risk_level"] = (
    hospital_summary[
        "max_breach_probability"
    ].apply(assign_risk)
)


# ============================================================
# 11. HOSPITAL VACANCY STATUS
# ============================================================

hospital_summary["hospital_vacancy_status"] = (
    hospital_summary["total_available"] > 0
).map({
    True: "AVAILABLE",
    False: "FULL"
})


# ============================================================
# 12. SORT BY RISK
# ============================================================

hospital_summary = (
    hospital_summary
    .sort_values(
        "max_breach_probability",
        ascending=False
    )
    .reset_index(drop=True)
)


# ============================================================
# 13. DISPLAY SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("HOSPITAL CAPACITY & RISK SUMMARY")
print("=" * 70)

display_columns = [
    "hospital_name_department",
    "total_capacity",
    "total_occupied",
    "total_available",
    "current_occupancy_pct",
    "highest_risk_department",
    "max_breach_probability",
    "hospital_risk_level",
    "hospital_vacancy_status"
]

print(
    hospital_summary[
        display_columns
    ].to_string(index=False)
)


# ============================================================
# 14. SAVE HOSPITAL ROLLUP
# ============================================================

hospital_summary.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nHospital rollup saved successfully:")
print(OUTPUT_FILE)


# ============================================================
# 15. SAVE LATEST DEPARTMENT AVAILABILITY
# ============================================================

DEPT_OUTPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "latest_department_availability.csv"
)

department_output = latest_df[
    [
        "date",
        "hospital_id",
        "hospital_name_department",
        "department",
        "department_bed_capacity",
        "occupied_beds",
        "available_beds",
        "vacancy_status",
        "predicted_occupancy_7d",
        "breach_probability",
        "predicted_breach_7d",
        "forecast_risk_level"
    ]
].copy()

department_output.to_csv(
    DEPT_OUTPUT_FILE,
    index=False
)

print("\nDepartment availability saved successfully:")
print(DEPT_OUTPUT_FILE)

print("\nRollup completed successfully.")