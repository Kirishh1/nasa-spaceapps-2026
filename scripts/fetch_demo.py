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


def process_area(area: dict, catalog_only: bool, max_granules: int, stream: bool = True, workers: int = 5) -> None:
    bbox = tuple(area["bbox"])
    keys = ("id", "name", "description", "research_question", "bbox", "featured_pair", "category", "story", "country_iso3", "swot_continent")
    registry.upsert_study_area({k: area[k] for k in keys if k in area} | {"geometry": bbox_polygon(bbox)})
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
    todo = []
    for g in stack:
        existing = (registry.get_observation(g["id"]) or {}).get("processed", {}).get(area["id"], {})
        if existing and all(registry.has_processed_layer(registry.get_observation(g["id"]), area["id"], area["frequency"], t) for t in area["terms"]):
            print(f"  == {g['date']} already processed", flush=True)
            continue
        todo.append(g)
    if not todo:
        return
    # each frame in its own process: h5py serialises reads within a process, and streaming is network-bound
    from concurrent.futures import ProcessPoolExecutor, as_completed

    with ProcessPoolExecutor(max_workers=min(workers, len(todo))) as ex:
        futs = {ex.submit(_process_frame, g, area, stream): g for g in todo}
        for fut in as_completed(futs):
            g = futs[fut]
            try:
                meta, layers = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  !! {g['date']} failed: {e}", flush=True)
                continue
            obs = registry.get_observation(g["id"]) or g
            processed = obs.get("processed") or {}
            processed[area["id"]] = {**processed.get(area["id"], {}), **layers}
            registry.upsert_observation({"id": g["id"], "file_metadata": meta, "processed": processed})
            print(f"  -> {g['date']} done: " + ", ".join(f"{k} {v['shape']} valid {v['valid_fraction']:.0%}" for k, v in layers.items()), flush=True)


def _process_frame(g: dict, area: dict, stream: bool):
    """Worker: read one NISAR frame (streamed window or full download) and write its COGs."""
    if stream:
        import earthaccess

        earthaccess.login(strategy="environment")
        h5 = g["download_url"]
    else:
        h5 = discovery.download_granule(g["download_url"])
    meta = nisar.inspect_gcov(h5)
    out_dir = config.PROCESSED_DIR / "observations" / g["id"]
    nisar.write_metadata_sidecar(meta, out_dir / "metadata.json")
    layers = {}
    for term in area["terms"]:
        if term not in meta["frequencies"].get(area["frequency"], {}).get("covariance_terms", []):
            continue
        rec = nisar.export_term_cog(h5, out_dir / f"{area['id']}_{area['frequency']}_{term}.tif", area["frequency"], term,
                                    tuple(area["bbox"]), area.get("multilook", 1))
        rec["path"] = config.to_data_relative(rec["path"])
        layers[f"{area['frequency']}_{term}"] = rec
    return meta, layers

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area")
    ap.add_argument("--catalog-only", action="store_true")
    ap.add_argument("--max-granules", type=int, default=3)
    ap.add_argument("--download", action="store_true", help="download full granules instead of streaming the window")
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    areas = json.loads(AREAS_FILE.read_text())
    for area in areas:
        if a.area and area["id"] != a.area:
            continue
        process_area(area, a.catalog_only, a.max_granules, stream=not a.download, workers=a.workers)


if __name__ == "__main__":
    main()  # (process pool needs the __main__ guard on macOS spawn)
