"""
Module 3 — Blood Bank Intelligence: Streamlit page
----------------------------------------------------
Run on its own:        py -m streamlit run app\\blood_page.py
Plug into the main app (Santhin):
        from blood_page import render      # app\\ folder on the path
        render()                           # call inside a page / tab

All logic is in blood_data.py; this file only draws.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import blood_data as bd

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "outputs" / "figures"
COLORS = {"High": "#E74C3C", "Medium": "#F5B041", "Low": "#58D68D"}


@st.cache_data(show_spinner=False)
def _load(root, files_stamp):
    return bd.load_all(root)


def _style_risk(df, col="risk_level"):
    fn = lambda v: f"background-color: {COLORS.get(v, 'white')}; color: white; font-weight: 600"
    styler = df.style
    apply = getattr(styler, "map", None) or styler.applymap      # pandas 2.1+ / older
    return apply(fn, subset=[col])


def _heatmap(cover, level):
    fig, ax = plt.subplots(figsize=(8.5, 0.55 * len(cover) + 1.6))
    im = ax.imshow(cover.clip(upper=15).values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)
    ax.set_xticks(range(cover.shape[1]))
    ax.set_xticklabels(cover.columns)
    ax.set_yticks(range(cover.shape[0]))
    ax.set_yticklabels([n.split(",")[0] for n in cover.index], fontsize=8)
    for i in range(cover.shape[0]):
        for j in range(cover.shape[1]):
            v, lv = cover.values[i, j], level.values[i, j]
            ax.text(j, i, "-" if pd.isna(v) else f"{v:.1f}", ha="center", va="center", fontsize=8,
                    fontweight="bold" if lv == "High" else "normal")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Days of cover")
    fig.tight_layout()
    return fig


def _forecast_chart(hist, fcs):
    fig, ax = plt.subplots(figsize=(10, 4))
    if hist is not None and len(hist):
        ax.plot(hist["date"], hist["demand"], color="#C0392B", lw=1.3, label="Demand (actual)")
        ax.plot(hist["date"], hist["donation"], color="#2874A6", lw=1.3, label="Donations (actual)")
    ax.fill_between(fcs["date"], fcs["lower"], fcs["upper"], color="#F5B7B1", alpha=0.6, label="Demand P10-P90")
    ax.plot(fcs["date"], fcs["demand"], color="#C0392B", ls="--", lw=1.6, label="Demand (forecast)")
    ax.plot(fcs["date"], fcs["donation"], color="#2874A6", ls="--", lw=1.6, label="Donations (forecast)")
    if hist is not None and len(hist):
        ax.axvline(hist["date"].max(), color="k", lw=0.8)
    ax.set_ylabel("Units per day")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def _transfer_map(arcs, hosp):
    try:
        import pydeck as pdk
    except ImportError:
        st.map(hosp.rename(columns={"latitude": "lat", "longitude": "lon"})[["lat", "lon"]])
        st.caption("Install pydeck to see transfer arcs: py -m pip install pydeck")
        return
    arcs = arcs.dropna(subset=["from_lat", "to_lat"]).copy()
    arcs["name"] = ""
    arcs["colour"] = arcs["type"].map(lambda t: [31, 97, 141, 200] if t == "primary" else [230, 126, 34, 200])
    layers = [
        pdk.Layer("ScatterplotLayer", data=hosp, get_position="[longitude, latitude]",
                  get_radius=450, get_fill_color=[120, 120, 120, 180], pickable=True),
        pdk.Layer("ArcLayer", data=arcs, get_source_position="[from_lon, from_lat]",
                  get_target_position="[to_lon, to_lat]", get_source_color="colour",
                  get_target_color="colour", get_width="width", pickable=True)]
    view = pdk.ViewState(latitude=float(hosp["latitude"].mean()), longitude=float(hosp["longitude"].mean()),
                         zoom=10.2, pitch=35)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view,
                             tooltip={"text": "{label}{name}"}))


def render():
    d, missing = _load(str(ROOT), bd.stamp(ROOT))
    if missing:
        st.error("Missing input files: " + ", ".join(missing) + ". Run the earlier scripts first.")
        st.stop()
    risk, fc, hosp = d["risk"], d["forecast"], d["hospitals"]
    names = dict(zip(hosp["hospital_id"], hosp["name"]))

    st.title("🩸 Blood Bank Intelligence")
    st.caption(f"Module 3 · stock as of {risk['as_of_date'].iloc[0]} · forecast "
               f"{fc['date'].min().date()} to {fc['date'].max().date()} · "
               "all hospital data is SIMULATED (see README for calibration)")

    # ---- filters -------------------------------------------------------
    st.sidebar.header("Filters")
    hsel = st.sidebar.multiselect("Hospital (empty = all)", options=list(names),
                                  format_func=lambda h: names[h], default=[])
    gsel = st.sidebar.multiselect("Blood group (empty = all)", options=bd.GROUPS, default=[])
    horizon = st.sidebar.slider("Forecast horizon (days)", 1, int(fc["horizon_day"].max()), 7)
    levels = st.sidebar.multiselect("Risk levels in tables", ["High", "Medium", "Low"],
                                    default=["High", "Medium"])
    st.sidebar.caption("Risk flags use the next 7 days. The horizon slider changes the forecast chart.")

    rsel = bd.select(risk, hsel, gsel)
    trs = bd.transfers_for(d["transfers"], hsel, gsel)

    # ---- KPIs ----------------------------------------------------------
    k = st.columns(5)
    k[0].metric("High risk", int((rsel.risk_level == "High").sum()))
    k[1].metric("Medium risk", int((rsel.risk_level == "Medium").sum()))
    k[2].metric("Low risk", int((rsel.risk_level == "Low").sum()))
    k[3].metric("Units short (7 days)", int(round(rsel.deficit_units.sum())))
    k[4].metric("Units to move", int(trs["units"].sum()) if trs is not None and len(trs) else 0)

    tabs = st.tabs(["Overview", "Forecast", "Risk & expiry", "Redistribution", "Explanations", "Model performance"])

    # ---- Overview ------------------------------------------------------
    with tabs[0]:
        st.subheader("Days of cover: hospital × blood group")
        st.caption("Stock divided by upper-bound daily demand. Red = under 2 days. Bold = High risk.")
        cover, level = bd.cover_matrix(risk, hsel, gsel)
        st.pyplot(_heatmap(cover, level))
        by_grp = (pd.crosstab(rsel["blood_group"], rsel["risk_level"])
                  .reindex(index=[g for g in bd.GROUPS if g in set(rsel["blood_group"])],
                           columns=["High", "Medium", "Low"], fill_value=0))
        st.subheader("Risk levels by blood group")
        try:
            st.bar_chart(by_grp, color=[COLORS["High"], COLORS["Medium"], COLORS["Low"]])
        except TypeError:
            st.bar_chart(by_grp)
        tot_def, tot_sup = float(risk.deficit_units.sum()), float(risk.surplus_units.sum())
        if tot_def > tot_sup:
            st.info(f"Network-wide, spare stock ({tot_sup:.0f} units) is smaller than the shortfall "
                    f"({tot_def:.0f} units): moving blood between hospitals cannot close the gap on its own.")

    # ---- Forecast ------------------------------------------------------
    with tabs[1]:
        st.subheader("Demand and donation forecast")
        fcs = bd.forecast_series(fc, hsel, gsel, horizon)
        hist = bd.history_series(d["history"], hsel, gsel)
        st.pyplot(_forecast_chart(hist, fcs))
        what = ("all hospitals" if not hsel else f"{len(hsel)} hospital(s)") + ", " + \
               ("all groups" if not gsel else ", ".join(gsel))
        st.caption(f"Selection: {what}. Band = P10-P90 of demand; for several series it is combined "
                   "assuming independent errors.")
        m = st.columns(3)
        m[0].metric(f"Forecast demand ({horizon} d)", f"{fcs.demand.sum():.0f} units")
        m[1].metric(f"Forecast donations ({horizon} d)", f"{fcs.donation.sum():.0f} units")
        m[2].metric("Net (donations - demand)", f"{fcs.donation.sum() - fcs.demand.sum():+.0f} units")
        with st.expander("Forecast table"):
            st.dataframe(fcs.round({"demand": 1, "lower": 1, "upper": 1, "donation": 1}))

    # ---- Risk & expiry -------------------------------------------------
    with tabs[2]:
        st.subheader("Shortage risk (next 7 days)")
        rt = bd.risk_table(risk, hsel, gsel, levels)
        if rt.empty:
            st.success("No rows match the selected filters.")
        else:
            st.dataframe(_style_risk(rt), hide_index=True)
        st.subheader("Expiry and wastage risk")
        ex = bd.select(d["expiry"], hsel, gsel)
        if ex is None or ex.empty:
            st.success("No batches are forecast to expire unused in the next 7 days.")
        else:
            st.dataframe(ex, hide_index=True)
        watch = rsel[rsel["units_expiring_3d"] > 0][["hospital_name", "blood_group", "units_expiring_3d",
                                                      "days_of_cover"]]
        with st.expander("Units expiring within 3 days (expected to be used first, oldest-first)"):
            st.dataframe(watch.sort_values("units_expiring_3d", ascending=False),
                         hide_index=True)

    # ---- Redistribution ------------------------------------------------
    with tabs[3]:
        st.subheader("Recommended transfers")
        if trs is None or trs.empty:
            st.info("No transfers recommended for this selection (or blood_redistribute.py has not been run).")
        else:
            st.caption("Travel time is an approximation until Module 4's road matrix is connected. "
                       "'substitute' rows are secondary suggestions that need clinician approval.")
            _transfer_map(bd.transfer_arcs(trs, hosp), hosp.assign(label="", name=hosp["name"]))
            show = trs.drop(columns=["from_hospital", "to_hospital"], errors="ignore")
            st.dataframe(show, hide_index=True)

    # ---- Explanations --------------------------------------------------
    with tabs[4]:
        st.subheader("Why this alert?")
        ex_df = bd.select(d["explain"], hsel, gsel)
        if ex_df is None or ex_df.empty:
            st.info("No explanations for this selection (run blood_shap.py to create them).")
        else:
            ex_df = ex_df.reset_index(drop=True)
            pick = st.selectbox("Alert", options=list(ex_df.index),
                                format_func=lambda i: f"{ex_df.risk_level[i]} · {ex_df.blood_group[i]} · {ex_df.hospital_name[i]}")
            row = ex_df.loc[pick]
            st.markdown(f"**{row['explanation']}**")
            c = st.columns(2)
            c[0].metric("Days of cover", f"{row['days_of_cover']:.1f}")
            c[1].metric("Predicted demand, first forecast day", f"{row['predicted_demand_day1']:.1f} units")
            wf = bd.find_waterfall(FIG_DIR, row["hospital_id"], row["blood_group"])
            if wf:
                st.image(str(wf), caption="SHAP waterfall (log scale: how each factor moves expected demand)")
        with st.expander("Global feature importance (SHAP)"):
            for f in ("shap_01_summary.png", "shap_02_importance_bar.png"):
                if (FIG_DIR / f).exists():
                    st.image(str(FIG_DIR / f))

    # ---- Model performance --------------------------------------------
    with tabs[5]:
        st.subheader("How good are the forecasts? (test period 2025 H2)")
        scope = st.selectbox("Scope", ["ALL"] + bd.GROUPS)
        if d["cmp"] is not None:
            t = d["cmp"]
            t = t[(t.split == "test") & (t.scope == scope)]
            st.markdown("**One day ahead**")
            st.dataframe(t[["target", "model", "MAE", "RMSE", "WAPE_%"]], hide_index=True)
        if d["cmp7"] is not None:
            t7 = d["cmp7"]
            t7 = t7[t7.scope == scope]
            st.markdown("**Seven days ahead (what the risk engine uses)**")
            st.dataframe(t7[["target", "model", "MAE_7d_units", "WAPE_7d_%"]], hide_index=True)
        st.caption("WAPE = total absolute error / total demand. Rare groups are mostly zeros, so their errors are large.")

    # ---- Hand-off to Module 4 -----------------------------------------
    st.divider()
    m4 = bd.module4_table(risk, d["transfers"])
    st.download_button("Download Module 4 hand-off (CSV)", data=m4.to_csv(index=False).encode("utf-8"),
                       file_name="blood_module4_export.csv", mime="text/csv")


def main():
    st.set_page_config(page_title="Blood Bank Intelligence", page_icon="🩸", layout="wide")
    render()


if __name__ == "__main__":
    main()