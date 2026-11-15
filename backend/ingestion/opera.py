"""NASA JPL OPERA products used as independent references and as the C-band comparison sensor.

* OPERA_L3_DSWX-S1_V1 (NASA PO.DAAC): surface-water extent from Sentinel-1 C-band radar, 30 m MGRS tiles.
  B01_WTR classes (DSWx-S1 product spec; the inundated-vegetation option is recorded in each file's
  PROCESSING_INFORMATION_INUNDATED_VEGETATION tag): 0 not water, 1 open water, 3 inundated vegetation,
  250 HAND-masked, 251 layover/shadow-masked, 255 no data.
* OPERA_L3_DSWX-HLS_V1 (NASA PO.DAAC): surface-water extent from Landsat/Sentinel-2 optical; clouds masked.
  B01_WTR classes: 0 not water, 1 open water, 2 partial surface water, 252 snow/ice, 253 cloud/shadow, 255 fill.
* OPERA_L2_RTC-S1_V1 (NASA ASF DAAC): radiometric-terrain-corrected Sentinel-1 backscatter (gamma0, linear),
  30 m UTM bursts, VV and VH. Used as an independent C-band change map, never differenced against NISAR.

Search uses NASA CMR (no auth); downloads use Earthdata Login via earthaccess.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject

from backend import config

COLLECTIONS = {
    "DSWX_S1": "C2949811996-POCLOUD",
    "DSWX_HLS": "C2617126679-POCLOUD",
    "RTC_S1": "C2777436413-ASF",
}

# Reference water encodings
DSWX_S1_WATER = (1, 3)
DSWX_S1_OPEN = (1,)
DSWX_S1_VALID = (0, 1, 3)
DSWX_HLS_WATER = (1, 2)
DSWX_HLS_VALID = (0, 1, 2)


def search(product: str, bbox, start: str, end: str) -> list[dict]:
    params = {
        "collection_concept_id": COLLECTIONS[product],
        "bounding_box": ",".join(str(v) for v in bbox),
        "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
        "page_size": 2000,
        "sort_key": "start_date",
    }
    url = f"{config.CMR_URL}/granules.umm_json?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as r:
        items = json.load(r)["items"]
    out = []
    for it in items:
        u = it["umm"]
        urls = [x["URL"] for x in u.get("RelatedUrls", []) if x["URL"].startswith("https") and x.get("Type", "").startswith("GET DATA")]
        rec = {"id": u["GranuleUR"], "product": product, "start_time": u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"],
               "date": u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10], "urls": urls}
        if product == "RTC_S1":
            m = re.search(r"_T(\d{3})-(\d{6})-(IW\d)_", u["GranuleUR"])
            rec["track"] = int(m.group(1)) if m else None
            rec["burst"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
            rec["platform"] = u["GranuleUR"].split("_")[-3]
        else:
            m = re.search(r"_T(\d{2}[A-Z]{3})_", u["GranuleUR"])
            rec["tile"] = m.group(1) if m else None
        out.append(rec)
    return out


def layer_url(granule: dict, suffix: str) -> str | None:
    return next((u for u in granule["urls"] if u.endswith(suffix)), None)


def download(urls: list[str], dest: Path) -> list[Path]:
    import os

    import earthaccess

    dest.mkdir(parents=True, exist_ok=True)
    todo = [u for u in urls if not (dest / u.rsplit("/", 1)[-1]).exists()]
    if todo:
        strategy = "environment" if (os.environ.get("EARTHDATA_TOKEN") or os.environ.get("EARTHDATA_USERNAME")) else "netrc"
        earthaccess.login(strategy=strategy)
        earthaccess.download(todo, local_path=str(dest))
    return [dest / u.rsplit("/", 1)[-1] for u in urls]


def mosaic_to_grid(paths: list[Path], crs, transform, shape, nodata, resampling=Resampling.nearest, dtype="uint8") -> np.ndarray:
    """Mosaic same-CRS tiles (first valid wins) and reproject onto a target grid."""
    srcs = [rasterio.open(p) for p in paths]
    try:
        by_crs: dict = {}
        for s in srcs:
            by_crs.setdefault(s.crs.to_string(), []).append(s)
        out = np.full(shape, nodata, dtype=dtype)
        for group in by_crs.values():
            mos, mt = merge(group, nodata=nodata)
            tmp = np.full(shape, nodata, dtype=dtype)
            reproject(mos[0].astype(dtype), tmp, src_transform=mt, src_crs=group[0].crs, src_nodata=nodata,
                      dst_transform=transform, dst_crs=crs, dst_nodata=nodata, resampling=resampling)
            fill = (out == nodata) if not (isinstance(nodata, float) and np.isnan(nodata)) else np.isnan(out)
            out[fill] = tmp[fill]
        return out
    finally:
        for s in srcs:
            s.close()


def write_cog(path: Path, arr: np.ndarray, crs, transform, nodata, tags: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {"driver": "COG", "dtype": str(arr.dtype), "count": 1, "width": arr.shape[1], "height": arr.shape[0],
               "crs": crs, "transform": transform, "nodata": nodata, "compress": "deflate",
               "overview_resampling": "nearest" if arr.dtype == np.uint8 else "average"}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
