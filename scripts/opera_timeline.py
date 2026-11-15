"""Surface-water timeline for a study area from NASA OPERA DSWx (Sentinel-1 and HLS), on the analysis grid.

Writes data/reference/water_timeline_<area>.json: for each date, the share of observed pixels that are
water (open water, and open water + inundated vegetation for DSWx-S1) and the share of the area observed.
Used to choose NISAR pairs from evidence and shown in the app as seasonal context.

Usage: .venv/bin/python scripts/opera_timeline.py --area sylhet_haor --start 2026-06-01 --end 2026-11-15
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402

from backend import config, storage  # noqa: E402
from backend.ingestion import opera, registry  # noqa: E402
from backend.preprocessing.georeferencing import polygon_mask  # noqa: E402


def grid_for(area_id: str):
    """Analysis grid of the area = grid of its processed NISAR frames."""
    for o in registry.observations():
        rec = registry.processed_layer(o, area_id, "A", "HHHH")
        if rec:
            with rasterio.open(rec["path"]) as s:
                return s.crs, s.transform, (s.height, s.width)
    sys.exit("no processed NISAR frame for this area yet; run scripts/fetch_demo.py first")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-15")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    crs, transform, shape = grid_for(a.area)
    inside = polygon_mask(area["geometry"], crs, transform, shape)
    raw = config.RAW_DIR / "opera"
    out = {"study_area": a.area, "grid": {"crs": crs.to_string(), "shape": list(shape)}, "series": []}
    for product, water, openw, valid in (("DSWX_S1", opera.DSWX_S1_WATER, opera.DSWX_S1_OPEN, opera.DSWX_S1_VALID),
                                         ("DSWX_HLS", opera.DSWX_HLS_WATER, (1,), opera.DSWX_HLS_VALID)):
        grans = opera.search(product, area["bbox"], a.start, a.end)
        by_date: dict[str, list[dict]] = {}
        for g in grans:
            by_date.setdefault(g["date"], []).append(g)
        for date, gs in sorted(by_date.items()):
            urls = [u for u in (opera.layer_url(g, "_B01_WTR.tif") for g in gs) if u]
            paths = opera.download(urls, raw / product.lower())
            wtr = opera.mosaic_to_grid(paths, crs, transform, shape, nodata=255)
            ok = inside & np.isin(wtr, valid)
            n_ok = int(ok.sum())
            rec = {"product": product, "date": date, "granules": [g["id"] for g in gs],
                   "observed_fraction": round(n_ok / int(inside.sum()), 4),
                   "water_fraction": round(float(np.isin(wtr[ok], water).mean()), 4) if n_ok else None,
                   "open_water_fraction": round(float(np.isin(wtr[ok], openw).mean()), 4) if n_ok else None}
            out["series"].append(rec)
            print(f"{product:8s} {date}  observed {rec['observed_fraction']:.0%}  water {rec['water_fraction']}  open {rec['open_water_fraction']}")
    storage.write_text(f"reference/water_timeline_{a.area}.json", json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
