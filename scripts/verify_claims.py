"""Recompute every headline claim in docs/presentation.md from the stored outputs and write docs/evidence.md.

Each claim is read (or recomputed from rasters) from: data/processed/analyses/<id>/result.json and *.tif,
data/reference/diagnostics_<id>.json, nisar_season_<area>.json, swot_<area>.json, rainfall_<area>.json,
soil_moisture_<area>.json. Usage: .venv/bin/python scripts/verify_claims.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
rows: list[tuple[str, str, str, str]] = []  # slide, claim, value, source


def res(aid):
    return json.loads((D / f"processed/analyses/{aid}/result.json").read_text())


def ref(name):
    return json.loads((D / f"reference/{name}.json").read_text())


def add(slide, claim, value, source):
    rows.append((slide, claim, value, source))


m = res("sylhet_monsoon")
w = m["water"]
with rasterio.open(D / "processed/analyses/sylhet_monsoon/water_change.tif") as s:
    wc = s.read(1)
    px = abs(s.transform.a * s.transform.e) / 1e6
lost_r, gained_r = float((wc == 4).sum() * px), float((wc == 3).sum() * px)
assert abs(lost_r - w["lost_km2"]) < 0.05 and abs(gained_r - w["gained_km2"]) < 0.05
basin = float((wc > 0).sum() * px)
add("1,4,5", "Basin analysed (valid pixels)", f"{basin:,.0f} km²", "water_change.tif (sylhet_monsoon), recomputed")
add("5", "Open water 18 Jun → 16 Oct", f"{w['earlier_km2']:,.0f} → {w['later_km2']:,.0f} km² ({100*w['earlier_fraction']:.0f}% → {100*w['later_fraction']:.0f}%)", "result.json water (sylhet_monsoon)")
add("5", "Water receded / newly flooded", f"{lost_r:.1f} km² / {gained_r:.1f} km² (raster recount matches result.json)", "water_change.tif classes 4 / 3")
add("4", "Thresholds (Otsu) and separability", f"{w['thresholds']['earlier']['threshold_db']} / {w['thresholds']['later']['threshold_db']} dB; η {w['thresholds']['earlier']['separability']} / {w['thresholds']['later']['separability']}", "result.json water.thresholds")

dg = ref("diagnostics_sylhet_monsoon")
sens = dg["D_impact"]["threshold_sensitivity"]
lo = [x["lost_km2"] for x in sens if abs(x["threshold_shift_db"]) <= 1]
cr = [x["cropland_emerged_km2"] for x in sens if abs(x["threshold_shift_db"]) <= 1]
add("5", "Receded, water threshold ±1 dB", f"{min(lo):.0f}–{max(lo):.0f} km²", "diagnostics_sylhet_monsoon D_impact.threshold_sensitivity")
add("5", "Cropland emerged (ESA WorldCover 2021 class 40)", f"{m['impact']['cropland_emerged_km2']:.1f} km² (±1 dB: {min(cr):.0f}–{max(cr):.0f})", "result.json impact; diagnostics D_impact")
add("5", "Drained area by land cover", ", ".join(f"{k} {v}" for k, v in dg["D_impact"]["drained_area_by_landcover_km2"].items()) + " km²", "diagnostics D_impact")
pop = dg["D_impact"]["population"]
add("1,7", "People living in the basin (WorldPop R2025A, modelled)", f"{pop['people_in_area']:,}", "diagnostics D_impact.population")
add("7", "Residents within 200 m / 1 km of drained land", f"{pop['people_within_distance_of_drained_land']['0.2km']:,} / {pop['people_within_distance_of_drained_land']['1km']:,} (context, not harm)", "diagnostics D_impact.population")
add("5", "Volume change (order of magnitude)", f"{m['impact']['volume_change_km3_approx']} km³", "result.json impact (mean area × median SWOT Δh)")

# single-date water-map validation (season series)
season = ref("nisar_season_sylhet_haor")["series"]
opt = [(e["date"], v["date"], v["f1"]) for e in season for v in e["validation"] if v["product"] == "DSWX_HLS"]
add("6", "Single-date water maps vs optical (DSWx-HLS), F1", "; ".join(f"{a}↔{b}: {f:.2f}" for a, b, f in opt) + f" → range {min(f for *_, f in opt):.2f}–{max(f for *_, f in opt):.2f}", "nisar_season_sylhet_haor.json")
seas = ", ".join(f"{e['date'][5:]} {100*e['water_fraction']:.0f}%" for e in season)
add("4", "NISAR open-water fraction through the season", seas, "nisar_season_sylhet_haor.json")
oa = next(a for a in m["validation"]["accuracy"] if a["product"] == "DSWX_HLS")
add("6", "16 Oct water map vs optical 17 Oct", f"F1 {oa['open_water']['f1']}, IoU {oa['open_water']['iou']}, κ {oa['open_water']['kappa']}, precision {oa['open_water']['precision']}, recall {oa['open_water']['recall']}", "result.json validation.accuracy")
ts = [x["f1"] for x in oa.get("threshold_sensitivity", [])]
if ts:
    add("6", "Threshold ±3 dB, F1 vs optical", f"{min(ts):.2f}–{max(ts):.2f}", "result.json validation.accuracy[].threshold_sensitivity")

# change validation
ca = m["validation"]["change_accuracy"]
s1f = [c["water_lost"]["f1"] for c in ca if c["product"] == "DSWX_S1"]
add("6", "Change ('water receded') F1 vs same-orbit C-band pairs", f"{min(s1f):.2f}–{max(s1f):.2f} ({len(s1f)} orbits)", "result.json validation.change_accuracy")
sa = m["validation"]["reference_change_self_agreement"]
add("6", "C-band reference agreeing with itself across orbits", f"F1 {sa['f1_min']:.2f}–{sa['f1_max']:.2f} ({sa['pairs']} pairs)", "result.json validation.reference_change_self_agreement")
A = dg["A_reference_quality"]["s1_vs_optical_same_days"]
add("6", "C-band reference vs optical, same week: water fraction", f"S1 {min(x['s1_water_fraction'] for x in A)*100:.0f}–{max(x['s1_water_fraction'] for x in A)*100:.0f}% vs optical {min(x['optical_water_fraction'] for x in A)*100:.0f}–{max(x['optical_water_fraction'] for x in A)*100:.0f}% (F1 {min(x['f1_open'] for x in A):.2f}–{max(x['f1_open'] for x in A):.2f})", "diagnostics A_reference_quality")
june = [t["reference_water_km2"][0] for t in dg["B_change_vs_s1"]]
add("6", "June open water by the four C-band orbits (≤ 7 days apart)", f"{min(june):.0f}–{max(june):.0f} km²", "diagnostics B_change_vs_s1")
rc = res("sylhet_recession")
oc = next(c for c in rc["validation"]["change_accuracy"] if c["product"] == "DSWX_HLS")
add("6", "Optical before/after (10 Sep → 16 Oct): direction agreement in changed 500 m cells; pixel F1", f"{100*oc['cells_500m']['direction_agreement_where_changed']:.0f}%; F1 {oc['water_lost']['f1']:.2f}", "result.json validation.change_accuracy (sylhet_recession)")

# SWOT
sw = m["validation"]["swot"]
add("4,6", "SWOT lake-level change, median per pass", "; ".join(f"pass {p['pass']}: {p['median_change_m']:+.2f} m, {p['lakes']} lakes, {100*p['fraction_falling']:.0f}% fell" for p in sw["passes"]), "result.json validation.swot")
aa = sw.get("area_agreement") or {}
if aa.get("status") == "available":
    add("6", "Per-lake area NISAR vs SWOT", f"r {aa['earlier_area_r']:.2f} (area), {aa['change_r']:.2f} (change), same direction {100*aa['same_sign_fraction']:.0f}%, {aa['lakes']} lakes", "result.json validation.swot.area_agreement")
cal = m["validation"]["radiometric_stability"]
add("6", "Calibration check (median ΔB on unchanged land)", f"{cal['median_delta_db']:+.2f} dB (tolerance 0.5)", "result.json validation.radiometric_stability")

# rainfall, soil moisture
try:
    rf = ref("rainfall_sylhet_haor")
    months = {}
    for d in rf.get("series", rf.get("daily", [])):
        mo = d["date"][:7]
        months[mo] = months.get(mo, 0) + (d.get("mean_mm") or 0)
    add("4", "GPM IMERG basin-mean rainfall by month", ", ".join(f"{k[5:]} {v:.0f} mm" for k, v in sorted(months.items()) if k <= "2026-10"), "rainfall_sylhet_haor.json")
except Exception as ex:  # noqa: BLE001
    add("4", "GPM rainfall", f"not recomputed ({ex})", "")

# L vs C by land cover, all sites
for aid, label in (("sylhet_monsoon", "Sylhet"), ("okavango_featured", "Okavango"), ("tonle_sap_featured", "Tonlé Sap"), ("atchafalaya_featured", "Atchafalaya")):
    r = res(aid)
    by = {x["class"]: x for x in (r.get("sensor_comparison") or {}).get("by_landcover", [])}
    for cls in (90, 80, 10):
        x = by.get(cls)
        if x:
            add("2", f"{label}: {x['name']} L/C agreement", f"{x['agree_percent']}% (95% CI {x['agree_percent_ci95'][0]}–{x['agree_percent_ci95'][1]}), both stable {x['agree_stable_percent']}%, both changed {x['agree_change_percent']}%, C-only {x['c_band_only_percent']}%, L-only {x['l_band_only_percent']}%, κ {x['kappa']:.2f}, {x['cells']:,} cells", f"result.json sensor_comparison.by_landcover ({aid})")
C = dg["C_l_vs_c"]
hw = [next(y for y in v["by_landcover"] if y["class"] == 90)["agree_percent"] for v in C["variants"]]
hwt = [next(y for y in t["by_landcover"] if y["name"] == "Herbaceous wetland")["agree_percent"] for t in C["threshold_sensitivity"]]
add("2", "Sylhet herbaceous wetland agreement across 6 aggregation variants / 3 ΔB thresholds", f"{min(hw)}–{max(hw)}% / {min(hwt)}–{max(hwt)}%", "diagnostics C_l_vs_c")

sm = ref("soil_moisture_sylhet_haor")
try:
    ser = sm.get("series", [])
    mon = {}
    for d in ser:
        v = d.get("mean_m3m3")
        if v is not None:
            mon.setdefault(d["date"][:7], []).append(v)
    add("4", "SMAP soil moisture, monthly mean", ", ".join(f"{k[5:]} {np.mean(v):.2f}" for k, v in sorted(mon.items())) + " m³/m³", "soil_moisture_sylhet_haor.json")
except Exception as ex:  # noqa: BLE001
    add("4", "SMAP", f"not recomputed ({ex})", "")

# cross-site summary
for aid, label in (("okavango_featured", "Okavango"), ("tonle_sap_featured", "Tonlé Sap"), ("atchafalaya_featured", "Atchafalaya")):
    r = res(aid)
    f1 = ", ".join(f"{a['nisar_date'][5:]} {a['open_water']['f1']:.2f}" for a in r["validation"]["accuracy"] if a["product"] == "DSWX_HLS")
    add("5,7", f"{label}: {r['earlier']['date']} → {r['later']['date']}", f"water {r['water']['earlier_km2']:.0f} → {r['water']['later_km2']:.0f} km²; optical F1 {f1}; calibration {r['validation']['radiometric_stability']['median_delta_db']:+.2f} dB{' ⚠ exceeds 0.5' if not r['validation']['radiometric_stability'].get('stable', True) else ''}; thresholds {r['water']['thresholds']['earlier']['method']}/{r['water']['thresholds']['later']['method']}", f"result.json ({aid})")

out = ["# Evidence for every number in the presentation", "",
       "Generated by `scripts/verify_claims.py` from the stored outputs (the same files the live API serves).",
       "Areas are recounted from the rasters where possible. Satellite references are not ground truth; no field data exist.", "",
       "| Slide | Claim | Value | Source |", "|---|---|---|---|"]
out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
(ROOT / "docs/evidence.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
