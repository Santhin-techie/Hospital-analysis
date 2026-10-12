import pandas as pd

meds = pd.read_csv("../Cleaned_data/medicine_master.csv")
batch = pd.read_csv("../Cleaned_data/batch_stock.csv")
usage = pd.read_csv("../Data/cleaned/usage_history.csv")

print("master:", sorted(meds['medicine_id'].unique()))
print("batch:", sorted(batch['medicine_id'].unique()))
print("usage:", sorted(usage['medicine_id'].unique()))