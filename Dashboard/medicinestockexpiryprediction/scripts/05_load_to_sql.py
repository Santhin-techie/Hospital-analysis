import sqlite3
import pandas as pd
import os

# Create database folder
os.makedirs("../database", exist_ok=True)

# Connect to SQLite database
conn = sqlite3.connect("../database/hospital.db")

# Load CSV files into SQLite tables
pd.read_csv("../Cleaned_data/medicine_master.csv").to_sql(
    "medicine_master", conn, if_exists="replace", index=False
)

pd.read_csv("../Data/cleaned/usage_history.csv").to_sql(
    "usage_history", conn, if_exists="replace", index=False
)

pd.read_csv("../Cleaned_data/batch_stock.csv").to_sql(
    "batch_stock", conn, if_exists="replace", index=False
)

# Check number of records in each table
for t in ["medicine_master", "usage_history", "batch_stock"]:
    count = pd.read_sql(
        f"SELECT COUNT(*) AS n FROM {t}", conn
    )["n"][0]

    print(t, count)

# Close database connection
conn.close()