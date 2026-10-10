"""
Module 4 - Emergency Coverage & Referral Intelligence - DASHBOARD (redesigned)
--------------------------------------------------------------------------------
What's new in this design:
  * Interactive map (Leaflet) is the main view. Click a zone in the list and the
    map flies to it. Needs internet for the map tiles.
  * Each zone shows its travel time as a bar against the 20-minute limit.
  * Tabs: Recommended fixes, Hospitals, About the data.
  * Light clinical theme instead of the dark console look.

Data it reads (all in ../data/simulated/):
  chennai_hotspot_zones.csv, chennai_hospitals.csv,
  chennai_coverage_results_LIVE.csv  (falls back to _APPROX.csv),
  chennai_recommendations.csv        (made by recommend_actions.py)

Run:
    streamlit run module4_dashboard_full.py
Requires:
    pip install streamlit pandas
    pip install streamlit-autorefresh      (only for Live Simulation Mode)
"""

import html as html_lib
import json
import math
import os
import random

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# PATHS + SETTINGS
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "simulated")
ZONES_PATH = os.path.join(DATA_DIR, "chennai_hotspot_zones.csv")
HOSPITALS_PATH = os.path.join(DATA_DIR, "chennai_hospitals.csv")
LIVE_PATH = os.path.join(DATA_DIR, "chennai_coverage_results_LIVE.csv")
APPROX_PATH = os.path.join(DATA_DIR, "chennai_coverage_results_APPROX.csv")
RECS_PATH = os.path.join(DATA_DIR, "chennai_recommendations.csv")

SAFE_WINDOW = 20
USING_LIVE = os.path.exists(LIVE_PATH)
COVERAGE_PATH = LIVE_PATH if USING_LIVE else APPROX_PATH

st.set_page_config(page_title="Emergency coverage - Chennai", layout="wide")

# Make the Streamlit shell match the light theme and remove its chrome
st.markdown("""
<style>
  .stApp { background:#EEF1EF; }
  header[data-testid="stHeader"], #MainMenu, footer { display:none !important; }
  .block-container { padding:1rem 1.5rem 2rem; max-width:1320px; }
  .stApp label, .stApp p, .stApp span { color:#12262D; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# LIVE SIMULATION TOGGLE
# (Simulated fluctuation on top of real base data. No public API gives live
#  hospital telemetry, so this is a demo feature, labeled as such.)
# ---------------------------------------------------------------------------
c1, c2 = st.columns([1.2, 5])
with c1:
    live_mode = st.toggle("Live simulation", value=False)
with c2:
    st.caption("Adds small random changes to travel times every 6 seconds for demos. It is not real hospital data."
               if live_mode else "Showing your saved results. Turn on live simulation for a demo-style auto-refresh.")

refresh_count = 0
if live_mode:
    try:
        from streamlit_autorefresh import st_autorefresh
        refresh_count = st_autorefresh(interval=6000, limit=None, key="m4_refresh")
    except ImportError:
        st.warning("Live simulation needs one extra package: pip install streamlit-autorefresh")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------
try:
    zones = pd.read_csv(ZONES_PATH)
    hospitals = pd.read_csv(HOSPITALS_PATH)
    coverage = pd.read_csv(COVERAGE_PATH)
except FileNotFoundError as err:
    st.error(f"Missing data file: {err}")
    st.stop()

recs = pd.read_csv(RECS_PATH) if os.path.exists(RECS_PATH) else None

nearest_col = "nearest_capable_min" if "nearest_capable_min" in coverage.columns else "nearest_capable_min_APPROX"
any_col = next((c for c in ("nearest_hospital_any_min", "nearest_any_min_APPROX") if c in coverage.columns), None)

cov = coverage.sort_values("risk_score", ascending=False).reset_index(drop=True)
if live_mode:
    rng = random.Random(refresh_count)
    cov[nearest_col] = cov[nearest_col].apply(lambda t: round(max(1, t + rng.uniform(-2.5, 2.5)), 1))
    cov["coverage_status"] = cov[nearest_col].apply(lambda t: "COVERED" if t <= SAFE_WINDOW else "GAP")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def esc(x):
    return html_lib.escape("" if x is None else str(x))

def py(v):
    """Make pandas/numpy values JSON-safe; NaN -> None."""
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


# ---------------------------------------------------------------------------
# BUILD ZONE RECORDS
# ---------------------------------------------------------------------------
zone_info = zones.set_index("zone_id")
hosp_xy = hospitals.set_index("name")[["latitude", "longitude"]]
recs_by_zone = {}
if recs is not None:
    for _, r in recs.iterrows():
        recs_by_zone[r["zone_id"]] = {k: py(v) for k, v in r.items()}

zone_list = []
for _, row in cov.iterrows():
    zid = row["zone_id"]
    zi = zone_info.loc[zid]
    capable = py(row.get("nearest_capable_hospital"))
    hlat = hlon = None
    if capable in hosp_xy.index:
        hlat, hlon = float(hosp_xy.loc[capable, "latitude"]), float(hosp_xy.loc[capable, "longitude"])
    any_min = py(row[any_col]) if any_col else None
    zone_list.append({
        "id": zid,
        "area": str(zi["dominant_area"]),
        "lat": float(zi["centroid_lat"]), "lon": float(zi["centroid_lon"]),
        "risk": float(row["risk_score"]),
        "accidents": int(zi["accident_count"]), "fatal": int(zi["fatal_count"]),
        "status": row["coverage_status"],
        "mins": float(row[nearest_col]),
        "hosp": capable, "hlat": hlat, "hlon": hlon,
        "any_hosp": py(row.get("nearest_hospital_any")),
        "any_min": any_min,
        "rec": recs_by_zone.get(zid),
    })

n_total = len(zone_list)
n_gap = sum(1 for z in zone_list if z["status"] == "GAP")
all_mins = [z["mins"] for z in zone_list]
for z in zone_list:
    if z["rec"] and z["rec"].get("projected_definitive_min") is not None:
        all_mins.append(float(z["rec"]["projected_definitive_min"]))
SCALE = max(40, int(math.ceil(max(all_mins) / 10.0) * 10))

def pct(m):
    return min(100.0, float(m) / SCALE * 100.0)

LIMIT_POS = pct(SAFE_WINDOW)

# Hospital records (+ how many zones each one serves, + upgrade candidates)
serves = {}
for z in zone_list:
    if z["hosp"]:
        serves[z["hosp"]] = serves.get(z["hosp"], 0) + 1
upgrade_names = {z["rec"]["upgrade_candidate"] for z in zone_list
                 if z["rec"] and z["rec"].get("upgrade_candidate")}

hosp_records = []
for _, h in hospitals.iterrows():
    hosp_records.append({
        "name": h["name"], "lat": float(h["latitude"]), "lon": float(h["longitude"]),
        "tier": int(h["trauma_tier"]), "icu": int(h["icu_beds"]),
        "cath": bool(h["has_cath_lab"]), "vent": bool(h["has_ventilator_bank"]),
        "serves": serves.get(h["name"], 0), "upgrade": h["name"] in upgrade_names,
    })

# ---------------------------------------------------------------------------
# HEADLINE TEXT
# ---------------------------------------------------------------------------
if n_gap == 0:
    headline = f"All {n_total} high-risk zones are within {SAFE_WINDOW} minutes of a trauma-capable hospital."
else:
    headline = f"{n_gap} of {n_total} high-risk zones are more than {SAFE_WINDOW} minutes from a trauma-capable hospital."

worst = max(zone_list, key=lambda z: z["mins"])
sub_parts = [f"Slowest: {worst['area']} at {worst['mins']:.1f} minutes."]
if recs is not None:
    gap_recs = [z["rec"] for z in zone_list if z["status"] == "GAP" and z["rec"]]
    closed = sum(1 for r in gap_recs if r.get("projected_status") == "COVERED")
    improved = sum(1 for r in gap_recs if r.get("projected_status") == "IMPROVED")
    newfac = len(gap_recs) - closed - improved
    if gap_recs:
        sub_parts.append(f"The recommended fixes close {closed}, improve {improved}, and {newfac} need a new facility.")
subline = " ".join(sub_parts)

# ---------------------------------------------------------------------------
# HTML FRAGMENTS BUILT IN PYTHON
# ---------------------------------------------------------------------------
def bar(minutes, cls):
    return (f'<div class="tbar"><i class="fill {cls}" style="width:{pct(minutes):.1f}%"></i>'
            f'<b class="mark" style="left:{LIMIT_POS:.1f}%"></b></div>')

def status_cls(status):
    return "gap" if status == "GAP" else "ok"

def status_label(status):
    return "Gap" if status == "GAP" else "Covered"

zone_rows = ""
for z in zone_list:
    cls = status_cls(z["status"])
    zone_rows += f"""
    <button class="zrow" data-id="{esc(z['id'])}" onclick="selectZone('{esc(z['id'])}', true)">
      <span class="zrow-top"><span class="zname">{esc(z['area'])}</span><span class="chip {cls}">{status_label(z['status'])}</span></span>
      {bar(z['mins'], cls)}
      <span class="zmin"><b>{z['mins']:.1f} min</b> to {esc(z['hosp'] or 'no capable hospital')}</span>
    </button>"""

REC_STYLE = {
    "COVERED": ("ok", "Closes the gap"),
    "IMPROVED": ("warn", "Improves it, still over the limit"),
}

def rec_style(status):
    return REC_STYLE.get(status, ("gap", "Needs a new facility"))

fix_cards = ""
if recs is None:
    fix_cards = ('<div class="empty">No recommendations yet. Run <code>python scripts\\recommend_actions.py</code> '
                 'and reload this page.</div>')
else:
    for z in zone_list:
        r = z["rec"]
        if z["status"] != "GAP" or not r:
            continue
        cls, label = rec_style(r.get("projected_status"))
        after = float(r["projected_definitive_min"])
        post = r.get("post_first_care_min")
        post_txt = (f'<p class="note">An ambulance post would give first care in about {int(float(post))} minutes. '
                    f'This figure is an assumption.</p>') if post not in (None, "") else ""
        fix_cards += f"""
        <article class="fix">
          <header><h4>{esc(z['area'])}</h4><span class="chip {cls}">{label}</span></header>
          <p class="act">{esc(r['recommended_action'])}</p>
          <div class="ba"><span class="ba-l">Now</span>{bar(z['mins'], 'gap')}<span class="ba-v">{z['mins']:.1f} min</span></div>
          <div class="ba"><span class="ba-l">After</span>{bar(after, cls)}<span class="ba-v">{after:.1f} min</span></div>
          {post_txt}
        </article>"""
    if not fix_cards:
        fix_cards = '<div class="empty">No gap zones, so no fixes are needed.</div>'

hosp_rows = ""
for h in sorted(hosp_records, key=lambda x: (x["tier"], -x["serves"], x["name"])):
    tag = ' <span class="chip warn">Upgrade candidate</span>' if h["upgrade"] else ""
    hosp_rows += f"""
    <tr>
      <td>{esc(h['name'])}{tag}</td>
      <td><span class="tier t{h['tier']}">Tier {h['tier']}</span></td>
      <td class="num">{h['icu']}</td>
      <td>{'Yes' if h['cath'] else 'No'}</td>
      <td>{'Yes' if h['vent'] else 'No'}</td>
      <td class="num">{h['serves']}</td>
    </tr>"""

pulled = ""
if "data_pulled_at" in coverage.columns:
    pulled = f"Travel times were pulled on {esc(coverage['data_pulled_at'].iloc[0])}. Traffic changes through the day, so a different time can give different results."
routing_note = ("Travel times come from TomTom's routing service with live traffic."
                if USING_LIVE else
                "Travel times are rough estimates (straight-line distance with a traffic factor). Run compute_travel_time.py for real routing.")

notes_html = f"""
<ul class="notes">
  <li><b>Accident locations are simulated.</b> India does not publish crash coordinates, so points were scattered around six known accident-prone junctions. Severity mix follows real 2023 Tamil Nadu totals.</li>
  <li><b>The six zones were planted.</b> Finding six clusters is expected. The useful result is the coverage analysis, not the clustering.</li>
  <li><b>Hospital capabilities are simulated.</b> Names and locations are real. ICU beds, cath labs and ventilators are estimates.</li>
  <li><b>{esc(routing_note)}</b> {pulled}</li>
  <li><b>The ambulance-post time (8 minutes) is an assumption.</b> A post shortens time to first care, not time to the hospital.</li>
  <li><b>Map lines are straight lines,</b> not the road route. The times shown are for the real road route.</li>
</ul>"""

map_data = {
    "safe": SAFE_WINDOW, "scale": SCALE, "limit": LIMIT_POS,
    "zones": zone_list, "hospitals": hosp_records,
}
data_json = json.dumps(map_data).replace("</", "<\\/")
source_label = "Live traffic routing" if USING_LIVE else "Estimated routing"
mode_label = "Live simulation on" if live_mode else "Saved results"

# ---------------------------------------------------------------------------
# PAGE TEMPLATE
# ---------------------------------------------------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#EEF1EF; --card:#FFFFFF; --ink:#12262D; --ink2:#4B6068; --line:#D5DDDA;
    --gap:#C93A24; --gap-bg:#FBE9E5; --ok:#1C8160; --ok-bg:#E3F3EC;
    --warn:#A86F00; --warn-bg:#FAF0D6; --hosp:#2554C7;
    --sans:'Schibsted Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-variant-numeric:tabular-nums;line-height:1.45}
  .shell{max-width:1280px;margin:0 auto;padding:8px 6px 28px}
  button{font:inherit;color:inherit}
  button:focus-visible,.tab:focus-visible{outline:3px solid var(--hosp);outline-offset:2px}

  .top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:6px}
  .kicker{font-size:13px;color:var(--ink2);font-weight:500}
  .meta{display:flex;gap:8px;flex-wrap:wrap}
  .pill{font-size:12px;font-weight:600;padding:5px 11px;border-radius:999px;background:#fff;border:1px solid var(--line);color:var(--ink2)}
  h1{font-size:clamp(26px,3.4vw,40px);line-height:1.12;font-weight:800;letter-spacing:-0.02em;max-width:26ch;margin:6px 0 10px}
  .lede{font-size:16px;color:var(--ink2);max-width:62ch;margin-bottom:22px}

  .main{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,1fr);gap:18px;align-items:start}
  .mapwrap{position:relative;border-radius:20px;overflow:hidden;border:1px solid var(--line);background:#DDE6E3;height:660px}
  #map{position:absolute;inset:0}
  .maperr{position:absolute;inset:0;display:none;align-items:center;justify-content:center;text-align:center;padding:30px;color:var(--ink2);font-weight:500}
  .legend{position:absolute;left:12px;bottom:12px;z-index:1000;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:12px;display:grid;gap:6px}
  .legend div{display:flex;align-items:center;gap:8px}
  .sw{width:12px;height:12px;border-radius:50%;display:inline-block}
  .sw.sq{border-radius:3px}
  .sw.ln{width:18px;height:0;border-top:2px dashed var(--ink2);border-radius:0}

  .side{display:grid;gap:14px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px}
  .panel-h{display:flex;justify-content:space-between;align-items:baseline;margin:2px 4px 10px}
  .panel-h h2{font-size:15px;font-weight:700}
  .panel-h span{font-size:12px;color:var(--ink2)}
  .zrow{display:grid;gap:7px;width:100%;text-align:left;background:transparent;border:1px solid transparent;border-radius:12px;padding:10px;cursor:pointer}
  .zrow:hover{background:#F5F8F7}
  .zrow.sel{background:#F0F5F3;border-color:var(--ink)}
  .zrow-top{display:flex;justify-content:space-between;align-items:center;gap:10px}
  .zname{font-weight:700;font-size:14.5px}
  .zmin{font-size:12.5px;color:var(--ink2)}
  .zmin b{color:var(--ink)}

  .chip{font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}
  .chip.gap{background:var(--gap-bg);color:var(--gap)}
  .chip.ok{background:var(--ok-bg);color:var(--ok)}
  .chip.warn{background:var(--warn-bg);color:var(--warn)}

  .tbar{position:relative;height:10px;background:#E6ECEA;border-radius:5px;overflow:visible}
  .tbar .fill{display:block;height:100%;border-radius:5px}
  .fill.gap{background:var(--gap)} .fill.ok{background:var(--ok)} .fill.warn{background:#D9A21B}
  .tbar .mark{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink);border-radius:1px}

  .detail h3{font-size:18px;font-weight:800;margin-bottom:2px}
  .detail .sub{font-size:13px;color:var(--ink2);margin-bottom:12px}
  .kv{display:grid;grid-template-columns:auto 1fr;gap:7px 14px;font-size:13.5px}
  .kv dt{color:var(--ink2)} .kv dd{font-weight:600;text-align:right}
  .fixbox{margin-top:14px;padding:12px;border-radius:12px;background:#F5F8F7;font-size:13.5px}
  .fixbox b{display:block;margin-bottom:3px}

  .tabs{margin-top:26px}
  .tablist{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:18px}
  .tab{background:none;border:none;border-bottom:3px solid transparent;padding:10px 16px;font-weight:700;font-size:14.5px;color:var(--ink2);cursor:pointer;margin-bottom:-1px}
  .tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink)}
  .pane{display:none} .pane.show{display:block}

  .fixes{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
  .fix{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
  .fix header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}
  .fix h4{font-size:17px;font-weight:800}
  .fix .act{font-size:14.5px;margin-bottom:14px}
  .ba{display:grid;grid-template-columns:44px 1fr 62px;align-items:center;gap:10px;margin-bottom:10px;font-size:13px}
  .ba-l{color:var(--ink2);font-weight:600} .ba-v{font-weight:700;text-align:right}
  .note{font-size:12.5px;color:var(--ink2);margin-top:6px}

  .tablewrap{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:14px;min-width:620px}
  th{text-align:left;font-size:12.5px;color:var(--ink2);font-weight:600;padding:12px 14px;border-bottom:1px solid var(--line)}
  td{padding:11px 14px;border-bottom:1px solid #EAF0EE}
  tr:last-child td{border-bottom:none}
  td.num,th.num{text-align:right}
  .tier{font-size:12px;font-weight:700;padding:3px 9px;border-radius:6px;background:#E8EEF9;color:var(--hosp)}
  .tier.t2{background:#EEF1EF;color:var(--ink2)} .tier.t3{background:var(--warn-bg);color:var(--warn)}

  .notes{display:grid;gap:12px;list-style:none;max-width:78ch}
  .notes li{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px}
  .empty{background:var(--card);border:1px dashed var(--line);border-radius:14px;padding:22px;color:var(--ink2)}
  code{background:#E6ECEA;padding:2px 6px;border-radius:5px;font-size:13px}

  .leaflet-tooltip{font-family:var(--sans);font-weight:600;border-radius:8px}
  @media (max-width:900px){.main{grid-template-columns:1fr}.mapwrap{height:460px}}
</style></head>
<body><div class="shell">

  <div class="top">
    <div class="kicker">Chennai accident hotspots and emergency coverage</div>
    <div class="meta"><span class="pill">__SOURCE__</span><span class="pill">__MODE__</span><span class="pill">__NHOSP__ hospitals</span></div>
  </div>
  <h1>__HEADLINE__</h1>
  <p class="lede">__SUBLINE__</p>

  <div class="main">
    <div class="mapwrap">
      <div id="map"></div>
      <div class="maperr" id="maperr">The map could not load. It needs an internet connection for map tiles. The list and tabs still work.</div>
      <div class="legend">
        <div><span class="sw" style="background:var(--gap)"></span>Zone over the limit</div>
        <div><span class="sw" style="background:var(--ok)"></span>Zone within the limit</div>
        <div><span class="sw sq" style="background:var(--hosp)"></span>Hospital</div>
        <div><span class="sw ln"></span>Nearest trauma-capable hospital</div>
      </div>
    </div>

    <div class="side">
      <section class="panel">
        <div class="panel-h"><h2>Zones by risk</h2><span>Black line = __SAFE__ minute limit</span></div>
        __ZONEROWS__
      </section>
      <section class="panel detail" id="detail" aria-live="polite"></section>
    </div>
  </div>

  <div class="tabs">
    <div class="tablist" role="tablist">
      <button class="tab" role="tab" id="t-fixes" aria-selected="true" onclick="showTab('fixes')">Recommended fixes</button>
      <button class="tab" role="tab" id="t-hosp" aria-selected="false" onclick="showTab('hosp')">Hospitals</button>
      <button class="tab" role="tab" id="t-notes" aria-selected="false" onclick="showTab('notes')">About the data</button>
    </div>
    <div class="pane show" id="p-fixes"><div class="fixes">__FIXES__</div></div>
    <div class="pane" id="p-hosp"><div class="tablewrap"><table>
      <thead><tr><th>Hospital</th><th>Trauma tier</th><th class="num">ICU beds</th><th>Cath lab</th><th>Ventilators</th><th class="num">Zones served</th></tr></thead>
      <tbody>__HOSPROWS__</tbody></table></div></div>
    <div class="pane" id="p-notes">__NOTES__</div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
const D = __DATA__;
const byId = Object.fromEntries(D.zones.map(z => [z.id, z]));
const markers = {};
let map = null;

function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
const REC = { COVERED:['ok','Closes the gap'], IMPROVED:['warn','Improves it, still over the limit'] };

function renderDetail(z){
  const gap = z.status === 'GAP';
  let h = '<h3>' + esc(z.area) + '</h3>';
  h += '<p class="sub">' + esc(z.id) + ', ' + z.accidents + ' simulated accidents, ' + z.fatal + ' fatal, risk score ' + z.risk + '</p>';
  h += '<dl class="kv">';
  h += '<dt>Status</dt><dd><span class="chip ' + (gap ? 'gap' : 'ok') + '">' + (gap ? 'Gap' : 'Covered') + '</span></dd>';
  h += '<dt>Nearest trauma-capable hospital</dt><dd>' + esc(z.hosp || 'None found') + '</dd>';
  h += '<dt>Travel time</dt><dd>' + z.mins.toFixed(1) + ' min</dd>';
  if (z.any_hosp && z.any_hosp !== z.hosp) {
    h += '<dt>Closest hospital of any tier</dt><dd>' + esc(z.any_hosp) + ', ' + Number(z.any_min).toFixed(1) + ' min</dd>';
    h += '<dt>Delay from skipping it</dt><dd>' + (z.mins - z.any_min).toFixed(1) + ' min</dd>';
  }
  h += '</dl>';
  if (z.rec && gap) {
    const st = REC[z.rec.projected_status] || ['gap','Needs a new facility'];
    h += '<div class="fixbox"><b>Recommended fix</b>' + esc(z.rec.recommended_action) +
         '<div style="margin-top:8px"><span class="chip ' + st[0] + '">' + st[1] + '</span> ' +
         Number(z.rec.projected_definitive_min).toFixed(1) + ' min after the fix</div></div>';
  } else if (!gap) {
    h += '<div class="fixbox"><b>No action needed</b>This zone is within the ' + D.safe + ' minute limit.</div>';
  }
  document.getElementById('detail').innerHTML = h;
}

function selectZone(id, fly){
  const z = byId[id]; if (!z) return;
  document.querySelectorAll('.zrow').forEach(r => r.classList.toggle('sel', r.dataset.id === id));
  renderDetail(z);
  if (map && fly) {
    map.flyTo([z.lat, z.lon], 13, {duration: 0.8});
    if (markers[id]) markers[id].openTooltip();
  }
}

function showTab(name){
  ['fixes','hosp','notes'].forEach(n => {
    document.getElementById('p-' + n).classList.toggle('show', n === name);
    document.getElementById('t-' + n).setAttribute('aria-selected', n === name ? 'true' : 'false');
  });
}

function initMap(){
  if (typeof L === 'undefined') { document.getElementById('maperr').style.display = 'flex'; return; }
  map = L.map('map', {zoomControl: true, scrollWheelZoom: false});
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 18, attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
  }).addTo(map);

  const risks = D.zones.map(z => z.risk), rmin = Math.min(...risks), rmax = Math.max(...risks);
  const bounds = [];

  D.zones.forEach(z => {
    if (z.hlat != null) {
      L.polyline([[z.lat, z.lon], [z.hlat, z.hlon]], {
        color: z.status === 'GAP' ? '#C93A24' : '#1C8160',
        weight: z.status === 'GAP' ? 3 : 2, opacity: .7, dashArray: '6 6'
      }).addTo(map);
    }
  });

  D.hospitals.forEach(h => {
    const size = h.tier === 1 ? 14 : 11;
    const icon = L.divIcon({
      className: '',
      html: '<div style="width:' + size + 'px;height:' + size + 'px;background:#2554C7;border:2px solid #fff;border-radius:3px;' +
            (h.upgrade ? 'box-shadow:0 0 0 3px #D9A21B;' : 'box-shadow:0 0 0 1px rgba(0,0,0,.25);') + '"></div>',
      iconSize: [size, size]
    });
    L.marker([h.lat, h.lon], {icon}).addTo(map)
      .bindTooltip(esc(h.name) + ', tier ' + h.tier + (h.upgrade ? ' (upgrade candidate)' : ''));
    bounds.push([h.lat, h.lon]);
  });

  D.zones.forEach(z => {
    const r = 10 + (z.risk - rmin) / (rmax - rmin + 1e-9) * 8;
    const m = L.circleMarker([z.lat, z.lon], {
      radius: r, color: '#fff', weight: 2, fillOpacity: .92,
      fillColor: z.status === 'GAP' ? '#C93A24' : '#1C8160'
    }).addTo(map).bindTooltip(esc(z.area) + ', ' + z.mins.toFixed(1) + ' min');
    m.on('click', () => selectZone(z.id, false));
    markers[z.id] = m;
    bounds.push([z.lat, z.lon]);
  });

  map.fitBounds(bounds, {padding: [30, 30]});
}

initMap();
const first = D.zones.find(z => z.status === 'GAP') || D.zones[0];
if (first) selectZone(first.id, false);
</script>
</body></html>
"""

page = (TEMPLATE
        .replace("__SOURCE__", esc(source_label))
        .replace("__MODE__", esc(mode_label))
        .replace("__NHOSP__", str(len(hosp_records)))
        .replace("__HEADLINE__", esc(headline))
        .replace("__SUBLINE__", esc(subline))
        .replace("__SAFE__", str(SAFE_WINDOW))
        .replace("__ZONEROWS__", zone_rows)
        .replace("__FIXES__", fix_cards)
        .replace("__HOSPROWS__", hosp_rows)
        .replace("__NOTES__", notes_html)
        .replace("__DATA__", data_json))

components.html(page, height=1600, scrolling=True)

if recs is not None:
    st.download_button("Download recommendations (CSV)", data=recs.to_csv(index=False),
                       file_name="chennai_recommendations.csv", mime="text/csv")