from pathlib import Path
import subprocess
import sys
import time


# ============================================================
# 1. PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"


# ============================================================
# 2. PIPELINE STEPS
# ============================================================

PIPELINE = [
    ("Combining datasets", "combine.py"),
    ("Feature engineering", "features.py"),
    ("Training prediction models", "train.py"),
    ("Creating hospital risk rollup", "rollup.py"),
    ("Generating SHAP explanations", "explain.py"),
]


# ============================================================
# 3. RUN ONE PIPELINE STEP
# ============================================================

def run_step(step_number, description, script_name):

    script_path = SRC_DIR / script_name

    print("\n" + "=" * 70)
    print(
        f"STEP {step_number}/{len(PIPELINE)}: "
        f"{description.upper()}"
    )
    print("=" * 70)

    if not script_path.exists():
        print(f"ERROR: Could not find {script_path}")
        return False

    start_time = time.time()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR
    )

    elapsed_time = time.time() - start_time

    if result.returncode != 0:
        print("\n" + "!" * 70)
        print(f"PIPELINE STOPPED AT: {script_name}")
        print(
            f"Exit code: {result.returncode}"
        )
        print("!" * 70)

        return False

    print(
        f"\n{script_name} completed successfully "
        f"in {elapsed_time:.1f} seconds."
    )

    return True


# ============================================================
# 4. MAIN PIPELINE
# ============================================================

def main():

    pipeline_start = time.time()

    print("\n" + "=" * 70)
    print("HOSPITAL BED OCCUPANCY FORECASTING PIPELINE")
    print("=" * 70)

    print("\nStarting Module 1 pipeline...")

    for step_number, (
        description,
        script_name
    ) in enumerate(PIPELINE, start=1):

        success = run_step(
            step_number,
            description,
            script_name
        )

        if not success:
            print(
                "\nPipeline execution failed."
            )
            sys.exit(1)

    total_time = time.time() - pipeline_start

    # ========================================================
    # 5. FINAL OUTPUT SUMMARY
    # ========================================================

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)

    print(
        f"\nTotal execution time: "
        f"{total_time:.1f} seconds"
    )

    print("\nGenerated outputs:")

    expected_outputs = [
        BASE_DIR / "data" / "bed_occupancy_combined.csv",
        BASE_DIR / "data" / "bed_occupancy_features.csv",
        BASE_DIR / "models" / "reg_model.json",
        BASE_DIR / "models" / "clf_model.json",
        BASE_DIR / "outputs" / "dept_forecast_results.csv",
        BASE_DIR / "outputs" / "hospital_risk_rollup.csv",
        BASE_DIR / "outputs" / "latest_department_availability.csv",
        BASE_DIR / "outputs" / "shap_summary.png",
        BASE_DIR / "outputs" / "alert_explanations.csv",
    ]

    for file_path in expected_outputs:

        if file_path.exists():
            print(
                f"[OK] {file_path.relative_to(BASE_DIR)}"
            )
        else:
            print(
                f"[MISSING] {file_path.relative_to(BASE_DIR)}"
            )

    print("\nModule 1 is ready.")


# ============================================================
# 6. START PROGRAM
# ============================================================

if __name__ == "__main__":
    main()