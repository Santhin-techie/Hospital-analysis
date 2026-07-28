"""
Module 2 — Medicine Demand Forecasting + Expiry-Aware Stock Dataset Generator
-------------------------------------------------------------------------------
Grounding References:
  1. National List of Essential Medicines (NLEM 2022, MoHFW, Govt of India)
  2. ICMR Disease Burden & Epidemiological Surge Profiles (Monsoon/Winter/Summer)
  3. CDSCO / Central Medical Services Society (CMSS) Procurement Standards

Output: data/simulated/medicine_inventory_demand.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Set random seed for reproducibility
np.random.seed(108)

# ---------------------------------------------------------------------------
# 1. 20 ESSENTIAL MEDICINES IN INDIA (NLEM Aligned) with ICMR Surge Factors
# ---------------------------------------------------------------------------
MEDICINES = [
    {"name": "Paracetamol 650mg",          "category": "Analgesic / Antipyretic", "base_daily": 450, "surge_season": "Monsoon (Dengue/Flu)",   "surge_factor": 1.6, "cost_inr": 2.50},
    {"name": "Amoxicillin + Clav 625mg",   "category": "Antibacterial",           "base_daily": 220, "surge_season": "Winter (Respiratory)",  "surge_factor": 1.4, "cost_inr": 18.00},
    {"name": "Metformin 500mg SR",         "category": "Antidiabetic",            "base_daily": 550, "surge_season": "Chronic (Stable)",       "surge_factor": 1.05, "cost_inr": 3.80},
    {"name": "Atorvastatin 10mg",          "category": "Cardiovascular",          "base_daily": 400, "surge_season": "Chronic (Stable)",       "surge_factor": 1.05, "cost_inr": 6.50},
    {"name": "Pantoprazole 40mg",          "category": "Gastrointestinal",        "base_daily": 380, "surge_season": "Summer (Gastro)",        "surge_factor": 1.3, "cost_inr": 7.20},
    {"name": "Azithromycin 500mg",         "category": "Antibacterial",           "base_daily": 180, "surge_season": "Winter (Respiratory)",  "surge_factor": 1.5, "cost_inr": 22.00},
    {"name": "Cetirizine 10mg",            "category": "Anti-allergy",            "base_daily": 310, "surge_season": "Spring / Pollen",       "surge_factor": 1.35, "cost_inr": 1.80},
    {"name": "Oral Rehydration Salts (ORS)","category": "Electrolyte Replenisher", "base_daily": 600, "surge_season": "Summer (Dehydration)",   "surge_factor": 1.8, "cost_inr": 4.50},
    {"name": "Salbutamol Inhaler 100mcg",  "category": "Respiratory",             "base_daily": 120, "surge_season": "Winter (Asthma/Smog)",  "surge_factor": 1.7, "cost_inr": 115.00},
    {"name": "Artemether + Lumefantrine",  "category": "Antimalarial",            "base_daily": 90,  "surge_season": "Monsoon (Malaria)",      "surge_factor": 2.1, "cost_inr": 65.00},
    {"name": "Amlodipine 5mg",             "category": "Antihypertensive",        "base_daily": 480, "surge_season": "Chronic (Stable)",       "surge_factor": 1.02, "cost_inr": 2.20},
    {"name": "Dicyclomine + Paracetamol",  "category": "Antispasmodic",           "base_daily": 140, "surge_season": "Summer (Gastro)",        "surge_factor": 1.25, "cost_inr": 5.40},
    {"name": "Insulin Glargine 100IU/ml",  "category": "Antidiabetic",            "base_daily": 75,  "surge_season": "Chronic (Stable)",       "surge_factor": 1.08, "cost_inr": 480.00},
    {"name": "Cefixime 200mg",             "category": "Antibacterial",           "base_daily": 160, "surge_season": "Monsoon (Waterborne)",   "surge_factor": 1.45, "cost_inr": 14.50},
    {"name": "Ibuprofen 400mg",            "category": "NSAID / Anti-inflammatory","base_daily": 260, "surge_season": "General",                "surge_factor": 1.15, "cost_inr": 3.10},
    {"name": "Telmisartan 40mg",           "category": "Antihypertensive",        "base_daily": 390, "surge_season": "Chronic (Stable)",       "surge_factor": 1.04, "cost_inr": 8.00},
    {"name": "Domperidone 10mg",           "category": "Antiemetic",              "base_daily": 230, "surge_season": "Summer (Gastro)",        "surge_factor": 1.3, "cost_inr": 3.60},
    {"name": "Ascorbic Acid (Vit C) 500mg","category": "Nutritional Supplement",  "base_daily": 340, "surge_season": "Monsoon / Winter",      "surge_factor": 1.25, "cost_inr": 1.50},
    {"name": "Levothyroxine 50mcg",        "category": "Endocrine",               "base_daily": 310, "surge_season": "Chronic (Stable)",       "surge_factor": 1.02, "cost_inr": 2.80},
    {"name": "Oseltamivir 75mg (Tamiflu)", "category": "Antiviral",               "base_daily": 45,  "surge_season": "Monsoon/Winter (H1N1)",  "surge_factor": 2.4, "cost_inr": 45.00},
]

# ---------------------------------------------------------------------------
# 2. GENERATE DETAILED BATCHES & EXPIRED DATES
# ---------------------------------------------------------------------------
today = datetime.now()
data = []

for i, med in enumerate(MEDICINES, start=1):
    med_id = f"MED-{i:03d}"
    batch_no = f"BAT-2025-{np.random.randint(100, 999)}"
    
    scenario = np.random.choice(["expired", "critical", "warning", "safe", "shortage_prone"], p=[0.10, 0.20, 0.25, 0.30, 0.15])
    
    if scenario == "expired":
        days_to_exp = np.random.randint(-20, -1)
        stock_units = np.random.randint(500, 3000)
    elif scenario == "critical":
        days_to_exp = np.random.randint(5, 30)
        stock_units = np.random.randint(2000, 15000)
    elif scenario == "warning":
        days_to_exp = np.random.randint(31, 90)
        stock_units = np.random.randint(4000, 25000)
    elif scenario == "shortage_prone":
        days_to_exp = np.random.randint(40, 120)
        stock_units = np.random.randint(500, 2500)
    else: # safe
        days_to_exp = np.random.randint(91, 365)
        stock_units = np.random.randint(10000, 50000)

    expiry_date = today + timedelta(days=int(days_to_exp))
    mfg_date = expiry_date - timedelta(days=730)
    
    daily_demand = round(med["base_daily"] * med["surge_factor"] * np.random.uniform(0.95, 1.05), 1)
    
    effective_days = max(0, days_to_exp)
    projected_stock_left = round(stock_units - (daily_demand * effective_days), 1)
    
    if days_to_exp <= 0:
        expiry_urgency = "EXPIRED"
        stock_status = "EXPIRED WASTAGE"
        value_at_risk = round(stock_units * med["cost_inr"], 2)
    elif days_to_exp <= 30:
        expiry_urgency = "CRITICAL"
        if projected_stock_left < 0:
            stock_status = "SHORTAGE RISK"
            value_at_risk = 0.0
        else:
            stock_status = "WASTAGE RISK"
            value_at_risk = round(projected_stock_left * med["cost_inr"], 2)
    elif days_to_exp <= 90:
        expiry_urgency = "WARNING"
        if projected_stock_left < 0:
            stock_status = "SHORTAGE RISK"
            value_at_risk = 0.0
        else:
            stock_status = "WASTAGE RISK"
            value_at_risk = round(projected_stock_left * med["cost_inr"], 2)
    else:
        expiry_urgency = "SAFE"
        if projected_stock_left < 0:
            stock_status = "SHORTAGE RISK"
            value_at_risk = 0.0
        else:
            stock_status = "STABLE STOCK"
            value_at_risk = 0.0

    data.append({
        "medicine_id": med_id,
        "medicine_name": med["name"],
        "category": med["category"],
        "batch_number": batch_no,
        "manufacture_date": mfg_date.strftime("%Y-%m-%d"),
        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        "days_to_expiry": days_to_exp,
        "unit_cost_inr": med["cost_inr"],
        "current_stock_units": stock_units,
        "reorder_level": int(daily_demand * 7),
        "base_daily_demand": med["base_daily"],
        "icmr_surge_season": med["surge_season"],
        "icmr_surge_factor": med["surge_factor"],
        "forecasted_daily_demand": daily_demand,
        "projected_stock_left_at_expiry": projected_stock_left,
        "expiry_urgency": expiry_urgency,
        "stock_status": stock_status,
        "value_at_risk_inr": value_at_risk,
    })

df = pd.DataFrame(data)

out_dir = r"C:\Users\santhin kumar k\mini\data\simulated"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "medicine_inventory_demand.csv")
df.to_csv(out_path, index=False)

print(f"Generated dataset for {len(df)} medicines -> {out_path}")
print("\nExpiry Urgency Breakdown:")
print(df["expiry_urgency"].value_counts())
print("\nStock Risk Status Breakdown:")
print(df["stock_status"].value_counts())
print(f"\nTotal Financial Value at Risk: Rs.{df['value_at_risk_inr'].sum():,.2f}")
