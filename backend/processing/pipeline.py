"""End-to-end NISAR temporal change-detection pipeline."""
from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.warp import transform_bounds

from backend import config, storage
from backend.environmental_context.precipitation import precipitation_context
from backend.ingestion import registry
from backend.preprocessing import quality
from backend.preprocessing.alignment import align_to_reference
from backend.preprocessing.calibration import linear_to_db, speckle_filter
from backend.preprocessing.georeferencing import pixel_area_m2, polygon_mask
from backend.processing import change_detection as cd
from backend.comparison import cband
from backend.ingestion import references
from backend.processing import inundation as inu
from backend.processing import water
from backend.validation import accuracy, swot
from backend.processing.statistics import change_statistics
from backend.validation import reference_data, validation

log = logging.getLogger("sarpulse.pipeline")

DEFAULT_CONFIG: dict[str, Any] = {
    "frequency": "A",
    "polarization": "HH",
    "threshold_db": 3.0,
    "speckle_filter": "lee",
    "filter_size": 5,
    "water_threshold_db": -18.0,
    "water_threshold_mode": "otsu",
    "min_region_m2": 20000.0,
    "min_valid_fraction": 0.2,
    "allow_cross_geometry": False,
    "include_precipitation": True,
    "include_reference": True,
}


OPERA_WATER = {
    "DSWX_S1": {"valid": (0, 1, 3), "open": (1,), "water": (1, 3)},   # 3 = inundated vegetation
    "DSWX_HLS": {"valid": (0, 1, 2), "open": (1,), "water": (1, 2)},  # 2 = partial surface water
}


class AnalysisError(Exception):
    def __init__(self, message: str, errors: list[dict] | None = None, warnings: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or [{"code": "analysis_error", "message": message}]
        self.warnings = warnings or []


DB_SCALE = 0.01      # dB layers are stored as int16 hundredths of a dB (±327 dB range, 0.01 dB precision)
DB_NODATA = -32768


def _write_cog(path: Path, arr: np.ndarray, transform, crs, nodata, tags: dict | None = None, db: bool = False) -> None:
    scale = None
    if db:  # halve storage/upload size; readers apply the scale factor (rio-tiler unscale=True)
        a = np.where(np.isfinite(arr), np.round(arr / DB_SCALE), DB_NODATA)
        arr, nodata, scale = np.clip(a, -32768, 32767).astype("int16"), DB_NODATA, DB_SCALE
    profile = {"driver": "COG", "dtype": str(arr.dtype), "count": 1, "width": arr.shape[1], "height": arr.shape[0],
               "crs": crs, "transform": transform, "nodata": nodata, "compress": "deflate",
               "predictor": 2 if arr.dtype == np.int16 else 1,
               "overview_resampling": "nearest" if arr.dtype == np.uint8 else "average"}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        if scale is not None:
            dst.scales = (scale,)
            dst.offsets = (0.0,)
        if tags:
            dst.update_tags(1, **{k: str(v) for k, v in tags.items()})


def resolve_config(user: dict | None) -> dict:
    cfg = {**DEFAULT_CONFIG, **{k: v for k, v in (user or {}).items() if v is not None}}
    cfg["polarization"] = cfg["polarization"].upper()
    cfg["frequency"] = cfg["frequency"].upper()
    if cfg["polarization"] not in ("HH", "HV", "VV", "VH"):
        raise AnalysisError(f"Unsupported polarization {cfg['polarization']}")
    if not 0 < float(cfg["threshold_db"]) <= 20:
        raise AnalysisError("threshold_db must be in (0, 20]")
    if cfg["speckle_filter"] not in ("lee", "boxcar", "none"):
        raise AnalysisError("speckle_filter must be lee, boxcar or none")
    if int(cfg["filter_size"]) < 1 or int(cfg["filter_size"]) % 2 == 0:
        raise AnalysisError("filter_size must be a positive odd integer")
    return cfg


def preflight(study_area_id: str, earlier_id: str, later_id: str, cfg: dict) -> tuple[dict, dict, dict, quality.Compatibility, dict, dict]:
    """Metadata checks and processed-layer lookup. Raises AnalysisError if the analysis cannot run."""
    area = registry.get_study_area(study_area_id)
    if not area:
        raise AnalysisError(f"Unknown study area '{study_area_id}'", [{"code": "unknown_study_area", "message": f"Unknown study area '{study_area_id}'"}])
    e, l = registry.get_observation(earlier_id), registry.get_observation(later_id)
    missing = [i for i, o in ((earlier_id, e), (later_id, l)) if o is None]
    if missing:
        raise AnalysisError("Unknown observation", [{"code": "unknown_observation", "message": f"Unknown observation id(s): {missing}"}])
    compat = quality.check_pair(e, l, cfg["frequency"], cfg["polarization"], area, cfg["allow_cross_geometry"])
    term = cfg["polarization"] * 2
    le = registry.processed_layer(e, study_area_id, cfg["frequency"], term)
    ll = registry.processed_layer(l, study_area_id, cfg["frequency"], term)
    for name, o, rec in (("earlier", e, le), ("later", l, ll)):
        if rec is None and not any(x["code"] == "polarization_unavailable" for x in compat.errors):
            compat.error("not_ingested", f"The {name} observation ({o['date']}) has not been downloaded and processed for {term} over this study area. Run scripts/fetch_demo.py.")
    if not compat.ok:
        raise AnalysisError("Observations are not compatible", compat.errors, compat.warnings)
    return area, e, l, compat, le, ll


def _dilate(mask: np.ndarray, radius_px: int) -> np.ndarray:
    """Binary dilation by a square of the given radius using cumulative sums (no SciPy)."""
    if radius_px <= 0:
        return mask
    k = 2 * radius_px + 1
    m = np.pad(mask.astype("int32"), radius_px)
    ii = np.zeros((m.shape[0] + 1, m.shape[1] + 1), "int64")
    ii[1:, 1:] = m.cumsum(0).cumsum(1)
    return (ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]) > 0


def _days_between(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def subarea(area: dict, geometry: dict | None) -> dict:
    """Intersect an optional user-drawn polygon with the study area."""
    if not geometry:
        return area
    from shapely.geometry import mapping, shape

    try:
        g = shape(geometry)
    except Exception as ex:  # noqa: BLE001
        raise AnalysisError("Invalid drawn area", [{"code": "invalid_geometry", "message": f"Drawn area is not a valid polygon: {ex}"}])
    inter = g.intersection(shape(area["geometry"]))
    if inter.is_empty or inter.area == 0:
        raise AnalysisError("Drawn area outside study area", [{"code": "geometry_outside", "message": "The drawn area does not overlap the processed study area."}])
    return {**area, "geometry": mapping(inter), "bbox": list(inter.bounds), "name": f"{area['name']} (drawn subset)", "subset": True}


def run_analysis(study_area_id: str, earlier_id: str, later_id: str, user_config: dict | None = None, analysis_id: str | None = None, geometry: dict | None = None, progress=None) -> dict:
    step = progress or (lambda _msg: None)
    cfg = resolve_config(user_config)
    area, e, l, compat, le, ll = preflight(study_area_id, earlier_id, later_id, cfg)
    area = subarea(area, geometry)
    analysis_id = analysis_id or uuid.uuid4().hex[:12]
    out_dir = config.ANALYSES_DIR / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)

    step("Aligning the two frames")
    pair = align_to_reference(le["path"], ll["path"])
    shape_hw = pair.earlier.shape
    in_area = polygon_mask(area["geometry"], pair.crs, pair.transform, shape_hw)
    px_m2 = pixel_area_m2(pair.transform, pair.crs)
    spacing = [abs(pair.transform.a), abs(pair.transform.e)]

    step("Filtering speckle and computing ΔB")
    looks_e, looks_l = le.get("median_looks") or 1.0, ll.get("median_looks") or 1.0
    fe = speckle_filter(pair.earlier, cfg["speckle_filter"], int(cfg["filter_size"]), looks_e)
    fl = speckle_filter(pair.later, cfg["speckle_filter"], int(cfg["filter_size"]), looks_l)
    edb, ldb = linear_to_db(fe), linear_to_db(fl)
    edb[~in_area] = np.nan
    ldb[~in_area] = np.nan
    delta = cd.difference_db(edb, ldb)
    cls = cd.classify(delta, float(cfg["threshold_db"]), in_area)

    total = int(in_area.sum())
    valid_frac = float((cls > 0).sum() / total) if total else 0.0
    quality.check_valid_overlap(valid_frac, float(cfg["min_valid_fraction"]), compat)
    if not compat.ok:
        raise AnalysisError("Insufficient valid data", compat.errors, compat.warnings)

    step("Reading JRC water and ESA WorldCover references")
    occurrence = landcover = None
    ref_errors = []
    refs = references.load(study_area_id)
    if cfg["include_reference"]:
        for r in refs:  # precomputed on this grid by scripts/fetch_reference.py (avoids remote reads at run time)
            if r["kind"] in ("jrc", "worldcover"):
                path = storage.local_file(r["path"])
                if path:
                    with rasterio.open(path) as src:
                        arr = src.read(1)
                    if arr.shape == shape_hw:
                        if r["kind"] == "jrc":
                            occurrence = arr
                        else:
                            landcover = arr
    if cfg["include_reference"]:
        for name, fn in (("jrc", reference_data.jrc_occurrence), ("worldcover", reference_data.worldcover)):
            if (name == "jrc" and occurrence is not None) or (name == "worldcover" and landcover is not None):
                continue
            try:
                arr = fn(pair.crs, pair.transform, shape_hw)
                if name == "jrc":
                    occurrence = arr
                else:
                    landcover = arr
            except Exception as ex:  # noqa: BLE001
                ref_errors.append(f"{name}: {ex}")
                log.warning("reference %s failed: %s", name, ex)

    step("Mapping open water on each date")
    min_px = max(1, int(round(float(cfg["min_region_m2"]) / px_m2)))
    thr = {}
    fits = {side: (water.otsu(img) if cfg["water_threshold_mode"] == "otsu" else None) for side, img in (("earlier", edb), ("later", ldb))}
    for side in ("earlier", "later"):
        other = "later" if side == "earlier" else "earlier"
        own, alt = fits[side], fits[other]
        if own and own[1] >= water.MIN_SEPARABILITY:
            thr[side] = {"threshold_db": round(own[0], 2), "method": "otsu", "separability": own[1]}
        elif alt and alt[1] >= water.MIN_SEPARABILITY:
            # this image has no clear water/land split (e.g. little water); reuse the other date's threshold
            thr[side] = {"threshold_db": round(alt[0], 2), "method": "otsu (from other date)", "separability": own[1] if own else None}
        else:
            thr[side] = {"threshold_db": float(cfg["water_threshold_db"]), "method": "fixed", "separability": own[1] if own else None}
    wmap_e = water.water_map(edb, thr["earlier"]["threshold_db"], in_area, min_px)
    wmap_l = water.water_map(ldb, thr["later"]["threshold_db"], in_area, min_px)
    wchange = water.water_change(wmap_e, wmap_l)

    step("Finding potential inundation and computing statistics")
    copol = cfg["polarization"] in ("HH", "VV")
    if copol:
        inund, inund_info = inu.potential_inundation(cls, ldb, thr["later"]["threshold_db"], min_px, landcover)
    else:
        inund = np.where(cls > 0, inu.NONE, 0).astype("uint8")
        inund_info = {"evaluated": False, "reason": "Potential inundation rules are defined for co-polarized channels (HH/VV) only."}
    inund_info.update({"min_region_pixels": min_px, "copol": copol})

    stats = change_statistics(delta, cls, inund, in_area, px_m2, edb, ldb, float(cfg["threshold_db"]))
    ref = validation.reference_consistency(inund, cls, occurrence, landcover)
    if ref_errors:
        ref["errors"] = ref_errors
    report = validation.uncertainty_report(e, l, cfg, compat.as_dict(), pair.notes, stats, spacing)
    report["method"]["water_threshold"] = f"{cfg['water_threshold_mode']} (earlier {thr['earlier']['threshold_db']} dB, later {thr['later']['threshold_db']} dB)"

    def km2(mask) -> float:
        return round(float(np.count_nonzero(mask)) * px_m2 / 1e6, 3)

    water_info = {
        "thresholds": thr,
        "earlier_km2": km2(wmap_e == water.WATER), "later_km2": km2(wmap_l == water.WATER),
        "persistent_km2": km2(wchange == water.PERSISTENT_WATER), "gained_km2": km2(wchange == water.WATER_GAINED),
        "lost_km2": km2(wchange == water.WATER_LOST),
        "earlier_fraction": round(float((wmap_e == water.WATER).sum() / max(1, (wmap_e > 0).sum())), 4),
        "later_fraction": round(float((wmap_l == water.WATER).sum() / max(1, (wmap_l > 0).sum())), 4),
    }

    # radiometric stability: backscatter of built-up and tree-covered pixels that are land on both dates should not move
    calib = {"status": "unavailable", "reason": "No land-cover reference to select invariant targets."}
    if landcover is not None:
        inv = np.isin(landcover, (10, 50)) & (wmap_e == water.LAND) & (wmap_l == water.LAND) & np.isfinite(delta)
        if inv.sum() > 1000:
            dv = delta[inv]
            med = float(np.median(dv))
            calib = {"status": "available", "pixels": int(inv.sum()), "median_delta_db": round(med, 2),
                     "iqr_db": [round(float(np.percentile(dv, 25)), 2), round(float(np.percentile(dv, 75)), 2)],
                     "stable": abs(med) <= 0.5,
                     "note": "Median ΔB over built-up and tree-cover pixels that are land on both dates. "
                             "A value near 0 dB means the two frames are radiometrically consistent (no calibration offset)."}
    ref["radiometric_stability"] = calib

    step("Validating water maps against NASA OPERA references")
    ref["accuracy"] = []
    ref_maps = {}
    for side, d, wm in (("earlier", e["date"], wmap_e), ("later", l["date"], wmap_l)):
        for r in references.water_refs(refs, d):
            path = storage.local_file(r["path"])
            if path is None:
                continue
            with rasterio.open(path) as src:
                rw = src.read(1)
            if rw.shape != wm.shape:
                continue
            spec = OPERA_WATER[r["product"]]
            ok = (wm > 0) & np.isin(rw, spec["valid"])
            ref_maps[(side, r["product"])] = (rw, ok)
            img = edb if side == "earlier" else ldb
            t0 = thr[side]["threshold_db"]
            ref_open = np.isin(rw, spec["open"])
            sensitivity = []
            for dt_ in (-3, -2, -1, 0, 1, 2, 3):
                m = accuracy.binary_metrics(np.isfinite(img) & (img < t0 + dt_), ref_open, ok)
                sensitivity.append({"threshold_db": round(t0 + dt_, 2), "f1": m["f1"], "iou": m["iou"], "precision": m["precision"], "recall": m["recall"]})
            entry = {"side": side, "nisar_date": d, **{k: r[k] for k in ("product", "date", "offset_days", "track", "observed_fraction", "granules")},
                     "open_water": accuracy.binary_metrics(wm == water.WATER, ref_open, ok),
                     "all_water": accuracy.binary_metrics(wm == water.WATER, np.isin(rw, spec["water"]), ok),
                     "threshold_sensitivity": sensitivity}
            ref["accuracy"].append(entry)
    # change agreement against same-orbit radar reference pairs (avoids orbit-geometry differences)
    ref["change_accuracy"] = []
    pe_mask, pl_mask = wmap_e == water.WATER, wmap_l == water.WATER
    ref_lost = []  # reference "water lost" maps per orbit, to measure how well the reference agrees with itself
    for re_r, rl_r in references.change_pairs(refs, e["date"], l["date"]):
        pe_, pl_ = storage.local_file(re_r["path"]), storage.local_file(rl_r["path"])
        if not pe_ or not pl_:
            continue
        with rasterio.open(pe_) as a_, rasterio.open(pl_) as b_:
            ra, rb = a_.read(1), b_.read(1)
        spec = OPERA_WATER["DSWX_S1"]
        ok = (wmap_e > 0) & (wmap_l > 0) & np.isin(ra, spec["valid"]) & np.isin(rb, spec["valid"])
        rew, rlw = np.isin(ra, spec["open"]), np.isin(rb, spec["open"])
        ref_lost.append((rew & ~rlw, ok))
        entry = {"product": "DSWX_S1", "track": re_r["track"], "earlier_date": re_r["date"], "later_date": rl_r["date"],
                 "total_offset_days": re_r["offset_days"] + rl_r["offset_days"],
                 "water_lost": accuracy.binary_metrics(wchange == water.WATER_LOST, rew & ~rlw, ok),
                 "water_gained": accuracy.binary_metrics(wchange == water.WATER_GAINED, ~rew & rlw, ok),
                 "cells_100m": accuracy.cell_fraction_agreement(pe_mask, pl_mask, rew, rlw, ok, 5),
                 "cells_500m": accuracy.cell_fraction_agreement(pe_mask, pl_mask, rew, rlw, ok, 25)}
        ref["change_accuracy"].append(entry)

    for prod in ("DSWX_HLS",):
        if ("earlier", prod) in ref_maps and ("later", prod) in ref_maps:
            (ra, oka), (rb, okb) = ref_maps[("earlier", prod)], ref_maps[("later", prod)]
            spec = OPERA_WATER[prod]
            ok = oka & okb
            rew, rlw = np.isin(ra, spec["open"]), np.isin(rb, spec["open"])
            de = next(x["date"] for x in ref["accuracy"] if x["product"] == prod and x["side"] == "earlier")
            dl = next(x["date"] for x in ref["accuracy"] if x["product"] == prod and x["side"] == "later")
            ref["change_accuracy"].insert(0, {
                "product": prod, "track": None, "earlier_date": de, "later_date": dl,
                "total_offset_days": _days_between(de, e["date"]) + _days_between(dl, l["date"]),
                "water_lost": accuracy.binary_metrics(wchange == water.WATER_LOST, rew & ~rlw, ok),
                "water_gained": accuracy.binary_metrics(wchange == water.WATER_GAINED, ~rew & rlw, ok),
                "cells_100m": accuracy.cell_fraction_agreement(pe_mask, pl_mask, rew, rlw, ok, 5),
                "cells_500m": accuracy.cell_fraction_agreement(pe_mask, pl_mask, rew, rlw, ok, 25)})

    self_f1 = []
    for i in range(len(ref_lost)):
        for j in range(i + 1, len(ref_lost)):
            m = accuracy.binary_metrics(ref_lost[i][0], ref_lost[j][0], ref_lost[i][1] & ref_lost[j][1])
            if m["f1"] is not None:
                self_f1.append(m["f1"])
    ref["reference_change_self_agreement"] = {"pairs": len(self_f1), "f1_min": min(self_f1), "f1_max": max(self_f1)} if self_f1 else None

    step("Reading SWOT lake water levels")
    sw = swot.lake_level_change(study_area_id, e["date"], l["date"])
    data = sw.pop("_data", None)
    if sw["status"] == "available" and data:
        sw["area_agreement"] = swot.lake_area_agreement(data, sw["passes"], wmap_e == water.WATER, wmap_l == water.WATER,
                                                        pair.crs, pair.transform, px_m2 / 1e6)
    ref["swot"] = sw

    step("Estimating impact (cropland, people, volume)")
    impact: dict = {}
    if landcover is not None:
        lost = wchange == water.WATER_LOST
        impact["cropland_emerged_km2"] = km2(lost & (landcover == 40))
        impact["wetland_emerged_km2"] = km2(lost & (landcover == 90))
        impact["note_cropland"] = ("Cropland (ESA WorldCover) that was open water on the earlier date and land on the later date. "
                                   + ((area.get("story") or {}).get("impact") or ""))
        impact["cropland_flooded_km2"] = km2((wchange == water.WATER_GAINED) & (landcover == 40))
    pop_ref = next((r for r in refs if r["kind"] == "worldpop"), None)
    if pop_ref and (pth := storage.local_file(pop_ref["path"])):
        with rasterio.open(pth) as src:
            pop = src.read(1)
        if pop.shape == shape_hw:
            near = _dilate(wchange == water.WATER_LOST, int(round(1000 / spacing[0])))
            impact["people_within_1km_of_receded_water"] = int(round(float(np.nansum(pop[near & in_area]))))
            impact["people_in_area"] = int(round(float(np.nansum(pop[in_area]))))
            impact["population_source"] = pop_ref.get("source")
    drained_lc = None
    if landcover is not None:
        drained_lc = np.zeros(shape_hw, "uint8")
        lost_ = wchange == water.WATER_LOST
        drained_lc[lost_] = 3
        drained_lc[lost_ & np.isin(landcover, (30, 90))] = 2
        drained_lc[lost_ & (landcover == 40)] = 1
        drained_lc[(wchange == water.WATER_GAINED) & (landcover == 40)] = 4
    pop_density = None
    if pop_ref and (pth := storage.local_file(pop_ref["path"])):
        with rasterio.open(pth) as src:
            pp = src.read(1).astype("float32")
        if pp.shape == shape_hw:
            pop_density = np.where(in_area, pp / (px_m2 / 1e4), np.nan)  # people per hectare
    if sw.get("status") == "available" and sw.get("passes"):
        dh = float(np.median([p_["median_change_m"] for p_ in sw["passes"]]))
        mean_area = (water_info["earlier_km2"] + water_info["later_km2"]) / 2
        impact["volume_change_km3_approx"] = round(mean_area * dh / 1000, 2)
        impact["note_volume"] = (f"Order of magnitude only: mean open-water area ({mean_area:.0f} km²) × median SWOT lake-level change ({dh:.2f} m). "
                                 "Assumes the haor water surface fell uniformly, which it did not exactly.")

    if ref["accuracy"]:
        ref["independently_validated"] = True
        max_off = max(a["offset_days"] for a in ref["accuracy"])
        ref["statement"] = ("Open-water maps were compared pixel by pixel with NASA OPERA surface-water products (DSWx) from "
                            "Sentinel-1 radar and Harmonized Landsat-Sentinel-2 optical data, within a few days of each NISAR pass. "
                            "These are independent products, not ground truth: they have their own errors, and dates differ by up to "
                            + (f"{max_off} day." if max_off == 1 else f"{max_off} days."))

    step("Comparing with Sentinel-1 C-band (NASA OPERA RTC-S1)")
    sensor_cmp = {"status": "unavailable", "reason": "No same-track Sentinel-1 RTC pair near both NISAR dates."}
    cband_cls = None
    pairc = references.cband_pair(refs, e["date"], l["date"])
    if pairc:
        pe_, pl_ = (storage.local_file(x["path"]) for x in pairc)
        if pe_ and pl_:
            cdelta, cband_cls = cband.cband_change(str(pe_), str(pl_), in_area, float(cfg["threshold_db"]), cfg["speckle_filter"], int(cfg["filter_size"]))
            comp = cband.compare(cls, cband_cls, landcover, 5, pair.transform)
            _write_cog(out_dir / "lc_agreement.tif", comp["agreement"], comp["transform"], pair.crs, 0, {"cell_size_m": comp["cell_size_m"]})
            cv = cband_cls > 0
            sensor_cmp = {
                "status": "available",
                "sensor": "Sentinel-1 C-band VV (NASA OPERA RTC-S1)",
                "earlier": {k: pairc[0][k] for k in ("date", "track", "granules")},
                "later": {k: pairc[1][k] for k in ("date", "track", "granules")},
                "cell_size_m": comp["cell_size_m"], "stats": comp["stats"], "by_landcover": comp["by_landcover"],
                "cband_change_percent": {
                    "decrease": round(100 * float((cband_cls == cd.DECREASE).sum() / max(1, cv.sum())), 2),
                    "increase": round(100 * float((cband_cls == cd.INCREASE).sum() / max(1, cv.sum())), 2)},
                "method": "Each sensor's ΔB is classified with the same threshold on its own data; class maps are aggregated to "
                          f"{comp['cell_size_m']:.0f} m cells (a change class wins a cell when it covers ≥30% of its valid pixels) and compared. "
                          "Raw L- and C-band backscatter are never differenced. The bands also differ in polarization (NISAR HH, Sentinel-1 VV), "
                          "viewing geometry and exact dates, so not every difference is due to wavelength. Land cover: ESA WorldCover 2021, "
                          "dominant class per cell. Intervals: 95% bootstrap over 5 km blocks.",
            }

    step("Writing map layers")
    tags = {"study_area": study_area_id, "earlier": e["id"], "later": l["id"], "polarization": cfg["polarization"]}
    layers_spec = [
        ("earlier_db", edb, np.nan, "dB"), ("later_db", ldb, np.nan, "dB"), ("delta_db", delta, np.nan, "dB"),
        ("change_class", cls, 0, "class"), ("inundation", inund, 0, "class"), ("water_change", wchange, 0, "class"),
    ]
    if cband_cls is not None:
        layers_spec.append(("cband_change", cband_cls, 0, "class"))
    if drained_lc is not None:
        layers_spec.append(("drained_landcover", drained_lc, 0, "class"))
    if pop_density is not None:
        layers_spec.append(("population", pop_density, np.nan, "people/ha"))
    for name, arr, nod, units in layers_spec:
        _write_cog(out_dir / f"{name}.tif", arr.astype("float32") if units in ("dB", "people/ha") else arr, pair.transform, pair.crs, nod, {**tags, "units": units}, db=units in ("dB", "people/ha"))
    if occurrence is not None:
        _write_cog(out_dir / "jrc_occurrence.tif", occurrence, pair.transform, pair.crs, 255, {"units": "percent"})

    bounds_ll = transform_bounds(pair.crs, "EPSG:4326", *rasterio.transform.array_bounds(*shape_hw, pair.transform), densify_pts=21)

    step("Requesting GPM rainfall context")
    precip = None
    if cfg["include_precipitation"]:
        try:
            precip = precipitation_context(tuple(area["bbox"]), e["date"], l["date"], area_id=study_area_id)
        except Exception as ex:  # noqa: BLE001
            precip = {"status": "unavailable", "reason": f"GPM retrieval failed: {ex}"}

    result = {
        "id": analysis_id,
        "status": "complete",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study_area": {k: area[k] for k in ("id", "name", "bbox", "geometry", "research_question", "subset", "story", "category") if k in area},
        "sensor": "NISAR",
        "config": cfg,
        "earlier": {k: v for k, v in e.items() if k not in ("file_metadata", "processed")},
        "later": {k: v for k, v in l.items() if k not in ("file_metadata", "processed")},
        "days_between": (dt.date.fromisoformat(l["date"]) - dt.date.fromisoformat(e["date"])).days,
        "grid": {"crs": pair.crs.to_string(), "shape": list(shape_hw), "pixel_spacing_m": spacing, "bounds_lonlat": list(bounds_ll), "resampled": pair.resampled},
        "compatibility": compat.as_dict(),
        "statistics": stats,
        "inundation": inund_info,
        "validation": ref,
        "uncertainty": report,
        "precipitation": precip,
        "water": water_info,
        "impact": impact,
        "sensor_comparison": sensor_cmp,
        "layers": [n for n, *_ in layers_spec] + (["jrc_occurrence"] if occurrence is not None else [])
                  + (["lc_agreement"] if sensor_cmp["status"] == "available" else []),
    }
    result = registry.json_safe(result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
    if storage.is_blob():
        step("Saving results")
        # result.json last, so a listed result always has its layers
        from concurrent.futures import ThreadPoolExecutor

        files = [f for f in out_dir.iterdir() if f.name != "result.json"]
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda f: storage.upload_file(f"processed/analyses/{analysis_id}/{f.name}", f), files))
        storage.upload_file(f"processed/analyses/{analysis_id}/result.json", out_dir / "result.json")
    return result


def load_result(analysis_id: str) -> dict | None:
    if not analysis_id.replace("_", "").replace("-", "").isalnum():
        return None
    text = storage.read_text(f"processed/analyses/{analysis_id}/result.json")
    return registry.json_safe(json.loads(text)) if text else None


def layer_path(analysis_id: str, layer: str) -> Path | None:
    """Local path of an analysis raster (downloaded from Blob into the cache when needed)."""
    return storage.local_file(f"processed/analyses/{analysis_id}/{layer}.tif")


def list_results(study_area_id: str | None = None) -> list[dict]:
    """Summaries of stored analyses, newest first."""
    out = []
    for rel in storage.list_files("processed/analyses", "result.json"):
        try:
            r = json.loads(storage.read_text(rel) or "")
        except Exception:  # noqa: BLE001
            continue
        if study_area_id and r.get("study_area", {}).get("id") != study_area_id:
            continue
        out.append({"id": r["id"], "created_at": r["created_at"], "study_area_id": r["study_area"]["id"],
                    "earlier_id": r["earlier"]["id"], "later_id": r["later"]["id"], "earlier_date": r["earlier"]["date"],
                    "later_date": r["later"]["date"], "subset": bool(r["study_area"].get("subset")), "config": r["config"]})
    return sorted(out, key=lambda x: x["created_at"], reverse=True)
