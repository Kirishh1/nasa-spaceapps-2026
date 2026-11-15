"""Independent reference datasets, read directly from public cloud-optimized GeoTIFFs.

* JRC Global Surface Water v1.4 (2021) occurrence: % of months 1984–2021 a pixel was water (Pekel et al. 2016).
* ESA WorldCover 10 m v200 (2021) land cover.

Both are resampled (nearest) onto the analysis grid. They describe *historical/typical* conditions,
not the observation dates, so they provide context, not ground truth for a specific event.
"""
from __future__ import annotations

import math

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject, transform_bounds

GSW_URL = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{lon}_{lat}v1_4_2021.tif"
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

SOURCES = {
    "jrc_gsw": {"name": "JRC Global Surface Water occurrence v1.4 (1984–2021)", "citation": "Pekel, J.-F. et al. (2016) Nature 540, 418–422", "url": "https://global-surface-water.appspot.com/"},
    "worldcover": {"name": "ESA WorldCover 10 m 2021 v200", "citation": "Zanaga, D. et al. (2022) doi:10.5281/zenodo.7254221", "url": "https://esa-worldcover.org/"},
}


def _gsw_tiles(w, s, e, n):
    for lon in range(int(math.floor(w / 10) * 10), int(math.ceil(e / 10) * 10), 10):
        for top in range(int(math.floor(s / 10) * 10) + 10, int(math.ceil(n / 10) * 10) + 10, 10):
            ln = f"{abs(lon)}{'W' if lon < 0 else 'E'}"
            lt = f"{abs(top)}{'S' if top < 0 else 'N'}"
            yield GSW_URL.format(lon=ln, lat=lt)


def _wc_tiles(w, s, e, n):
    for lon in range(int(math.floor(w / 3) * 3), int(math.ceil(e / 3) * 3), 3):
        for lat in range(int(math.floor(s / 3) * 3), int(math.ceil(n / 3) * 3), 3):
            t = f"{'S' if lat < 0 else 'N'}{abs(lat):02d}{'W' if lon < 0 else 'E'}{abs(lon):03d}"
            yield WC_URL.format(tile=t)


def _read_onto_grid(urls, crs, transform, shape, nodata_out, dtype):
    w, s, e, n = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(shape[0], shape[1], transform), densify_pts=21)
    srcs = []
    try:
        for u in urls:
            try:
                srcs.append(rasterio.open("/vsicurl/" + u))
            except rasterio.errors.RasterioIOError:
                continue
        if not srcs:
            return None
        mosaic, mt = merge(srcs, bounds=(w - 0.01, s - 0.01, e + 0.01, n + 0.01), nodata=nodata_out)
        out = np.full(shape, nodata_out, dtype=dtype)
        reproject(mosaic[0], out, src_transform=mt, src_crs="EPSG:4326", src_nodata=nodata_out,
                  dst_transform=transform, dst_crs=crs, dst_nodata=nodata_out, resampling=Resampling.nearest)
        return out
    finally:
        for s_ in srcs:
            s_.close()


def jrc_occurrence(crs, transform, shape) -> np.ndarray | None:
    """Water occurrence 0–100 (%), 255 = no data."""
    w, s, e, n = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(shape[0], shape[1], transform))
    return _read_onto_grid(list(_gsw_tiles(w, s, e, n)), crs, transform, shape, 255, "uint8")


def worldcover(crs, transform, shape) -> np.ndarray | None:
    """ESA WorldCover class codes, 0 = no data."""
    w, s, e, n = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(shape[0], shape[1], transform))
    return _read_onto_grid(list(_wc_tiles(w, s, e, n)), crs, transform, shape, 0, "uint8")
