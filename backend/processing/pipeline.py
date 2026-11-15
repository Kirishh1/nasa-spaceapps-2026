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
from backend.processing import inundation as inu
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
    "min_region_m2": 20000.0,
    "min_valid_fraction": 0.2,
    "allow_cross_geometry": False,
    "include_precipitation": True,
    "include_reference": True,
}


class AnalysisError(Exception):
    def __init__(self, message: str, errors: list[dict] | None = None, warnings: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or [{"code": "analysis_error", "message": message}]
        self.warnings = warnings or []


def _write_cog(path: Path, arr: np.ndarray, transform, crs, nodata, tags: dict | None = None) -> None:
    profile = {"driver": "COG", "dtype": str(arr.dtype), "count": 1, "width": arr.shape[1], "height": arr.shape[0],
               "crs": crs, "transform": transform, "nodata": nodata, "compress": "deflate",
               "overview_resampling": "nearest" if arr.dtype == np.uint8 else "average"}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
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
    if cfg["include_reference"]:
        for name, fn in (("jrc", reference_data.jrc_occurrence), ("worldcover", reference_data.worldcover)):
            try:
                arr = fn(pair.crs, pair.transform, shape_hw)
                if name == "jrc":
                    occurrence = arr
                else:
                    landcover = arr
            except Exception as ex:  # noqa: BLE001
                ref_errors.append(f"{name}: {ex}")
                log.warning("reference %s failed: %s", name, ex)

    step("Finding potential inundation and computing statistics")
    min_px = max(1, int(round(float(cfg["min_region_m2"]) / px_m2)))
    copol = cfg["polarization"] in ("HH", "VV")
    if copol:
        inund, inund_info = inu.potential_inundation(cls, ldb, float(cfg["water_threshold_db"]), min_px, landcover)
    else:
        inund = np.where(cls > 0, inu.NONE, 0).astype("uint8")
        inund_info = {"evaluated": False, "reason": "Potential inundation rules are defined for co-polarized channels (HH/VV) only."}
    inund_info.update({"min_region_pixels": min_px, "copol": copol})

    stats = change_statistics(delta, cls, inund, in_area, px_m2, edb, ldb, float(cfg["threshold_db"]))
    ref = validation.reference_consistency(inund, cls, occurrence, landcover)
    if ref_errors:
        ref["errors"] = ref_errors
    report = validation.uncertainty_report(e, l, cfg, compat.as_dict(), pair.notes, stats, spacing)

    step("Writing map layers")
    tags = {"study_area": study_area_id, "earlier": e["id"], "later": l["id"], "polarization": cfg["polarization"]}
    layers_spec = [
        ("earlier_db", edb, np.nan, "dB"), ("later_db", ldb, np.nan, "dB"), ("delta_db", delta, np.nan, "dB"),
        ("change_class", cls, 0, "class"), ("inundation", inund, 0, "class"),
    ]
    for name, arr, nod, units in layers_spec:
        _write_cog(out_dir / f"{name}.tif", arr.astype("float32") if units == "dB" else arr, pair.transform, pair.crs, nod, {**tags, "units": units})
    if occurrence is not None:
        _write_cog(out_dir / "jrc_occurrence.tif", occurrence, pair.transform, pair.crs, 255, {"units": "percent"})

    bounds_ll = transform_bounds(pair.crs, "EPSG:4326", *rasterio.transform.array_bounds(*shape_hw, pair.transform), densify_pts=21)

    step("Requesting GPM rainfall context")
    precip = None
    if cfg["include_precipitation"]:
        try:
            precip = precipitation_context(tuple(area["bbox"]), e["date"], l["date"])
        except Exception as ex:  # noqa: BLE001
            precip = {"status": "unavailable", "reason": f"GPM retrieval failed: {ex}"}

    result = {
        "id": analysis_id,
        "status": "complete",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study_area": {k: area[k] for k in ("id", "name", "bbox", "geometry", "research_question", "subset") if k in area},
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
        "sensor_comparison": {"status": "unavailable", "reason": "No compatible RCM (C-band) change map is available for this study area and period."},
        "layers": [n for n, *_ in layers_spec] + (["jrc_occurrence"] if occurrence is not None else []),
    }
    result = registry.json_safe(result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
    if storage.is_blob():
        step("Saving results")
        # result.json last, so a listed result always has its layers
        for f in sorted(out_dir.iterdir(), key=lambda f: f.name == "result.json"):
            storage.upload_file(f"processed/analyses/{analysis_id}/{f.name}", f)
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
