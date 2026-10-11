from pathlib import Path

import numpy as np
import pandas as pd

from xgboost import XGBRegressor, XGBClassifier

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
)


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "data" / "bed_occupancy_features.csv"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"

MODELS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(DATA_FILE)

df["date"] = pd.to_datetime(df["date"])

df = df.sort_values("date").reset_index(drop=True)

print("Feature dataset loaded successfully.")
print("Dataset shape:", df.shape)

print("\nDate range:")
print(df["date"].min(), "to", df["date"].max())


# ============================================================
# 3. SELECT MODEL FEATURES
# ============================================================

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


X = df[feature_columns]

y_reg = df["target_occupancy_7d"]
y_clf = df["target_breach_7d"]


print("\nNumber of features:", len(feature_columns))


# ============================================================
# 4. TIME-BASED TRAIN / TEST SPLIT
# ============================================================

# IMPORTANT:
# We use earlier dates for training and later dates for testing.
# We do NOT randomly mix past and future dates.

unique_dates = np.array(sorted(df["date"].unique()))

split_index = int(len(unique_dates) * 0.90)

train_dates = unique_dates[:split_index]
test_dates = unique_dates[split_index:]

train_mask = df["date"].isin(train_dates)
test_mask = df["date"].isin(test_dates)


X_train = X.loc[train_mask]
X_test = X.loc[test_mask]

y_reg_train = y_reg.loc[train_mask]
y_reg_test = y_reg.loc[test_mask]

y_clf_train = y_clf.loc[train_mask]
y_clf_test = y_clf.loc[test_mask]


print("\n" + "=" * 60)
print("TIME-BASED TRAIN / TEST SPLIT")
print("=" * 60)

print(
    "Training period:",
    df.loc[train_mask, "date"].min().date(),
    "to",
    df.loc[train_mask, "date"].max().date()
)

print(
    "Testing period:",
    df.loc[test_mask, "date"].min().date(),
    "to",
    df.loc[test_mask, "date"].max().date()
)

print("Training rows:", len(X_train))
print("Testing rows:", len(X_test))


# ============================================================
# 5. XGBOOST REGRESSION MODEL
# ============================================================

print("\n" + "=" * 60)
print("TRAINING OCCUPANCY REGRESSION MODEL")
print("=" * 60)

reg_model = XGBRegressor(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1
)

reg_model.fit(X_train, y_reg_train)


# ============================================================
# 6. REGRESSION PREDICTIONS
# ============================================================

reg_predictions = reg_model.predict(X_test)

reg_predictions = np.clip(
    reg_predictions,
    0,
    100
)


# ============================================================
# 7. REGRESSION EVALUATION
# ============================================================

mae = mean_absolute_error(
    y_reg_test,
    reg_predictions
)

rmse = np.sqrt(
    mean_squared_error(
        y_reg_test,
        reg_predictions
    )
)

r2 = r2_score(
    y_reg_test,
    reg_predictions
)


print("\nREGRESSION RESULTS")
print("MAE :", round(mae, 3))
print("RMSE:", round(rmse, 3))
print("R²  :", round(r2, 3))


# ============================================================
# 8. NAIVE BASELINE
# ============================================================

# Baseline:
# Assume future occupancy is similar to the most recently
# available occupancy.

naive_predictions = X_test["lag_1_occupancy"].values

naive_mae = mean_absolute_error(
    y_reg_test,
    naive_predictions
)

print("\nNaive baseline MAE:", round(naive_mae, 3))
print("XGBoost MAE       :", round(mae, 3))

if mae < naive_mae:
    print("Result: XGBoost beats the naive baseline.")
else:
    print("Result: XGBoost does not beat the naive baseline.")


# ============================================================
# 9. HANDLE CLASS IMBALANCE
# ============================================================

negative_count = (y_clf_train == 0).sum()
positive_count = (y_clf_train == 1).sum()

scale_pos_weight = negative_count / positive_count

print("\nTraining breach distribution:")
print(y_clf_train.value_counts())

print(
    "\nscale_pos_weight:",
    round(scale_pos_weight, 3)
)


# ============================================================
# 10. XGBOOST CLASSIFIER
# ============================================================

print("\n" + "=" * 60)
print("TRAINING CAPACITY BREACH CLASSIFIER")
print("=" * 60)

clf_model = XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="binary:logistic",
    eval_metric="logloss",
    scale_pos_weight=scale_pos_weight,
    random_state=42,
    n_jobs=-1
)

clf_model.fit(
    X_train,
    y_clf_train
)


# ============================================================
# 11. CLASSIFICATION PREDICTIONS
# ============================================================

breach_probabilities = clf_model.predict_proba(
    X_test
)[:, 1]

breach_predictions = (
    breach_probabilities >= 0.50
).astype(int)


# ============================================================
# 12. CLASSIFICATION EVALUATION
# ============================================================

accuracy = accuracy_score(
    y_clf_test,
    breach_predictions
)

precision = precision_score(
    y_clf_test,
    breach_predictions,
    zero_division=0
)

recall = recall_score(
    y_clf_test,
    breach_predictions,
    zero_division=0
)

f1 = f1_score(
    y_clf_test,
    breach_predictions,
    zero_division=0
)

roc_auc = roc_auc_score(
    y_clf_test,
    breach_probabilities
)


print("\nCLASSIFICATION RESULTS")

print("Accuracy :", round(accuracy, 3))
print("Precision:", round(precision, 3))
print("Recall   :", round(recall, 3))
print("F1 Score :", round(f1, 3))
print("ROC-AUC  :", round(roc_auc, 3))


print("\nConfusion Matrix:")
print(
    confusion_matrix(
        y_clf_test,
        breach_predictions
    )
)


print("\nClassification Report:")
print(
    classification_report(
        y_clf_test,
        breach_predictions,
        digits=3,
        zero_division=0
    )
)


# ============================================================
# 13. SAVE BOTH MODELS
# ============================================================

reg_model.save_model(
    MODELS_DIR / "reg_model.json"
)

clf_model.save_model(
    MODELS_DIR / "clf_model.json"
)

print("\nModels saved successfully.")


# ============================================================
# 14. SAVE DEPARTMENT FORECAST RESULTS
# ============================================================

results = df.loc[
    test_mask,
    [
        "date",
        "hospital_id",
        "hospital_name_department",
        "department",
        "department_bed_capacity",
        "occupied_beds",
        "available_beds"
    ]
].copy()


results["actual_occupancy_7d"] = (
    y_reg_test.values
)

results["predicted_occupancy_7d"] = (
    reg_predictions
)

results["actual_breach_7d"] = (
    y_clf_test.values
)

results["breach_probability"] = (
    breach_probabilities
)

results["predicted_breach_7d"] = (
    breach_predictions
)


RESULT_FILE = (
    OUTPUTS_DIR /
    "dept_forecast_results.csv"
)

results.to_csv(
    RESULT_FILE,
    index=False
)


print(
    "\nDepartment forecast results saved:",
    RESULT_FILE
)

print("\nTraining completed successfully.")