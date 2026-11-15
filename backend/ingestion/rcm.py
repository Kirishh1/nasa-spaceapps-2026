"""RADARSAT Constellation Mission (RCM, C-band) ingestion.

RCM products are distributed by the Canadian Space Agency / NRCan EODMS. No RCM files have been
ingested for the current study area, so this module reports availability honestly instead of
producing a layer. When calibrated, geocoded RCM GeoTIFFs (e.g. sigma0/gamma0 in linear power) are
placed in data/raw/rcm/<study_area_id>/, `discover_local_rcm` will list them.
"""
from __future__ import annotations

import re

import rasterio

from backend import config

RCM_DIR = config.RAW_DIR / "rcm"
_DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")


def discover_local_rcm(study_area_id: str) -> dict:
    d = RCM_DIR / study_area_id
    files = sorted(d.glob("*.tif")) if d.exists() else []
    if not files:
        return {
            "status": "unavailable",
            "reason": (
                "No RCM (C-band) observations have been ingested for this study area. RCM data must be "
                "ordered through EODMS and calibrated/geocoded before comparison; no RCM result is shown."
            ),
            "observations": [],
        }
    obs = []
    for p in files:
        m = _DATE_RE.search(p.name)
        with rasterio.open(p) as src:
            obs.append({
                "id": p.stem, "sensor": "RCM", "band": "C", "path": str(p),
                "date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None,
                "crs": src.crs.to_string() if src.crs else None, "shape": [src.height, src.width],
                "tags": src.tags(),
            })
    return {"status": "available", "observations": obs}
