import pandas as pd

df = pd.read_csv("../Data/cleaned/salesdaily_clean.csv")

medicine_cols = ['M01AB', 'M01AE', 'N02BA', 'N02BE', 'N05B', 'N05C', 'R03', 'R06']

usage_long = df.melt(
    id_vars='datum',
    value_vars=medicine_cols,
    var_name='medicine_id',
    value_name='quantity_used'
)

usage_long.rename(columns={'datum': 'date'}, inplace=True)

usage_long['department'] = 'General'
usage_long['hospital_id'] = 'H01'
usage_long['usage_id'] = range(1, len(usage_long) + 1)

usage_long.to_csv("../Data/cleaned/usage_history.csv", index=False)

print("usage_history shape:", usage_long.shape)