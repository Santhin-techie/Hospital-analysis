from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap

from xgboost import XGBClassifier


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FEATURE_FILE = (
    BASE_DIR
    / "data"
    / "bed_occupancy_features.csv"
)

MODEL_FILE = (
    BASE_DIR
    / "models"
    / "clf_model.json"
)

FORECAST_FILE = (
    BASE_DIR
    / "outputs"
    / "dept_forecast_results.csv"
)

OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

SHAP_PLOT_FILE = OUTPUTS_DIR / "shap_summary.png"
EXPLANATION_FILE = OUTPUTS_DIR / "alert_explanations.csv"


# ============================================================
# 2. FEATURE LIST
# ============================================================

# IMPORTANT:
# This must be exactly the same feature list and order
# that was used in train.py.

feature_columns = [
    "department_bed_capacity",
    "lag_1_occupancy",
    "lag_7_occupancy",
    "rolling_7d_occupancy",
    "rolling_14d_occupancy",
    "occupancy_trend_7d",
    "admissions_7d_avg",
    "discharges_7d_avg",
    "avg_temperature_c",
    "rainfall_mm",
    "accident_cases",
    "holiday_flag",
    "month",
    "day_of_week",
    "week_of_year",
    "is_weekend"
]


# ============================================================
# 3. LOAD FEATURE DATASET
# ============================================================

df = pd.read_csv(FEATURE_FILE)

df["date"] = pd.to_datetime(df["date"])

df = df.sort_values("date").reset_index(drop=True)

print("Feature dataset loaded successfully.")
print("Dataset shape:", df.shape)


# ============================================================
# 4. RECREATE THE SAME TEST PERIOD USED IN train.py
# ============================================================

unique_dates = np.array(sorted(df["date"].unique()))

split_index = int(len(unique_dates) * 0.90)

test_dates = unique_dates[split_index:]

test_mask = df["date"].isin(test_dates)

test_df = df.loc[test_mask].copy()

X_test = test_df[feature_columns].copy()

print("\nTest period:")
print(test_df["date"].min().date(), "to", test_df["date"].max().date())

print("Test rows:", len(test_df))


# ============================================================
# 5. LOAD TRAINED CLASSIFIER
# ============================================================

clf_model = XGBClassifier()

clf_model.load_model(str(MODEL_FILE))

print("\nTrained classifier loaded successfully.")


# ============================================================
# 6. CREATE SHAP EXPLAINER
# ============================================================

print("\nCalculating SHAP values...")

explainer = shap.TreeExplainer(clf_model)

shap_values = explainer.shap_values(X_test)

# Convert to numpy array if required.
shap_values = np.asarray(shap_values)

print("SHAP values calculated successfully.")
print("SHAP shape:", shap_values.shape)


# ============================================================
# 7. GLOBAL SHAP SUMMARY PLOT
# ============================================================

plt.figure()

shap.summary_plot(
    shap_values,
    X_test,
    feature_names=feature_columns,
    show=False
)

plt.tight_layout()

plt.savefig(
    SHAP_PLOT_FILE,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("\nSHAP summary plot saved:")
print(SHAP_PLOT_FILE)


# ============================================================
# 8. GLOBAL FEATURE IMPORTANCE
# ============================================================

mean_abs_shap = np.abs(shap_values).mean(axis=0)

global_importance = pd.DataFrame({
    "feature": feature_columns,
    "mean_abs_shap": mean_abs_shap
})

global_importance = global_importance.sort_values(
    "mean_abs_shap",
    ascending=False
).reset_index(drop=True)

print("\n" + "=" * 65)
print("GLOBAL SHAP FEATURE IMPORTANCE")
print("=" * 65)

print(global_importance.to_string(index=False))


# ============================================================
# 9. LOAD ACTUAL FORECAST RESULTS
# ============================================================

forecast_df = pd.read_csv(FORECAST_FILE)

forecast_df["date"] = pd.to_datetime(
    forecast_df["date"]
)

# Safety check:
# train.py and explain.py should refer to the same test rows.

if len(forecast_df) != len(test_df):
    raise ValueError(
        "Forecast rows and SHAP test rows do not match."
    )


# ============================================================
# 10. FIND HIGH-RISK ALERTS
# ============================================================

# We explain departments predicted as breaches.

alert_mask = (
    forecast_df["predicted_breach_7d"] == 1
)

alert_positions = np.where(alert_mask.to_numpy())[0]

print("\nPredicted breach alerts:", len(alert_positions))


# ============================================================
# 11. CREATE PER-ALERT EXPLANATIONS
# ============================================================

explanation_rows = []

for position in alert_positions:

    forecast_row = forecast_df.iloc[position]

    row_shap = shap_values[position]

    # For breach-risk explanations, focus on SHAP values
    # that push the classifier toward the positive class.

    positive_indices = np.where(row_shap > 0)[0]

    if len(positive_indices) > 0:

        sorted_positive_indices = positive_indices[
            np.argsort(
                row_shap[positive_indices]
            )[::-1]
        ]

        top_indices = sorted_positive_indices[:3]

    else:

        # Fallback in the unusual case where no feature
        # has a positive SHAP contribution.
        top_indices = np.argsort(
            np.abs(row_shap)
        )[::-1][:3]

    explanation = {
        "date": forecast_row["date"],
        "hospital_id": forecast_row["hospital_id"],
        "hospital_name": forecast_row[
            "hospital_name_department"
        ],
        "department": forecast_row["department"],
        "predicted_occupancy_7d":
            forecast_row["predicted_occupancy_7d"],
        "breach_probability":
            forecast_row["breach_probability"]
    }

    for rank, feature_index in enumerate(
        top_indices,
        start=1
    ):

        feature_name = feature_columns[feature_index]

        explanation[
            f"driver_{rank}_feature"
        ] = feature_name

        explanation[
            f"driver_{rank}_value"
        ] = X_test.iloc[position][feature_name]

        explanation[
            f"driver_{rank}_shap"
        ] = row_shap[feature_index]

    explanation_rows.append(explanation)


# ============================================================
# 12. SAVE ALERT EXPLANATIONS
# ============================================================

alert_explanations = pd.DataFrame(
    explanation_rows
)

alert_explanations.to_csv(
    EXPLANATION_FILE,
    index=False
)

print("\nAlert explanations saved:")
print(EXPLANATION_FILE)


# ============================================================
# 13. SHOW TOP HIGH-RISK ALERTS
# ============================================================

if not alert_explanations.empty:

    top_alerts = (
        alert_explanations
        .sort_values(
            "breach_probability",
            ascending=False
        )
        .head(10)
    )

    print("\n" + "=" * 65)
    print("TOP HIGH-RISK ALERT EXPLANATIONS")
    print("=" * 65)

    display_columns = [
        "hospital_name",
        "department",
        "breach_probability",
        "driver_1_feature",
        "driver_2_feature",
        "driver_3_feature"
    ]

    print(
        top_alerts[
            display_columns
        ].to_string(index=False)
    )

else:

    print("\nNo predicted breach alerts found.")


print("\nExplainability analysis completed successfully.")