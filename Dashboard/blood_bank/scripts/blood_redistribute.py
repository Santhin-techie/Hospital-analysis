"""
Module 3 — Blood Bank Intelligence: Redistribution Recommender
----------------------------------------------------------------
Moves surplus units to hospitals with a projected deficit, per blood group.

  Version 1 (rule-based)  : most urgent deficit first, nearest hospital with surplus.
  Version 2 (optimisation): integer transportation problem per blood group (scipy MILP).
        minimise  sum(travel_minutes x units)  +  penalty x unmet units
        s.t.      send <= sendable surplus (and only units with enough shelf life left)
                  received + unmet = deficit
                  no transfer longer than MAX_TRAVEL_MIN
  Secondary    : for deficits still unmet after V2, suggest compatible-group substitutes
                  from leftover surplus (clearly labelled, needs clinician approval).

Inputs : outputs/blood_risk.csv, data/simulated/blood_inventory_batches.csv,
         data/simulated/chennai_hospitals.csv
Outputs: outputs/blood_transfers.csv          recommended transfers (V2 + substitutes)
         outputs/blood_transfers_rulebased.csv  V1 result, for the comparison in the report
         outputs/blood_transfer_summary.txt

TRAVEL TIME: Module 4's road travel-time matrix is not wired in yet. Until it is, travel
time = straight-line km x ROAD_FACTOR / CITY_SPEED_KMH + HANDLING_MIN. To use the real
matrix, replace the body of travel_minutes() below (one function, nothing else changes).

Run from the project root:   py scripts\\blood_redistribute.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "data" / "simulated"
OUT_DIR = ROOT / "outputs"

# ---------------------------------------------------------------------------
# Settings (all assumptions, documented)
# ---------------------------------------------------------------------------
ROAD_FACTOR = 1.4          # road distance ~ 1.4 x straight line in a city
CITY_SPEED_KMH = 25.0      # average Chennai road speed
HANDLING_MIN = 15.0        # packing + cold-chain handover
MAX_TRAVEL_MIN = 90.0      # do not recommend transfers longer than this
MIN_DAYS_LEFT = 7          # a unit must have >= 7 days of shelf life left to be sent
UNMET_PENALTY = {"High": 600.0, "Medium": 300.0, "Low": 150.0}   # minutes per unmet unit
GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Red-cell compatibility: recipient group -> donor groups in order of preference
COMPAT = {"A+": ["A+", "A-", "O+", "O-"], "A-": ["A-", "O-"],
          "B+": ["B+", "B-", "O+", "O-"], "B-": ["B-", "O-"],
          "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
          "AB-": ["AB-", "A-", "B-", "O-"], "O+": ["O+", "O-"], "O-": ["O-"]}

risk = pd.read_csv(OUT_DIR / "blood_risk.csv")
batches = pd.read_csv(SIM_DIR / "blood_inventory_batches.csv")
hosp = pd.read_csv(SIM_DIR / "chennai_hospitals.csv").set_index("hospital_id")
name = hosp["name"].to_dict()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2)
    return 2 * r * np.arcsin(np.sqrt(a))


def travel_minutes(a, b):
    """Travel time between two hospital_ids. REPLACE with the Module 4 matrix when ready."""
    km = haversine_km(hosp.loc[a, "latitude"], hosp.loc[a, "longitude"],
                      hosp.loc[b, "latitude"], hosp.loc[b, "longitude"])
    return km * ROAD_FACTOR / CITY_SPEED_KMH * 60.0 + HANDLING_MIN


# ---------------------------------------------------------------------------
# Supply and demand per hospital x group
# ---------------------------------------------------------------------------
# Units that still have enough shelf life to be worth sending
ok_units = (batches[batches["days_to_expiry"] >= MIN_DAYS_LEFT]
            .groupby(["hospital_id", "blood_group"])["units"].sum())

risk["deficit"] = np.ceil(risk["deficit_units"] - 1e-9).astype(int)
risk["sendable_surplus"] = np.floor(risk["surplus_units"] + 1e-9)
risk["sendable_surplus"] = np.minimum(
    np.minimum(risk["sendable_surplus"], risk["stock_now"].round()),
    [ok_units.get((h, g), 0) for h, g in zip(risk.hospital_id, risk.blood_group)]).astype(int)
# A hospital that itself has a deficit never ships out that group
risk.loc[risk["deficit"] > 0, "sendable_surplus"] = 0
risk["risk_level"] = pd.Categorical(risk["risk_level"], ["High", "Medium", "Low"], ordered=True)

pairs_cache = {}


def tmin(a, b):
    if (a, b) not in pairs_cache:
        pairs_cache[(a, b)] = travel_minutes(a, b)
    return pairs_cache[(a, b)]


def reason_text(r_to, src, units, g):
    return (f"{name[r_to.hospital_id]}: {r_to.risk_level} risk for {g} "
            f"({r_to.days_of_cover:.1f} days of cover, short by {r_to.deficit} units); "
            f"{name[src.hospital_id]} has {int(src.sendable_surplus)} spare units above its safety stock")


# ---------------------------------------------------------------------------
# Version 1: rule-based (urgent first, nearest supplier)
# ---------------------------------------------------------------------------
def rule_based():
    out, left = [], {}
    for g in GROUPS:
        sup = risk[(risk.blood_group == g) & (risk.sendable_surplus > 0)]
        for r in sup.itertuples():
            left[(r.hospital_id, g)] = int(r.sendable_surplus)
        rec = (risk[(risk.blood_group == g) & (risk.deficit > 0)]
               .sort_values(["risk_level", "deficit"], ascending=[True, False]))
        for r in rec.itertuples():
            need = int(r.deficit)
            cand = sorted([s for s in sup.itertuples() if left[(s.hospital_id, g)] > 0],
                          key=lambda s: tmin(s.hospital_id, r.hospital_id))
            for s in cand:
                t = tmin(s.hospital_id, r.hospital_id)
                if need <= 0 or t > MAX_TRAVEL_MIN:
                    break
                send = min(need, left[(s.hospital_id, g)])
                left[(s.hospital_id, g)] -= send
                need -= send
                out.append(dict(from_hospital=s.hospital_id, to_hospital=r.hospital_id,
                                blood_group=g, units=send, travel_minutes=round(t, 0)))
    return pd.DataFrame(out, columns=["from_hospital", "to_hospital", "blood_group",
                                      "units", "travel_minutes"])


# ---------------------------------------------------------------------------
# Version 2: integer transportation problem per blood group
# ---------------------------------------------------------------------------
def optimise():
    out, leftover = [], {}
    for g in GROUPS:
        sup = risk[(risk.blood_group == g) & (risk.sendable_surplus > 0)].reset_index(drop=True)
        rec = risk[(risk.blood_group == g) & (risk.deficit > 0)].reset_index(drop=True)
        for r in sup.itertuples():
            leftover[(r.hospital_id, g)] = int(r.sendable_surplus)
        if sup.empty or rec.empty:
            continue
        ns, nr = len(sup), len(rec)
        nx = ns * nr
        T = np.array([[tmin(s, r) for r in rec.hospital_id] for s in sup.hospital_id])
        allowed = T <= MAX_TRAVEL_MIN
        c = np.concatenate([T.ravel(),
                            [UNMET_PENALTY[str(x)] for x in rec["risk_level"]]])
        ub = np.concatenate([
            np.where(allowed, np.minimum(sup.sendable_surplus.values[:, None],
                                         rec.deficit.values[None, :]), 0).ravel(),
            rec.deficit.values]).astype(float)
        A = lil_matrix((ns + nr, nx + nr))
        for i in range(ns):
            for j in range(nr):
                A[i, i * nr + j] = 1
        for j in range(nr):
            for i in range(ns):
                A[ns + j, i * nr + j] = 1
            A[ns + j, nx + j] = 1
        lo = np.concatenate([np.full(ns, -np.inf), rec.deficit.values.astype(float)])
        hi = np.concatenate([sup.sendable_surplus.values.astype(float),
                             rec.deficit.values.astype(float)])
        res = milp(c, constraints=LinearConstraint(A.tocsr(), lo, hi),
                   integrality=np.ones(nx + nr), bounds=Bounds(np.zeros(nx + nr), ub))
        if not res.success:
            print(f"  warning: optimiser failed for {g} ({res.message}); skipped")
            continue
        x = np.rint(res.x[:nx]).reshape(ns, nr)
        for i in range(ns):
            for j in range(nr):
                if x[i, j] > 0:
                    s, r = sup.iloc[i], rec.iloc[j]
                    leftover[(s.hospital_id, g)] -= int(x[i, j])
                    out.append(dict(from_hospital=s.hospital_id, to_hospital=r.hospital_id,
                                    blood_group=g, units=int(x[i, j]),
                                    travel_minutes=round(T[i, j], 0),
                                    type="primary",
                                    reason=reason_text(r, s, int(x[i, j]), g)))
    return pd.DataFrame(out), leftover


v1 = rule_based()
v2, leftover = optimise()
print(f"Rule-based: {len(v1)} transfers | Optimised: {len(v2)} transfers")


# ---------------------------------------------------------------------------
# Secondary: compatible-group substitutes for deficits still unmet
# ---------------------------------------------------------------------------
def remaining_deficit(plan):
    got = (plan.groupby(["to_hospital", "blood_group"])["units"].sum()
           if len(plan) else pd.Series(dtype=float))
    d = risk[risk.deficit > 0].copy()
    d["remaining"] = [max(int(r.deficit) - int(got.get((r.hospital_id, r.blood_group), 0)), 0)
                      for r in d.itertuples()]
    return d


rem = remaining_deficit(v2)
subs = []
for r in rem[(rem.remaining > 0) & (rem.risk_level == "High")].itertuples():
    need = int(r.remaining)
    for donor in COMPAT[r.blood_group][1:]:
        if need <= 0:
            break
        cands = sorted([(h, u) for (h, gg), u in leftover.items() if gg == donor and u > 0
                        and h != r.hospital_id and tmin(h, r.hospital_id) <= MAX_TRAVEL_MIN],
                       key=lambda hu: tmin(hu[0], r.hospital_id))
        for h, u in cands:
            if need <= 0:
                break
            send = min(need, u)
            leftover[(h, donor)] -= send
            need -= send
            t = tmin(h, r.hospital_id)
            subs.append(dict(from_hospital=h, to_hospital=r.hospital_id, blood_group=donor,
                             units=send, travel_minutes=round(t, 0), type="substitute",
                             reason=(f"SECONDARY SUGGESTION: {name[r.hospital_id]} is short of "
                                     f"{r.blood_group}; {donor} red cells are compatible. "
                                     f"Needs clinician approval and cross-match.")))
sub_df = pd.DataFrame(subs)

transfers = pd.concat([v2, sub_df], ignore_index=True) if len(sub_df) else v2.copy()
if len(transfers):
    transfers.insert(1, "from_name", transfers["from_hospital"].map(name))
    transfers.insert(3, "to_name", transfers["to_hospital"].map(name))
    transfers = transfers[["from_hospital", "from_name", "to_hospital", "to_name", "blood_group",
                           "units", "travel_minutes", "type", "reason"]]
    transfers = transfers.sort_values(["type", "to_hospital", "blood_group"])
transfers.to_csv(OUT_DIR / "blood_transfers.csv", index=False)
v1.to_csv(OUT_DIR / "blood_transfers_rulebased.csv", index=False)


# ---------------------------------------------------------------------------
# Summary and comparison
# ---------------------------------------------------------------------------
def stats(plan):
    if not len(plan):
        return 0, 0.0, 0.0
    u = plan["units"].sum()
    return int(u), float((plan["units"] * plan["travel_minutes"]).sum() / u), float(
        (plan["units"] * plan["travel_minutes"]).sum())


total_def = int(risk["deficit"].sum())
total_sup = int(risk["sendable_surplus"].sum())
rows = []
for label, plan in [("Rule-based (nearest first)", v1), ("Optimised (MILP)", v2)]:
    u, avg, tot = stats(plan)
    rows.append((label, u, total_def - u, round(avg, 1), round(tot, 0)))
cmp_df = pd.DataFrame(rows, columns=["method", "units_moved", "deficit_left_unmet",
                                     "avg_travel_min_per_unit", "total_unit_minutes"])
rem2 = remaining_deficit(v2)
hi_left = rem2[(rem2.risk_level == "High") & (rem2.remaining > 0)]
sub_units = int(sub_df["units"].sum()) if len(sub_df) else 0

lines = ["REDISTRIBUTION SUMMARY", "",
         f"Total deficit: {total_def} units | total sendable surplus: {total_sup} units",
         f"Max transfer time {MAX_TRAVEL_MIN:.0f} min, min shelf life {MIN_DAYS_LEFT} days, "
         f"travel time = straight line x {ROAD_FACTOR} / {CITY_SPEED_KMH:.0f} km/h + {HANDLING_MIN:.0f} min",
         "", "Method comparison:", cmp_df.to_string(index=False), "",
         f"Substitute (secondary) suggestions: {sub_units} units",
         f"High-risk deficits still unmet after optimisation: "
         f"{int(hi_left['remaining'].sum()) if len(hi_left) else 0} units"]
if len(hi_left):
    lines.append("Still short (need regional blood centre / camp):")
    for r in hi_left.sort_values("remaining", ascending=False).head(10).itertuples():
        lines.append(f"  {name[r.hospital_id]} - {r.blood_group}: {r.remaining} units")
lines += ["", "NOTE: travel time is an approximation until Module 4's road matrix is plugged in."]
text = "\n".join(lines)
print("\n" + text)
(OUT_DIR / "blood_transfer_summary.txt").write_text(text, encoding="utf-8")
print("\nSaved outputs\\blood_transfers.csv, blood_transfers_rulebased.csv, blood_transfer_summary.txt")