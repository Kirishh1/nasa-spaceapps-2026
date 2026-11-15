"""Discovery of real satellite observations via NASA CMR.

Search needs no authentication. Downloading needs an Earthdata Login (see download_granule).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from backend import config


def _attrs(umm: dict) -> dict[str, list[str]]:
    return {a["Name"]: a.get("Values", []) for a in umm.get("AdditionalAttributes", [])}


def _footprint(umm: dict) -> dict | None:
    """Return the granule footprint as a GeoJSON Polygon (lon/lat)."""
    geom = umm.get("SpatialExtent", {}).get("HorizontalSpatialDomain", {}).get("Geometry", {})
    polys = geom.get("GPolygons") or []
    if not polys:
        return None
    pts = polys[0]["Boundary"]["Points"]
    ring = [[p["Longitude"], p["Latitude"]] for p in pts]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def parse_nisar_granule(item: dict, collection: str) -> dict[str, Any]:
    umm = item["umm"]
    a = _attrs(umm)
    first = lambda k: (a.get(k) or [None])[0]  # noqa: E731
    urls = umm.get("RelatedUrls", [])
    h5_url = next((u["URL"] for u in urls if u.get("Type") == "GET DATA" and u["URL"].endswith(".h5")), None)
    browse = next((u["URL"] for u in urls if u["URL"].endswith("_LATLON.png") and u["URL"].startswith("https")), None)
    qa_report = next((u["URL"] for u in urls if u["URL"].endswith("_QA_REPORT.pdf") and u["URL"].startswith("https")), None)
    sizes = {f["Name"]: f.get("SizeInBytes") for f in umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])}
    granule_id = umm["GranuleUR"]
    t = umm["TemporalExtent"]["RangeDateTime"]
    return {
        "id": granule_id,
        "sensor": "NISAR",
        "band": "L",
        "product_type": first("PRODUCT_TYPE"),
        "processing_level": first("PROCESSING_LEVEL"),
        "product_version": first("PRODUCT_VERSION"),
        "collection": collection,
        "cmr_concept_id": item["meta"]["concept-id"],
        "start_time": t["BeginningDateTime"],
        "end_time": t["EndingDateTime"],
        "date": t["BeginningDateTime"][:10],
        "track": int(first("TRACK_NUMBER")) if first("TRACK_NUMBER") else None,
        "frame": int(first("FRAME_NUMBER")) if first("FRAME_NUMBER") else None,
        "stack_id": first("STACK_ID"),
        "pass_direction": first("ASCENDING_DESCENDING"),
        "full_frame": first("FULL_FRAME") == "TRUE",
        "frequencies": a.get("FREQUENCIES", []),
        "polarizations": {
            "A": a.get("FREQUENCY_A_POLARIZATION", []),
            "B": a.get("FREQUENCY_B_POLARIZATION", []),
        },
        "range_bandwidth_mhz": {
            "A": first("FREQUENCY_A_RANGE_BANDWIDTH"),
            "B": first("FREQUENCY_B_RANGE_BANDWIDTH"),
        },
        "footprint": _footprint(umm),
        "download_url": h5_url,
        "size_bytes": sizes.get(f"{granule_id}.h5"),
        "browse_url": browse,
        "qa_report_url": qa_report,
    }


def search_nisar_gcov(
    bbox: tuple[float, float, float, float],
    start: str | None = None,
    end: str | None = None,
    collection: str = config.DEFAULT_NISAR_COLLECTION,
    max_items: int = 500,
) -> list[dict[str, Any]]:
    """Search CMR for NISAR GCOV granules intersecting bbox (west, south, east, north)."""
    concept = config.NISAR_GCOV_COLLECTIONS[collection]
    params = {
        "collection_concept_id": concept,
        "bounding_box": ",".join(str(v) for v in bbox),
        "page_size": min(max_items, 2000),
        "sort_key": "start_date",
    }
    if start or end:
        params["temporal"] = f"{start or ''},{end or ''}"
    url = f"{config.CMR_URL}/granules.umm_json?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    return [parse_nisar_granule(it, collection) for it in data.get("items", [])]


def group_by_stack(granules: list[dict]) -> dict[str, list[dict]]:
    """Group granules into repeat-pass stacks (same track, direction and frame)."""
    stacks: dict[str, list[dict]] = {}
    for g in granules:
        pol = "+".join(g["polarizations"]["A"])
        stacks.setdefault(f"{g['stack_id']}|{pol}", []).append(g)
    for v in stacks.values():
        v.sort(key=lambda g: g["start_time"])
    return stacks


def download_granule(url: str, dest_dir: Path = config.RAW_DIR) -> Path:
    """Download a granule using an Earthdata Login (EARTHDATA_TOKEN / USERNAME+PASSWORD or ~/.netrc)."""
    import os

    import earthaccess

    strategy = "environment" if (os.environ.get("EARTHDATA_TOKEN") or os.environ.get("EARTHDATA_USERNAME")) else "netrc"
    auth = earthaccess.login(strategy=strategy)
    if not auth or not auth.authenticated:
        raise RuntimeError(
            "Earthdata authentication failed. Set EARTHDATA_TOKEN (or EARTHDATA_USERNAME/PASSWORD) in .env, "
            "or create ~/.netrc for urs.earthdata.nasa.gov."
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / url.rsplit("/", 1)[-1]
    if target.exists() and target.stat().st_size > 0:
        return target
    files = earthaccess.download([url], local_path=str(dest_dir))
    if not files:
        raise RuntimeError(f"Download failed for {url}")
    return Path(files[0])
