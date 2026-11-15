"""Discover, download and process real NISAR GCOV observations for the demo study areas.

Usage (from repo root):
    .venv/bin/python scripts/fetch_demo.py                 # all areas in scripts/demo_areas.json
    .venv/bin/python scripts/fetch_demo.py --area sylhet_haor --catalog-only

Requires EARTHDATA_TOKEN (or EARTHDATA_USERNAME/PASSWORD, or ~/.netrc) for downloads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config  # noqa: E402
from backend.ingestion import discovery, nisar, registry  # noqa: E402
from backend.preprocessing.georeferencing import bbox_polygon  # noqa: E402

AREAS_FILE = Path(__file__).with_name("demo_areas.json")


def process_area(area: dict, catalog_only: bool, max_granules: int) -> None:
    bbox = tuple(area["bbox"])
    registry.upsert_study_area({k: area[k] for k in ("id", "name", "description", "research_question", "bbox", "featured_pair") if k in area} | {"geometry": bbox_polygon(bbox)})
    granules = []
    for coll in area.get("collections", [config.DEFAULT_NISAR_COLLECTION]):
        found = discovery.search_nisar_gcov(bbox, collection=coll)
        print(f"[{area['id']}] {coll}: {len(found)} granules intersecting {bbox}")
        granules += found
    granules.sort(key=lambda g: g["start_time"])
    for g in granules:
        registry.upsert_observation(g)
    if catalog_only:
        return
    stack = [g for g in granules if g["stack_id"] == area["stack_id"] and g["full_frame"]]
    if area.get("dates"):
        stack = [g for g in stack if g["date"] in set(area["dates"])]
    else:
        stack = stack[-max_granules:]
    if len(stack) < 2:
        print(f"[{area['id']}] fewer than two granules in stack {area['stack_id']}; nothing to compare")
    for g in stack:
        print(f"  -> {g['date']} {g['id']} ({(g['size_bytes'] or 0) / 1e6:.0f} MB)")
        h5 = discovery.download_granule(g["download_url"])
        meta = nisar.inspect_gcov(h5)
        if meta["missing_paths"]:
            print("     missing HDF5 paths:", meta["missing_paths"])
        out_dir = config.PROCESSED_DIR / "observations" / g["id"]
        nisar.write_metadata_sidecar(meta, out_dir / "metadata.json")
        layers = {}
        for term in area["terms"]:
            if term not in meta["frequencies"].get(area["frequency"], {}).get("covariance_terms", []):
                print(f"     {term} not in file; skipped")
                continue
            rec = nisar.export_term_cog(h5, out_dir / f"{area['id']}_{area['frequency']}_{term}.tif", area["frequency"], term, bbox, area.get("multilook", 1))
            print(f"     {term}: {rec['shape']} px @ {rec['pixel_spacing_m']} m, EPSG:{rec['epsg']}, valid {rec['valid_fraction']:.1%}, looks~{rec['median_looks']}")
            rec["path"] = config.to_data_relative(rec["path"])  # portable across machines / deployments
            layers[f"{area['frequency']}_{term}"] = rec
        obs = registry.get_observation(g["id"]) or g
        processed = obs.get("processed") or {}
        processed[area["id"]] = {**processed.get(area["id"], {}), **layers}
        registry.upsert_observation({"id": g["id"], "file_metadata": meta, "processed": processed})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area")
    ap.add_argument("--catalog-only", action="store_true")
    ap.add_argument("--max-granules", type=int, default=3)
    a = ap.parse_args()
    areas = json.loads(AREAS_FILE.read_text())
    for area in areas:
        if a.area and area["id"] != a.area:
            continue
        process_area(area, a.catalog_only, a.max_granules)


if __name__ == "__main__":
    main()
