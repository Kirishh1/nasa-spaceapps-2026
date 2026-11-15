"""Fetch NASA OPERA reference data for every processed NISAR date of a study area, on the analysis grid.

For each processed NISAR acquisition date D:
  * DSWx-S1 water map on the closest date within ±MAX_DAYS (best coverage on ties)       -> validation
  * DSWx-HLS water map on the closest date within ±MAX_DAYS with ≥50 % cloud-free cover  -> validation
  * RTC-S1 VV backscatter for every Sentinel-1 track with a pass within ±MAX_DAYS_RTC     -> C-band change
Writes COGs to data/processed/reference/<area>/ and a registry at reference/references_<area>.json.

Usage: .venv/bin/python scripts/fetch_reference.py --area sylhet_haor
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling  # noqa: E402

from backend import config, storage  # noqa: E402
from backend.ingestion import opera, registry  # noqa: E402
from backend.preprocessing.georeferencing import polygon_mask  # noqa: E402

MAX_DAYS = 2
MAX_DAYS_OPTICAL = 5  # clear optical days are rare in the monsoon; the offset is recorded and shown
MAX_DAYS_RTC = 6


def _days(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    obs = [o for o in registry.observations() if registry.processed_layer(o, a.area, "A", "HHHH")]
    if not obs:
        sys.exit("no processed NISAR frames for this area")
    with rasterio.open(registry.processed_layer(obs[0], a.area, "A", "HHHH")["path"]) as s:
        crs, transform, shape = s.crs, s.transform, (s.height, s.width)
    inside = polygon_mask(area["geometry"], crs, transform, shape)
    out_dir = config.PROCESSED_DIR / "reference" / a.area
    raw = config.RAW_DIR / "opera"
    dates = sorted({o["date"] for o in obs})
    lo = (dt.date.fromisoformat(dates[0]) - dt.timedelta(days=MAX_DAYS_RTC)).isoformat()
    hi = (dt.date.fromisoformat(dates[-1]) + dt.timedelta(days=MAX_DAYS_RTC)).isoformat()
    refs: list[dict] = []

    # --- water maps (validation)
    for product, valid, min_obs in (("DSWX_S1", opera.DSWX_S1_VALID, 0.3), ("DSWX_HLS", opera.DSWX_HLS_VALID, 0.5)):
        grans = opera.search(product, area["bbox"], lo, hi)
        by_date: dict[str, list[dict]] = {}
        for g in grans:
            by_date.setdefault(g["date"], []).append(g)
        for d in dates:
            win = MAX_DAYS_OPTICAL if product == "DSWX_HLS" else MAX_DAYS
            cands = sorted((x for x in by_date if _days(x, d) <= win), key=lambda x: _days(x, d))
            best = None
            for x in cands:
                urls = [u for u in (opera.layer_url(g, "_B01_WTR.tif") for g in by_date[x]) if u]
                paths = opera.download(urls, raw / product.lower())
                wtr = opera.mosaic_to_grid(paths, crs, transform, shape, nodata=255)
                cover = float((inside & np.isin(wtr, valid)).sum() / inside.sum())
                if cover >= min_obs and (best is None or (_days(x, d), -cover) < (_days(best[0], d), -best[2])):
                    track = None
                    with rasterio.open(paths[0]) as s:
                        track = s.tags().get("RTC_TRACK_NUMBER") or s.tags().get("SPACECRAFT_NAME")
                    best = (x, wtr, cover, [g["id"] for g in by_date[x]], track)
            if best is None:
                print(f"{product}: no reference within ±{win} d of {d} with ≥{min_obs:.0%} cover")
            else:
                x, wtr, cover, ids, track = best
                rel = f"processed/reference/{a.area}/{product.lower()}_{x}.tif"
                opera.write_cog(config.DATA_DIR / rel, wtr, crs, transform, 255, {"product": product, "date": x})
                refs.append({"kind": "water", "product": product, "date": x, "nisar_date": d, "offset_days": _days(x, d),
                             "track": track, "observed_fraction": round(cover, 4), "granules": ids, "path": rel})
                print(f"{product}: {d} <- {x} (±{_days(x, d)} d, cover {cover:.0%}, {track})")
            if product != "DSWX_S1":
                continue
            # change-validation candidates: every radar water map within ±MAX_DAYS_RTC (pairs are formed per orbit)
            for x in sorted(by_date):
                if _days(x, d) > MAX_DAYS_RTC:
                    continue
                urls = [u for u in (opera.layer_url(g, "_B01_WTR.tif") for g in by_date[x]) if u]
                paths = opera.download(urls, raw / product.lower())
                wtr = opera.mosaic_to_grid(paths, crs, transform, shape, nodata=255)
                cover = float((inside & np.isin(wtr, valid)).sum() / inside.sum())
                if cover < min_obs:
                    continue
                with rasterio.open(paths[0]) as s:
                    track = s.tags().get("RTC_TRACK_NUMBER")
                rel = f"processed/reference/{a.area}/{product.lower()}_{x}.tif"
                if not (config.DATA_DIR / rel).exists():
                    opera.write_cog(config.DATA_DIR / rel, wtr, crs, transform, 255, {"product": product, "date": x})
                refs.append({"kind": "water_change_candidate", "product": product, "date": x, "nisar_date": d,
                             "offset_days": _days(x, d), "track": track, "observed_fraction": round(cover, 4),
                             "granules": [g["id"] for g in by_date[x]], "path": rel})

    # --- C-band backscatter (RTC-S1 VV), every track near every NISAR date
    grans = opera.search("RTC_S1", area["bbox"], lo, hi)
    groups: dict[tuple, list[dict]] = {}
    for g in grans:
        groups.setdefault((g["date"], g["track"]), []).append(g)
    # keep, per track, the closest pass to each NISAR date, and only tracks usable for a change pair
    chosen: dict[tuple, list[str]] = {}
    for track in {t for _, t in groups}:
        per_date = {}
        for d in dates:
            cands = [x for (x, t) in groups if t == track and _days(x, d) <= MAX_DAYS_RTC]
            if cands:
                per_date[d] = min(cands, key=lambda x: _days(x, d))
        if len(set(per_date.values())) >= 2:
            for d, x in per_date.items():
                chosen.setdefault((x, track), []).append(d)
    for (x, track), near in sorted(chosen.items()):
        gs = groups[(x, track)]
        urls = [u for u in (opera.layer_url(g, "_VV.tif") for g in gs) if u]
        try:
            paths = opera.download(urls, raw / "rtc_s1" / x)
        except Exception as ex:  # noqa: BLE001 - e.g. ASF EULA not yet accepted for this Earthdata account
            print(f"RTC_S1 {x} track {track}: download failed ({type(ex).__name__}: {str(ex)[:120]})")
            continue
        vv = opera.mosaic_to_grid(paths, crs, transform, shape, nodata=np.nan, resampling=Resampling.bilinear, dtype="float32")
        cover = float((inside & np.isfinite(vv) & (vv > 0)).sum() / inside.sum())
        if cover < 0.5:
            print(f"RTC_S1 {x} track {track}: cover {cover:.0%}, skipped")
            continue
        rel = f"processed/reference/{a.area}/rtc_s1_vv_t{track:03d}_{x}.tif"
        opera.write_cog(config.DATA_DIR / rel, vv, crs, transform, np.nan, {"product": "RTC_S1", "date": x, "track": track, "polarization": "VV"})
        refs.append({"kind": "cband", "product": "RTC_S1", "polarization": "VV", "date": x, "track": track, "nisar_dates": near,
                     "observed_fraction": round(cover, 4), "granules": [g["id"] for g in gs], "path": rel})
        print(f"RTC_S1 {x} track {track}: {len(gs)} bursts, cover {cover:.0%}")

    # land-cover and historical-water layers on the same grid, so analyses never read remote global tiles
    from backend.validation import reference_data

    for kind, fn, nod in (("worldcover", reference_data.worldcover, 0), ("jrc", reference_data.jrc_occurrence, 255)):
        arr = fn(crs, transform, shape)
        if arr is not None:
            rel = f"processed/reference/{a.area}/{kind}.tif"
            opera.write_cog(config.DATA_DIR / rel, arr, crs, transform, nod, {"product": kind})
            refs.append({"kind": kind, "path": rel})
            print(f"{kind}: written")
    storage.write_text(f"reference/references_{a.area}.json", json.dumps(refs, indent=1))
    print(f"{len(refs)} references written")


if __name__ == "__main__":
    main()
