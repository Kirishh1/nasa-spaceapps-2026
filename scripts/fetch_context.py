"""Context layers on the analysis grid (all free, no keys):

* ASF Global 30 m HAND (height above nearest drainage, from Copernicus GLO-30), AWS Open Data, CC0
  -> processed/reference/<area>/hand.tif          (metres)
* WorldPop R2025A constrained 100 m population, 2025, Bangladesh
  -> processed/reference/<area>/worldpop_2025.tif  (people per 20 m pixel, mass-preserving)
* NASA HLS (Harmonized Landsat Sentinel-2) true-colour composites for clear days
  -> processed/reference/<area>/hls_rgb_<date>.tif (3-band uint8, display only)

Registers each layer in reference/references_<area>.json.
Usage: .venv/bin/python scripts/fetch_context.py --area sylhet_haor --hls-dates 2026-09-15 2026-10-17
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject, transform_bounds  # noqa: E402

from backend import config, storage  # noqa: E402
from backend.ingestion import opera, registry  # noqa: E402

HAND_URL = "https://glo-30-hand.s3.us-west-2.amazonaws.com/v1/2021/Copernicus_DSM_COG_10_{lat}_00_{lon}_00_HAND.tif"
WORLDPOP_URL = "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/{ISO}/v1/100m/constrained/{iso}_pop_2025_CN_100m_R2025A_v1.tif"


def grid(area_id: str):
    for o in registry.observations():
        rec = registry.processed_layer(o, area_id, "A", "HHHH")
        if rec:
            with rasterio.open(rec["path"]) as s:
                return s.crs, s.transform, (s.height, s.width)
    sys.exit("no processed NISAR frame for this area")


def hand(area, crs, transform, shape) -> np.ndarray:
    w, s, e, n = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(*shape, transform))
    out = np.full(shape, np.nan, "float32")
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            url = HAND_URL.format(lat=f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}", lon=f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}")
            try:
                with rasterio.open("/vsicurl/" + url) as src:
                    tmp = np.full(shape, np.nan, "float32")
                    reproject(rasterio.band(src, 1), tmp, src_nodata=src.nodata, dst_transform=transform, dst_crs=crs,
                              dst_nodata=np.nan, resampling=Resampling.bilinear)
            except rasterio.errors.RasterioIOError:  # no tile (open ocean)
                print(f"HAND tile missing: {url.rsplit('/', 1)[-1]}")
                continue
            fill = np.isnan(out)
            out[fill] = tmp[fill]
    return out


def worldpop(crs, transform, shape, iso3: str = "BGD") -> np.ndarray:
    """People per pixel: resample population density (sum-preserving via area ratio)."""
    url = WORLDPOP_URL.format(ISO=iso3.upper(), iso=iso3.lower())
    local = config.RAW_DIR / "worldpop" / url.rsplit("/", 1)[-1]
    if not local.exists():  # the WorldPop server does not support HTTP range requests, so download once
        import urllib.request

        local.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, local)
    with rasterio.open(local) as src:
        dens = np.full(shape, np.nan, "float32")
        reproject(rasterio.band(src, 1), dens, src_nodata=src.nodata, dst_transform=transform, dst_crs=crs,
                  dst_nodata=np.nan, resampling=Resampling.average)
        # source cells are ~100 m (3 arc-seconds); convert people/cell to people per 20 m pixel
        px_area = abs(transform.a * transform.e)
        lat0 = (src.bounds.bottom + src.bounds.top) / 2
        src_cell_m2 = (3 / 3600 * 111_320) ** 2 * math.cos(math.radians(lat0))
    return np.nan_to_num(dens, nan=0.0) * (px_area / src_cell_m2)


def hls_rgb(area, date: str, crs, transform, shape) -> tuple[np.ndarray, list[str]] | None:
    import earthaccess

    earthaccess.login(strategy="environment")
    grans = []
    for sn in ("HLSL30", "HLSS30"):
        grans += earthaccess.search_data(short_name=sn, version="2.0", temporal=(date, date), bounding_box=tuple(area["bbox"]))
    if not grans:
        return None
    raw = config.RAW_DIR / "hls" / date
    rgb = np.zeros((3,) + shape, "float32")
    have = np.zeros(shape, bool)
    ids = []
    for g in grans:
        links = g.data_links(access="external")
        bands = [next((u for u in links if u.endswith(f".{b}.tif")), None) for b in ("B04", "B03", "B02")]
        fmask = next((u for u in links if u.endswith(".Fmask.tif")), None)
        if None in bands:
            continue
        paths = [Path(p) for p in earthaccess.download(bands + ([fmask] if fmask else []), local_path=str(raw))]
        stack = []
        for p in paths[:3]:
            tmp = np.full(shape, np.nan, "float32")
            with rasterio.open(p) as src:
                reproject(rasterio.band(src, 1), tmp, src_nodata=src.nodata, dst_transform=transform, dst_crs=crs,
                          dst_nodata=np.nan, resampling=Resampling.bilinear)
            stack.append(tmp * 0.0001)
        ok = np.all(np.isfinite(stack), axis=0) & ~have
        for i in range(3):
            rgb[i][ok] = stack[i][ok]
        have |= ok
        ids.append(g["umm"]["GranuleUR"])
    if not have.any():
        return None
    disp = np.clip(rgb / 0.25, 0, 1) ** (1 / 1.6)  # simple stretch + gamma for display
    out = (disp * 254 + 1).astype("uint8")
    out[:, ~have] = 0
    return out, ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--hls-dates", nargs="*", default=None, help="defaults to the study area's clear validation dates")
    ap.add_argument("--no-worldpop", action="store_true", help="skip population (the national file can be > 1 GB)")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    crs, transform, shape = grid(a.area)
    base = f"processed/reference/{a.area}"
    refs_path = config.REFERENCE_DIR / f"references_{a.area}.json"
    refs = json.loads(refs_path.read_text()) if refs_path.exists() else []
    refs = [r for r in refs if r["kind"] not in ("hand", "worldpop", "hls_rgb")]

    h = hand(area, crs, transform, shape)
    opera.write_cog(config.DATA_DIR / f"{base}/hand.tif", h, crs, transform, np.nan, {"product": "ASF GLO-30 HAND v1 2021", "units": "m"})
    refs.append({"kind": "hand", "path": f"{base}/hand.tif", "source": "ASF Global 30 m HAND (Copernicus GLO-30), CC0"})
    print(f"HAND: median {np.nanmedian(h):.1f} m, {np.mean(h > 15):.1%} of pixels > 15 m")

    if not a.no_worldpop:
        p = worldpop(crs, transform, shape, area.get("country_iso3", "BGD"))
        opera.write_cog(config.DATA_DIR / f"{base}/worldpop_2025.tif", p.astype("float32"), crs, transform, np.nan, {"product": "WorldPop R2025A 2025 constrained", "units": "people per pixel"})
        refs.append({"kind": "worldpop", "path": f"{base}/worldpop_2025.tif", "source": "WorldPop R2025A, doi:10.5258/SOTON/WP00839"})
        print(f"WorldPop: {p.sum():,.0f} people in the analysis grid")

    hls_dates = a.hls_dates if a.hls_dates is not None else sorted({r["date"] for r in refs if r.get("product") == "DSWX_HLS" and r["kind"] == "water"})
    for d in hls_dates:
        res = hls_rgb(area, d, crs, transform, shape)
        if res is None:
            print(f"HLS {d}: no usable scene")
            continue
        img, ids = res
        path = config.DATA_DIR / f"{base}/hls_rgb_{d}.tif"
        profile = {"driver": "COG", "dtype": "uint8", "count": 3, "width": shape[1], "height": shape[0], "crs": crs,
                   "transform": transform, "nodata": 0, "compress": "deflate"}
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(img)
        refs.append({"kind": "hls_rgb", "date": d, "path": f"{base}/hls_rgb_{d}.tif", "granules": ids})
        print(f"HLS {d}: true colour from {len(ids)} granule(s)")

    storage.write_text(f"reference/references_{a.area}.json", json.dumps(refs, indent=1))


if __name__ == "__main__":
    main()
