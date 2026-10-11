import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

pd.set_option("display.max_columns", None)


#======Load the main department dataset======
BASE_DIR = Path.cwd().parent

DATA_PATH = BASE_DIR / "data" / "bed_occupancy_real_hospitals.csv"

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully!")
print("Shape:", df.shape)
df["date"] = pd.to_datetime(df["date"])

#======Basic dataset overview======
print("Number of rows:", df.shape[0])
print("Number of columns:", df.shape[1])

print("\nColumn names:")
print(df.columns.tolist())

print("\nData types:")
print(df.dtypes)

print("\nFirst 5 rows:")
print(df.head())

#======Missing-value analysis======
missing = df.isnull().sum()

missing = missing[missing > 0].sort_values(ascending=False)

print("Columns containing missing values:")
print(missing.to_frame("missing_count"))

missing_pct = (df.isnull().sum() / len(df)) * 100
missing_pct = missing_pct[missing_pct > 0].sort_values(ascending=False)

print(missing_pct.to_frame("missing_percentage"))

#======Duplicate analysis======
duplicates = df.duplicated().sum()

print("Duplicate rows:", duplicates)

#======Basic numerical statistics======
important_columns = [
    "department_bed_capacity",
    "occupied_beds",
    "available_beds",
    "admissions",
    "discharges",
    "occupancy_rate_pct",
    "avg_temperature_c",
    "rainfall_mm",
    "accident_cases"
]

print(df[important_columns].describe().T)


#==============OCCUPANCY EDA==============
#======Occupancy distribution======
plt.figure(figsize=(9, 5))

plt.hist(
    df["occupancy_rate_pct"],
    bins=30,
    edgecolor="black"
)

plt.axvline(
    df["occupancy_rate_pct"].mean(),
    linestyle="--",
    label=f'Mean = {df["occupancy_rate_pct"].mean():.2f}%'
)

plt.xlabel("Occupancy Rate (%)")
plt.ylabel("Number of Records")
plt.title("Distribution of Hospital Bed Occupancy")

plt.legend()
plt.tight_layout()
plt.show()

#======Overall occupancy statistics======
print("Average occupancy:",
      round(df["occupancy_rate_pct"].mean(), 2), "%")

print("Median occupancy:",
      round(df["occupancy_rate_pct"].median(), 2), "%")

print("Minimum occupancy:",
      round(df["occupancy_rate_pct"].min(), 2), "%")

print("Maximum occupancy:",
      round(df["occupancy_rate_pct"].max(), 2), "%")


#==============Department Analysis==============
#======Average occupancy by department======
dept_occupancy = (
    df.groupby("department")["occupancy_rate_pct"]
    .mean()
    .sort_values(ascending=False)
)

print(dept_occupancy.to_frame("average_occupancy"))

plt.figure(figsize=(10, 5))

dept_occupancy.plot(kind="bar")

plt.title("Average Bed Occupancy by Department")
plt.xlabel("Department")
plt.ylabel("Average Occupancy (%)")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()


#==============Hospital Analysis==============
#======Average occupancy by hospital======
hospital_occupancy = (
    df.groupby("hospital_name")["occupancy_rate_pct"]
    .mean()
    .sort_values(ascending=False)
)

print(hospital_occupancy.to_frame("average_occupancy"))

plt.figure(figsize=(12, 6))

hospital_occupancy.plot(kind="bar")

plt.title("Average Bed Occupancy by Hospital")
plt.xlabel("Hospital")
plt.ylabel("Average Occupancy (%)")
plt.xticks(rotation=70, ha="right")

plt.tight_layout()
plt.show()


#==============Time-Series Analysis==============
#======Occupancy trend over time======
daily_occupancy = (
    df.groupby("date")["occupancy_rate_pct"]
    .mean()
    .sort_index()
)

plt.figure(figsize=(14, 5))

plt.plot(
    daily_occupancy.index,
    daily_occupancy.values
)

plt.title("Average Bed Occupancy Over Time")
plt.xlabel("Date")
plt.ylabel("Average Occupancy (%)")

plt.tight_layout()
plt.show()


#==============Admissions and Discharges==============
#======Admissions vs discharges over time======
daily_flow = (
    df.groupby("date")[["admissions", "discharges"]]
    .sum()
    .sort_index()
)

plt.figure(figsize=(14, 5))

plt.plot(
    daily_flow.index,
    daily_flow["admissions"],
    label="Admissions"
)

plt.plot(
    daily_flow.index,
    daily_flow["discharges"],
    label="Discharges"
)

plt.title("Daily Admissions vs Discharges")
plt.xlabel("Date")
plt.ylabel("Number of Patients")

plt.legend()
plt.tight_layout()
plt.show()


#==============Capacity Analysis==============
#======Capacity status======
capacity_counts = df["capacity_status"].value_counts()

print(capacity_counts.to_frame("count"))

plt.figure(figsize=(8, 5))

capacity_counts.plot(kind="bar")

plt.title("Distribution of Capacity Status")
plt.xlabel("Capacity Status")
plt.ylabel("Number of Records")
plt.xticks(rotation=0)

plt.tight_layout()
plt.show()

#======Accident cases vs occupancy======
plt.figure(figsize=(8, 5))

plt.scatter(
    df["accident_cases"],
    df["occupancy_rate_pct"],
    alpha=0.3
)

plt.title("Accident Cases vs Bed Occupancy")
plt.xlabel("Accident Cases")
plt.ylabel("Occupancy Rate (%)")

plt.tight_layout()
plt.show()

#======Rainfall vs occupancy======
plt.figure(figsize=(8, 5))

plt.scatter(
    df["rainfall_mm"],
    df["occupancy_rate_pct"],
    alpha=0.3
)

plt.title("Rainfall vs Bed Occupancy")
plt.xlabel("Rainfall (mm)")
plt.ylabel("Occupancy Rate (%)")

plt.tight_layout()
plt.show()

#======Holiday vs occupancy======
holiday_analysis = (
    df.groupby("holiday_flag")["occupancy_rate_pct"]
    .mean()
)

print(holiday_analysis.to_frame("average_occupancy"))

plt.figure(figsize=(6, 4))

holiday_analysis.plot(kind="bar")

plt.title("Average Occupancy: Holiday vs Non-Holiday")
plt.xlabel("Holiday Flag")
plt.ylabel("Average Occupancy (%)")
plt.xticks(rotation=0)

plt.tight_layout()
plt.show()



#==============Correlation Analysis==============
#======Correlation matrix======
corr_columns = [
    "department_bed_capacity",
    "occupied_beds",
    "available_beds",
    "admissions",
    "discharges",
    "occupancy_rate_pct",
    "avg_temperature_c",
    "rainfall_mm",
    "accident_cases",
    "holiday_flag",
    "lag_1_occupancy",
    "lag_7_occupancy",
    "rolling_7d_occupancy",
    "rolling_14d_occupancy",
    "admissions_7d_avg",
    "discharges_7d_avg"
]

corr = df[corr_columns].corr()

print(corr.round(2))

fig, ax = plt.subplots(figsize=(12, 10))

im = ax.imshow(corr)

ax.set_xticks(range(len(corr.columns)))
ax.set_yticks(range(len(corr.columns)))

ax.set_xticklabels(corr.columns, rotation=90)
ax.set_yticklabels(corr.columns)

fig.colorbar(im)

plt.title("Correlation Matrix of Bed Occupancy Features")
plt.tight_layout()
plt.show()

#used to explain feature selection
occupancy_corr = (
    corr["occupancy_rate_pct"]
    .drop("occupancy_rate_pct")
    .sort_values(ascending=False)
)

print(occupancy_corr.to_frame("correlation_with_occupancy"))


#==============7-Day Forecast Target Analysis==============
print("7-Day Occupancy Target Statistics")

print(
    df["predicted_7d_occupancy_pct"]
    .describe()
    .to_frame()
)

print("\nCapacity Breach Counts:")

print(
    df["capacity_breach_7d"]
    .value_counts()
    .to_frame("count")
)

#======Breach distribution======
breach_counts = df["capacity_breach_7d"].value_counts().sort_index()

plt.figure(figsize=(6, 4))

breach_counts.plot(kind="bar")

plt.title("7-Day Capacity Breach Distribution")
plt.xlabel("Capacity Breach")
plt.ylabel("Number of Records")
plt.xticks(rotation=0)

plt.tight_layout()
plt.show()

#======Final EDA Summary======
print("=" * 50)
print("BED OCCUPANCY EDA SUMMARY")
print("=" * 50)

print("Dataset shape:", df.shape)

print(
    "Date range:",
    df["date"].min().date(),
    "to",
    df["date"].max().date()
)

print("Hospitals:", df["hospital_name"].nunique())
print("Departments:", df["department"].nunique())

print(
    "Average occupancy:",
    round(df["occupancy_rate_pct"].mean(), 2),
    "%"
)

print(
    "Average daily admissions:",
    round(df["admissions"].mean(), 2)
)

print(
    "Average daily discharges:",
    round(df["discharges"].mean(), 2)
)

print(
    "Capacity breach records:",
    df["capacity_breach_7d"].sum()
)