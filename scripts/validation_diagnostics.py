"""Diagnose the validation numbers of a stored analysis (default: sylhet_monsoon, 18 Jun -> 16 Oct 2026).

Answers, from the stored layers and the same reference files the pipeline used:
  A. How good is the C-band change reference itself? (DSWx-S1 vs optical DSWx-HLS on near-same days; orbit-to-orbit
     self-agreement of the DSWx-S1 change maps.)
  B. Where does change disagreement sit? (change F1 after excluding pixels near water/land boundaries; per-date
     water-map error area compared with the size of the change; temporal offsets; open vs open+inundated-vegetation
     reference classes.)
  C. How robust is the L-band vs C-band land-cover finding? (stable vs change agreement, kappa, block-bootstrap
     95% intervals, cell size, aggregation rule and ΔB threshold sensitivity.)
  D. How sensitive are the impact numbers? (water threshold ±1 dB, drained area by land cover, population on
     vs near drained land.)
Nothing here changes the analysis or its thresholds. Writes reference/diagnostics_<analysis>.json.

Usage: .venv/bin/python scripts/validation_diagnostics.py [--analysis sylhet_monsoon]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402

from backend import config, storage  # noqa: E402
from backend.comparison import cband  # noqa: E402
from backend.comparison.sensor_comparison import aggregate_classes  # noqa: E402
from backend.ingestion import references  # noqa: E402
from backend.processing import change_detection as cd  # noqa: E402
from backend.processing import water  # noqa: E402
from backend.processing.pipeline import OPERA_WATER, _dilate  # noqa: E402
from backend.validation import accuracy, diagnostics as dg  # noqa: E402


def read(path, db=False):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float32")
        if db:
            nod = s.nodata
            a = np.where(a == nod, np.nan, a * (s.scales[0] or 1.0) + (s.offsets[0] or 0.0))
    return a


def days(a, b):
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", default="sylhet_monsoon")
    a = ap.parse_args()
    d = config.analysis_dir(a.analysis)
    r = json.loads((d / "result.json").read_text())
    area = r["study_area"]["id"]
    refs = references.load(area)
    px_km2 = abs(r["grid"]["pixel_spacing_m"][0] * r["grid"]["pixel_spacing_m"][1]) / 1e6
    e_date, l_date = r["earlier"]["date"], r["later"]["date"]
    out: dict = {"analysis": a.analysis, "study_area": area, "pair": [e_date, l_date], "pixel_km2": px_km2}

    wchange = read(d / "water_change.tif").astype("uint8")
    valid = wchange > 0
    ew = (wchange == water.PERSISTENT_WATER) | (wchange == water.WATER_LOST)
    lw = (wchange == water.PERSISTENT_WATER) | (wchange == water.WATER_GAINED)
    lost = wchange == water.WATER_LOST
    S1 = OPERA_WATER["DSWX_S1"]
    HLS = OPERA_WATER["DSWX_HLS"]

    def ref_arr(rec):
        return read(storage.local_file(rec["path"])).astype("uint8")

    # ---------------- A. reference quality
    s1_all = [x for x in refs if x["kind"] in ("water", "water_change_candidate") and x["product"] == "DSWX_S1"]
    hls_all = [x for x in refs if x["kind"] == "water" and x["product"] == "DSWX_HLS"]
    seen = set()
    s1_vs_opt = []
    for h in hls_all:
        H = ref_arr(h)
        for s in s1_all:
            key = (s["date"], s["track"], h["date"])
            if key in seen or days(s["date"], h["date"]) > 2:
                continue
            seen.add(key)
            Sx = ref_arr(s)
            ok = valid & np.isin(H, HLS["valid"]) & np.isin(Sx, S1["valid"])
            m_open = accuracy.binary_metrics(np.isin(Sx, S1["open"]), np.isin(H, HLS["open"]), ok)
            m_all = accuracy.binary_metrics(np.isin(Sx, S1["water"]), np.isin(H, HLS["open"]), ok)
            s1_vs_opt.append({"s1_date": s["date"], "s1_track": s["track"], "optical_date": h["date"], "optical_sensor": h["track"],
                              "f1_open": m_open["f1"], "f1_open_plus_inundated_veg": m_all["f1"],
                              "s1_water_fraction": m_open["predicted_fraction"], "optical_water_fraction": m_open["reference_fraction"]})
    out["A_reference_quality"] = {
        "s1_vs_optical_same_days": s1_vs_opt,
        "s1_change_self_agreement": r["validation"].get("reference_change_self_agreement"),
        "nisar_vs_optical_per_date": [{"nisar_date": x["nisar_date"], "optical_date": x["date"], "f1": x["open_water"]["f1"]}
                                      for x in r["validation"]["accuracy"] if x["product"] == "DSWX_HLS"],
    }

    # ---------------- B. change disagreement
    edges = dg.boundary(ew, valid) | dg.boundary(lw, valid)
    per_track = []
    for re_r, rl_r in references.change_pairs(refs, e_date, l_date):
        ra, rb = ref_arr(re_r), ref_arr(rl_r)
        ok = valid & np.isin(ra, S1["valid"]) & np.isin(rb, S1["valid"])
        rew, rlw = np.isin(ra, S1["open"]), np.isin(rb, S1["open"])
        rew2, rlw2 = np.isin(ra, S1["water"]), np.isin(rb, S1["water"])
        ref_edges = dg.boundary(rew, ok) | dg.boundary(rlw, ok)
        m_open = accuracy.binary_metrics(lost, rew & ~rlw, ok)
        m_all = accuracy.binary_metrics(lost, rew2 & ~rlw2, ok)
        per_track.append({
            "track": re_r["track"], "dates": [re_r["date"], rl_r["date"]], "total_offset_days": re_r["offset_days"] + rl_r["offset_days"],
            "f1_lost_open": m_open["f1"], "f1_lost_open_plus_inundated_veg": m_all["f1"],
            "nisar_lost_km2": round(float((lost & ok).sum()) * px_km2, 1), "reference_lost_km2": round(float((rew & ~rlw & ok).sum()) * px_km2, 1),
            "reference_water_km2": [round(float((rew & ok).sum()) * px_km2, 1), round(float((rlw & ok).sum()) * px_km2, 1)],
            "nisar_water_km2": [round(float((ew & ok).sum()) * px_km2, 1), round(float((lw & ok).sum()) * px_km2, 1)],
            "edge_buffer": dg.edge_buffer_change_f1(lost, rew & ~rlw, ok, edges | ref_edges),
        })
    out["B_change_vs_s1"] = per_track
    # error budget: water-map disagreement area at the later date vs the change itself
    budget = []
    for x in r["validation"]["accuracy"]:
        ow = x["open_water"]
        if ow.get("fp") is None:
            continue
        budget.append({"nisar_date": x["nisar_date"], "reference": f"{x['product']} {x['date']}",
                       "disagreement_km2": round((ow["fp"] + ow["fn"]) * px_km2, 1), "f1": ow["f1"]})
    out["B_error_budget"] = {"nisar_lost_km2": r["water"]["lost_km2"], "per_date_water_map_disagreement": budget,
                             "note": "A change map is the difference of two water maps. When each map disagrees with its reference over an "
                                     "area comparable to the change itself, pixel-level change agreement is limited even if each date is mapped well."}

    # ---------------- C. L vs C by land cover
    lc_ref = next((x for x in refs if x["kind"] == "worldcover"), None)
    lc = read(storage.local_file(lc_ref["path"])).astype("uint8") if lc_ref else None
    out["C_landcover_source"] = {"product": "ESA WorldCover 2021 v200 (10 m)", "on_grid": "resampled to the 20 m NISAR grid (see fetch_reference.py)",
                                 "cell_class": "dominant WorldCover class of each aggregated cell"} if lc_ref else None
    ncls = read(d / "change_class.tif").astype("uint8")
    ccls = read(d / "cband_change.tif").astype("uint8") if (d / "cband_change.tif").exists() else None
    sc = r.get("sensor_comparison") or {}
    if ccls is not None and lc is not None:
        names = cband.LANDCOVER_NAMES
        variants = []
        for factor in (5, 10):
            for mcf in (0.2, 0.3, 0.5):
                A = aggregate_classes(ncls, factor, min_change_fraction=mcf)
                B = aggregate_classes(ccls, factor, min_change_fraction=mcf)
                L = cband._block_majority(lc, factor)
                det = dg.landcover_agreement_detail(A, B, L, names, block=max(5, 250 // factor), n_boot=300 if (factor, mcf) != (5, 0.3) else 1000)
                variants.append({"cell_m": factor * 20, "min_change_fraction": mcf, "by_landcover": det,
                                 "primary": factor == 5 and mcf == 0.3})
        # ΔB threshold sensitivity (both sensors reclassified with the same threshold)
        pe_, pl_ = [storage.local_file(x["path"]) for x in references.cband_pair(refs, e_date, l_date)]
        delta_n = read(d / "delta_db.tif", db=True)
        in_area = np.isfinite(delta_n)
        thr_var = []
        for t in (2.0, 3.0, 4.0):
            cn = cd.classify(delta_n, t, in_area)
            _, cc = cband.cband_change(str(pe_), str(pl_), in_area, t, r["config"]["speckle_filter"], int(r["config"]["filter_size"]))
            det = dg.landcover_agreement_detail(aggregate_classes(cn, 5), aggregate_classes(cc, 5), cband._block_majority(lc, 5), names, n_boot=200)
            thr_var.append({"threshold_db": t, "by_landcover": [{k: x[k] for k in ("name", "cells", "agree_percent", "agree_stable_percent",
                                                                                    "agree_change_percent", "c_band_only_percent", "kappa")} for x in det]})
        out["C_l_vs_c"] = {"comparison": {"nisar": "NISAR L-band HH", "cband": sc.get("sensor"),
                                          "dates": {"nisar": [e_date, l_date], "cband": [sc["earlier"]["date"], sc["later"]["date"]]},
                                          "cband_track": sc["earlier"]["track"]},
                           "what_is_compared": "ΔB change classes (decrease / limited / increase at ±threshold dB), each from its own sensor, "
                                               "aggregated to cells by the rule 'a change class covers ≥ min_change_fraction of valid pixels'.",
                           "variants": variants, "threshold_sensitivity": thr_var}

    # ---------------- D. impact sensitivity
    edb, ldb = read(d / "earlier_db.tif", db=True), read(d / "later_db.tif", db=True)
    inside = np.isfinite(edb) & np.isfinite(ldb)
    min_px = max(1, int(round(r["config"]["min_region_m2"] / (px_km2 * 1e6))))
    the, thl = r["water"]["thresholds"]["earlier"]["threshold_db"], r["water"]["thresholds"]["later"]["threshold_db"]
    pop_ref = next((x for x in refs if x["kind"] == "worldpop"), None)
    pop = read(storage.local_file(pop_ref["path"])) if pop_ref else None
    spacing = r["grid"]["pixel_spacing_m"][0]
    sens = []
    for dthr in (-1.0, -0.5, 0.0, 0.5, 1.0):
        we = water.water_map(edb, the + dthr, inside, min_px)
        wl = water.water_map(ldb, thl + dthr, inside, min_px)
        wc = water.water_change(we, wl)
        lo = wc == water.WATER_LOST
        row = {"threshold_shift_db": dthr, "lost_km2": round(float(lo.sum()) * px_km2, 1),
               "gained_km2": round(float((wc == water.WATER_GAINED).sum()) * px_km2, 1)}
        if lc is not None:
            row["cropland_emerged_km2"] = round(float((lo & (lc == 40)).sum()) * px_km2, 1)
        if pop is not None and dthr == 0.0:
            near = _dilate(lo, int(round(1000 / spacing)))
            row["people_within_1km"] = int(np.nansum(pop[near & inside]))
        sens.append(row)
    by_lc = {}
    if lc is not None:
        for code, name in cband.LANDCOVER_NAMES.items():
            v = float((lost & (lc == code)).sum()) * px_km2
            if v >= 0.5:
                by_lc[name] = round(v, 1)
    pop_info = None
    if pop is not None:
        total = float(np.nansum(pop[valid]))
        near_lost = {}
        for km in (0.2, 0.5, 1.0):
            near_lost[f"{km:g}km"] = int(np.nansum(pop[_dilate(lost, int(round(km * 1000 / spacing))) & valid]))
        near_water = int(np.nansum(pop[_dilate(ew, int(round(1000 / spacing))) & valid]))
        pop_info = {"people_in_area": int(total), "people_on_drained_pixels": int(np.nansum(pop[lost])),
                    "people_within_distance_of_drained_land": near_lost, "people_within_1km_of_any_june_water": near_water,
                    "note": "Proximity is exposure context, not harm. In a wetland basin where most land is within 1 km of water, the "
                            "1 km figure covers nearly everyone, so it does not single out an affected group."}
    out["D_impact"] = {"threshold_sensitivity": sens, "drained_area_by_landcover_km2": by_lc, "population": pop_info,
                       "landcover_caveat": "WorldCover 2021 is a single-date map; seasonally flooded haor rice land can be labelled cropland "
                                           "or herbaceous wetland. Cropland figures inherit that uncertainty."}

    storage.write_text(f"reference/diagnostics_{a.analysis}.json", json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:6000])


if __name__ == "__main__":
    main()
