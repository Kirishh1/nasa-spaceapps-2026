"""NISAR open-water fraction for every processed frame of a study area (same method as the analysis pipeline:
Lee filter, dB, per-image Otsu threshold with the separability check), plus per-date agreement with the
OPERA references matched to that date. Writes reference/nisar_season_<area>.json for the season chart.

Usage: .venv/bin/python scripts/nisar_season.py --area sylhet_haor
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402

from backend import storage  # noqa: E402
from backend.ingestion import references, registry  # noqa: E402
from backend.preprocessing.calibration import linear_to_db, speckle_filter  # noqa: E402
from backend.preprocessing.georeferencing import pixel_area_m2, polygon_mask  # noqa: E402
from backend.processing import water  # noqa: E402
from backend.processing.pipeline import OPERA_WATER, DEFAULT_CONFIG  # noqa: E402
from backend.validation.accuracy import binary_metrics  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    refs = references.load(a.area)
    out = []
    seen: set[str] = set()
    # newest reprocessing (highest product counter, e.g. _002 over _001) first within a date
    for o in sorted(sorted(registry.observations(), key=lambda o: o["id"], reverse=True), key=lambda o: o["start_time"][:10]):
        if o["date"] in seen:  # reprocessed duplicates of one acquisition
            continue
        rec = registry.processed_layer(o, a.area, "A", "HHHH")
        if not rec:
            continue
        seen.add(o["date"])
        with rasterio.open(rec["path"]) as s:
            lin = s.read(1).astype("float32")
            crs, tr = s.crs, s.transform
        inside = polygon_mask(area["geometry"], crs, tr, lin.shape)
        db = linear_to_db(speckle_filter(lin, DEFAULT_CONFIG["speckle_filter"], DEFAULT_CONFIG["filter_size"], rec.get("median_looks") or 1.0))
        db[~inside] = np.nan
        fit = water.otsu(db)
        thr = fit[0] if fit and fit[1] >= water.MIN_SEPARABILITY else DEFAULT_CONFIG["water_threshold_db"]
        min_px = max(1, int(round(DEFAULT_CONFIG["min_region_m2"] / pixel_area_m2(tr, crs))))
        wm = water.water_map(db, thr, inside, min_px)
        valid = wm > 0
        entry = {"date": o["date"], "id": o["id"], "product_version": o.get("product_version"),
                 "threshold_db": round(thr, 2), "separability": fit[1] if fit else None,
                 "water_fraction": round(float((wm == water.WATER).sum() / max(1, valid.sum())), 4),
                 "water_km2": round(float((wm == water.WATER).sum()) * pixel_area_m2(tr, crs) / 1e6, 1), "validation": []}
        for r in references.water_refs(refs, o["date"]):
            p = storage.local_file(r["path"])
            with rasterio.open(p) as s:
                rw = s.read(1)
            spec = OPERA_WATER[r["product"]]
            ok = valid & np.isin(rw, spec["valid"])
            m = binary_metrics(wm == water.WATER, np.isin(rw, spec["open"]), ok)
            entry["validation"].append({"product": r["product"], "date": r["date"], "offset_days": r["offset_days"],
                                        "f1": m["f1"], "iou": m["iou"], "reference_fraction": m["reference_fraction"],
                                        "nisar_fraction_same_pixels": m["predicted_fraction"]})
        out.append(entry)
        print(f"{o['date']}: water {entry['water_fraction']:.0%} ({entry['water_km2']} km²), threshold {thr:.2f} dB, "
              + ", ".join(f"{v['product']} {v['date']} F1 {v['f1']}" for v in entry["validation"]))
    storage.write_text(f"reference/nisar_season_{a.area}.json", json.dumps({"study_area": a.area, "series": out}, indent=1))


if __name__ == "__main__":
    main()
