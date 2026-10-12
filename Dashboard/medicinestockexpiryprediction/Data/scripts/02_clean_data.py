import pandas as pd

# Read the sales daily data
df = pd.read_csv("../pharma-sales-data/salesdaily.csv")
medicine_cols = ['M01AB', 'M01AE', 'N02BA', 'N02BE', 'N05B', 'N05C', 'R03', 'R06']

# Cleaning
df['datum'] = pd.to_datetime(df['datum'], errors='coerce')

df.dropna(subset=['datum'], inplace=True)

df.drop_duplicates(inplace=True)

df[medicine_cols] = df[medicine_cols].fillna(0)

for col in medicine_cols:
    df[col] = df[col].clip(lower=0)

# Save cleaned data
df.to_csv("../Data/cleaned/salesdaily_clean.csv", index=False)

print("Cleaned shape:", df.shape)