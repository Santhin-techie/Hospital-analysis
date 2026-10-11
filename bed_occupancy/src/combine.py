import pandas as pd
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load both CSV files
df1 = pd.read_csv(BASE_DIR / "data" / "bed_occupancy_real_hospitals.csv")
df2 = pd.read_csv(BASE_DIR / "data" / "bed_occupancy_hospital_daily_summary.csv")

# Merge using date and hospital_id
combined_df = pd.merge(
    df1,
    df2,
    on=["date", "hospital_id"],
    how="left",
    suffixes=("_department", "_hospital")
)

# Save inside data folder
combined_df.to_csv(
    BASE_DIR / "data" / "bed_occupancy_combined.csv",
    index=False
)

print("Combined dataset created successfully!")
print("Shape:", combined_df.shape)
print(combined_df.head())