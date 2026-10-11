"""
Module 3 — Blood Bank Intelligence: dashboard data layer
---------------------------------------------------------
Pure pandas, no Streamlit. All loading, filtering and aggregation lives here so the
page file stays small and Module 4 / other pages can reuse the same functions.

Running this file directly writes the Module 4 hand-off table:
    py app\\blood_data.py        ->  outputs\\blood_module4_export.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
RISK_ORDER = {"High": 0, "Medium": 1, "Low": 2}
RISK_COLUMNS = ["hospital_name", "blood_group", "risk_level", "stock_now", "days_of_cover",
                "forecast_demand_7d", "demand_upper_7d", "forecast_donations_7d",
                "projected_stock_end", "deficit_units", "surplus_units", "reason"]


def _read(path, **kw):
    path = Path(path)
    return pd.read_csv(path, **kw) if path.exists() else None


def stamp(root):
    """File modification times, used by the page to refresh cached data when files change."""
    root = Path(root)
    files = list((root / "outputs").glob("*.csv")) + list((root / "data" / "simulated").glob("*.csv"))
    return tuple(sorted((f.name, f.stat().st_mtime) for f in files))


def load_all(root):
    """Return (dict of DataFrames, list of REQUIRED files that are missing)."""
    root = Path(root)
    out, sim = root / "outputs", root / "data" / "simulated"
    hist = _read(sim / "blood_daily_operations.csv", parse_dates=["date"],
                 usecols=["date", "hospital_id", "blood_group", "units_demanded",
                          "units_donated", "closing_stock"])
    if hist is not None:                       # only the recent weeks are ever plotted
        hist = hist[hist["date"] > hist["date"].max() - pd.Timedelta(days=60)]
    d = {
        "risk": _read(out / "blood_risk.csv"),
        "forecast": _read(out / "blood_forecasts.csv", parse_dates=["date"]),
        "expiry": _read(out / "blood_expiry_risk.csv"),
        "transfers": _read(out / "blood_transfers.csv"),
        "explain": _read(out / "blood_alert_explanations.csv"),
        "hospitals": _read(sim / "chennai_hospitals.csv"),
        "history": hist,
        "cmp": _read(out / "model_comparison_blood.csv"),
        "cmp7": _read(out / "horizon7_comparison_blood.csv"),
    }
    required = {"risk": "outputs\\blood_risk.csv", "forecast": "outputs\\blood_forecasts.csv",
                "hospitals": "data\\simulated\\chennai_hospitals.csv"}
    missing = [v for k, v in required.items() if d[k] is None]
    return d, missing


def select(df, hospitals=None, groups=None, hosp_col="hospital_id", grp_col="blood_group"):
    """Keep rows for the chosen hospitals / groups. Empty or None means 'all'."""
    if df is None:
        return None
    if hospitals:
        df = df[df[hosp_col].isin(hospitals)]
    if groups:
        df = df[df[grp_col].isin(groups)]
    return df


def forecast_series(fc, hospitals, groups, horizon):
    """Daily forecast summed over the selection. The P10-P90 band of a sum is combined in
    quadrature (errors treated as independent); for ONE hospital + group it is exact."""
    sub = select(fc, hospitals, groups)
    sub = sub[sub["horizon_day"] <= horizon].copy()
    sub["lo2"] = (sub["demand_forecast"] - sub["demand_lower_p10"]).clip(lower=0) ** 2
    sub["up2"] = (sub["demand_upper_p90"] - sub["demand_forecast"]).clip(lower=0) ** 2
    g = sub.groupby("date").agg(demand=("demand_forecast", "sum"), donation=("donation_forecast", "sum"),
                                lo2=("lo2", "sum"), up2=("up2", "sum")).reset_index()
    g["lower"] = (g["demand"] - np.sqrt(g["lo2"])).clip(lower=0)
    g["upper"] = g["demand"] + np.sqrt(g["up2"])
    return g[["date", "demand", "lower", "upper", "donation"]]


def history_series(hist, hospitals, groups, days=28):
    if hist is None:
        return None
    sub = select(hist, hospitals, groups)
    g = sub.groupby("date").agg(demand=("units_demanded", "sum"),
                                donation=("units_donated", "sum")).reset_index()
    return g[g["date"] > g["date"].max() - pd.Timedelta(days=days)]


def cover_matrix(risk, hospitals=None, groups=None):
    """Hospital x blood group matrices of days of cover and risk level."""
    sub = select(risk, hospitals, groups)
    cols = [g for g in GROUPS if g in set(sub["blood_group"])]
    cover = sub.pivot(index="hospital_name", columns="blood_group", values="days_of_cover")[cols]
    level = sub.pivot(index="hospital_name", columns="blood_group", values="risk_level")[cols]
    return cover, level


def risk_table(risk, hospitals, groups, levels):
    sub = select(risk, hospitals, groups)
    if levels:
        sub = sub[sub["risk_level"].isin(levels)]
    sub = sub.assign(_o=sub["risk_level"].map(RISK_ORDER)).sort_values(["_o", "days_of_cover"])
    return sub[[c for c in RISK_COLUMNS if c in sub.columns]].reset_index(drop=True)


def transfers_for(tr, hospitals, groups):
    """Transfers that touch the selected hospitals (as sender OR receiver)."""
    if tr is None or tr.empty:
        return tr
    if hospitals:
        tr = tr[tr["from_hospital"].isin(hospitals) | tr["to_hospital"].isin(hospitals)]
    if groups:
        tr = tr[tr["blood_group"].isin(groups)]
    return tr


def transfer_arcs(tr, hospitals_df):
    """Add coordinates to transfers so they can be drawn as arcs on a map."""
    if tr is None or tr.empty:
        return pd.DataFrame()
    xy = hospitals_df[["hospital_id", "latitude", "longitude"]]
    a = tr.merge(xy.rename(columns={"hospital_id": "from_hospital", "latitude": "from_lat",
                                    "longitude": "from_lon"}), on="from_hospital", how="left")
    a = a.merge(xy.rename(columns={"hospital_id": "to_hospital", "latitude": "to_lat",
                                   "longitude": "to_lon"}), on="to_hospital", how="left")
    a["width"] = 2 + a["units"].astype(float)
    a["label"] = (a["units"].astype(int).astype(str) + " units " + a["blood_group"] + ": "
                  + a["from_name"] + " -> " + a["to_name"] + " (" + a["travel_minutes"].astype(int).astype(str) + " min)")
    return a


def find_waterfall(fig_dir, hospital_id, group):
    hits = sorted(Path(fig_dir).glob(f"shap_03_waterfall_*_{hospital_id}_{group}.png"))
    return hits[0] if hits else None


def module4_table(risk, transfers):
    """Hand-off to Module 4: blood availability per hospital and group (same hospital_id)."""
    out = risk[["hospital_id", "blood_group", "risk_level", "days_of_cover", "stock_now",
                "deficit_units", "surplus_units"]].copy()
    if transfers is not None and not transfers.empty:
        inc = (transfers.groupby(["to_hospital", "blood_group"])["units"].sum()
               .rename("recommended_units_incoming").reset_index().rename(columns={"to_hospital": "hospital_id"}))
        outg = (transfers.groupby(["from_hospital", "blood_group"])["units"].sum()
                .rename("recommended_units_outgoing").reset_index().rename(columns={"from_hospital": "hospital_id"}))
        out = out.merge(inc, on=["hospital_id", "blood_group"], how="left")
        out = out.merge(outg, on=["hospital_id", "blood_group"], how="left")
    for c in ("recommended_units_incoming", "recommended_units_outgoing"):
        out[c] = out[c].fillna(0).astype(int) if c in out else 0
    out["risk_rank"] = out["risk_level"].map(RISK_ORDER)
    return out.sort_values(["hospital_id", "blood_group"]).reset_index(drop=True)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    d, missing = load_all(root)
    if missing:
        raise SystemExit(f"Missing files: {missing}. Run the earlier scripts first.")
    path = root / "outputs" / "blood_module4_export.csv"
    module4_table(d["risk"], d["transfers"]).to_csv(path, index=False)
    print("Wrote", path)