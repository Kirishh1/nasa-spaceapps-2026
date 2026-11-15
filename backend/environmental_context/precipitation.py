"""NASA GPM IMERG precipitation context.

Uses IMERG Late Run daily (GPM_3IMERGDL v07, ~0.1°, latency about 14 hours) through the GES DISC OPeNDAP
server, subset to the study-area bounding box. Final Run is preferred when available (~3.5-month latency).
Requires Earthdata Login (EARTHDATA_TOKEN). Values are area-mean daily precipitation (mm/day) over
grid cells whose centres fall in the bbox; nothing is reported for days that could not be retrieved.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request

import numpy as np

from backend import config

# NASA Earthdata cloud OPeNDAP (Hyrax) for GES DISC collections: subsets server-side, returns CSV.
CLOUD_OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{concept}/granules/{prod}:{fname}.dap.csv?dap4.ce=/precipitation%5B0:1:0%5D%5B{i0}:1:{i1}%5D%5B{j0}:1:{j1}%5D"
CLOUD_PRODUCTS = [  # (CMR concept id, short name with version, file template, run)
    ("C2723754859-GES_DISC", "GPM_3IMERGDL.07", "3B-DAY-L.MS.MRG.3IMERG.{d}-S000000-E235959.{v}.nc4", "Late Run"),
]

PRODUCTS = [
    ("GPM_3IMERGDF.07", "3B-DAY.MS.MRG.3IMERG.{d}-S000000-E235959.{v}.nc4", "Final Run"),
    ("GPM_3IMERGDL.07", "3B-DAY-L.MS.MRG.3IMERG.{d}-S000000-E235959.{v}.nc4", "Late Run"),
]
VERSIONS = ("V07C", "V07B")  # file-name minor versions seen on GES DISC
BASE = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/{prod}/{y}/{m}/{fname}"
CACHE = config.ANALYSES_DIR.parent / "gpm_cache.json"  # ANALYSES_DIR is always writable (/tmp on Vercel)


def _opener():
    token = os.environ.get("EARTHDATA_TOKEN")
    if not token:
        return None
    op = urllib.request.build_opener()
    op.addheaders = [("Authorization", f"Bearer {token}")]
    return op


def _idx(lo: float, hi: float, origin: float, res: float = 0.1) -> tuple[int, int]:
    return int(np.floor((lo - origin) / res)), int(np.ceil((hi - origin) / res)) - 1


def _parse_ascii(text: str) -> list[float]:
    vals: list[float] = []
    body = text.split("\n", 1)[1] if "\n" in text else text
    for line in body.splitlines():
        if line.startswith("[") and "," in line:
            vals += [float(v) for v in line.split(",")[1:] if v.strip()]
        elif line.strip() == "" and vals:
            break
    return vals


def _parse_dap_csv(text: str) -> list[float]:
    vals: list[float] = []
    for line in text.splitlines():
        if line.startswith("/precipitation["):
            vals += [float(v) for v in line.split(",")[1:] if v.strip()]
    return vals


def daily_mean_cloud(day: dt.date, bbox, opener, timeout: float = 30) -> dict | None:
    """Area-mean daily precipitation via NASA's cloud OPeNDAP service (GES DISC IMERG Late daily)."""
    w, s, e, n = bbox
    i0, i1 = _idx(w, e, -180.0)
    j0, j1 = _idx(s, n, -90.0)
    i1, j1 = max(i0, i1), max(j0, j1)
    for concept, prod, tmpl, run in CLOUD_PRODUCTS:
        for ver in VERSIONS:
            fname = tmpl.format(d=day.strftime("%Y%m%d"), v=ver)
            url = CLOUD_OPENDAP.format(concept=concept, prod=prod, fname=fname, i0=i0, i1=i1, j0=j0, j1=j1)
            try:
                with opener.open(url, timeout=timeout) as r:
                    vals = np.array(_parse_dap_csv(r.read().decode()))
            except urllib.error.HTTPError as ex:
                if ex.code in (401, 403):
                    raise PermissionError("NASA Earthdata refused the token for GES DISC data (HTTP %d)." % ex.code) from ex
                continue
            except Exception:  # noqa: BLE001
                continue
            vals = vals[(vals >= 0) & np.isfinite(vals)]
            if vals.size:
                return {"date": day.isoformat(), "mean_mm": round(float(vals.mean()), 3), "max_mm": round(float(vals.max()), 3),
                        "cells": int(vals.size), "product": f"{prod} {ver}", "run": run}
    return None


def stored_series(area_id: str) -> list[dict]:
    """Precomputed daily series from scripts/fetch_rainfall.py (reference/rainfall_<area>.json)."""
    from backend import storage

    text = storage.read_text(f"reference/rainfall_{area_id}.json")
    return json.loads(text)["series"] if text else []


def daily_mean(day: dt.date, bbox: tuple[float, float, float, float], opener, timeout: float = 15) -> dict | None:
    w, s, e, n = bbox
    i0, i1 = _idx(w, e, -180.0)
    j0, j1 = _idx(s, n, -90.0)
    i1, j1 = max(i0, i1), max(j0, j1)
    # Final Run appears ~3.5 months after the fact; try Late Run first for recent days.
    products = PRODUCTS if (dt.date.today() - day).days > 110 else PRODUCTS[::-1]
    for (prod, tmpl, run), ver in ((p, v) for p in products for v in VERSIONS):
        fname = tmpl.format(d=day.strftime("%Y%m%d"), v=ver)
        url = BASE.format(prod=prod, y=day.year, m=f"{day.month:02d}", fname=fname) + f".ascii?precipitation[0:0][{i0}:{i1}][{j0}:{j1}]"
        try:
            with opener.open(url, timeout=timeout) as r:
                vals = np.array(_parse_ascii(r.read().decode()))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError(
                    "GES DISC refused the Earthdata token (HTTP %d). Approve the 'NASA GESDISC DATA ARCHIVE' "
                    "application in your Earthdata profile (Applications → Authorized Apps)." % e.code
                ) from e
            continue
        except Exception:  # noqa: BLE001 - try next product / version
            continue
        vals = vals[(vals >= 0) & np.isfinite(vals)]
        if vals.size:
            return {"date": day.isoformat(), "mean_mm": round(float(vals.mean()), 3), "max_mm": round(float(vals.max()), 3), "cells": int(vals.size), "product": f"{prod} {ver}", "run": run}
    return None


def summarize(series: list[dict], earlier_date: str, later_date: str, pad_days: int = 7, missing: list[str] | None = None, bbox=None) -> dict:
    d0 = (dt.date.fromisoformat(earlier_date) - dt.timedelta(days=pad_days)).isoformat()
    series = [r for r in series if d0 <= r["date"] <= later_date]
    if not series:
        return {"status": "unavailable", "reason": "No GPM IMERG daily values cover these dates."}

    def window(end: str, days: int) -> dict:
        end_d = dt.date.fromisoformat(end)
        sel = [r for r in series if end_d - dt.timedelta(days=days) < dt.date.fromisoformat(r["date"]) <= end_d]
        return {"days_requested": days, "days_available": len(sel), "total_mm": round(sum(r["mean_mm"] for r in sel), 1) if sel else None}

    between = [r for r in series if earlier_date < r["date"] <= later_date]
    return {
        "status": "available",
        "source": "NASA GPM IMERG Late Run daily V07 (GES DISC, via NASA Earthdata cloud OPeNDAP)",
        "bbox": bbox,
        "series": series,
        "missing_days": missing or [],
        "before_earlier_7d": window(earlier_date, 7),
        "before_later_7d": window(later_date, 7),
        "between_acquisitions": {"days_available": len(between), "total_mm": round(sum(r["mean_mm"] for r in between), 1) if between else None},
        "caveat": "Area-mean satellite precipitation estimates at ~10 km. Coincidence with radar change does not establish causation.",
    }


def precipitation_context(bbox, earlier_date: str, later_date: str, pad_days: int = 7, budget_s: float = 45, area_id: str | None = None) -> dict:
    if area_id:
        stored = stored_series(area_id)
        if stored and stored[0]["date"] <= earlier_date and stored[-1]["date"] >= later_date:
            return summarize(stored, earlier_date, later_date, pad_days, bbox=bbox)
    opener = _opener()
    if opener is None:
        return {"status": "unavailable", "reason": "GPM retrieval requires EARTHDATA_TOKEN in .env; no precipitation values are shown."}
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    key_bbox = ",".join(f"{v:.3f}" for v in bbox)
    d0 = dt.date.fromisoformat(earlier_date) - dt.timedelta(days=pad_days)
    d1 = min(dt.date.fromisoformat(later_date), dt.date.today() - dt.timedelta(days=1))
    import time

    deadline = time.monotonic() + budget_s
    series, missing = [], []
    d = d0
    while d <= d1:
        if time.monotonic() > deadline:
            missing.append(d.isoformat())
            d += dt.timedelta(days=1)
            continue
        k = f"{key_bbox}|{d}"
        try:
            rec = cache.get(k) or daily_mean_cloud(d, bbox, opener) or daily_mean(d, bbox, opener)
        except PermissionError as e:
            return {"status": "unavailable", "reason": str(e)}
        if rec:
            cache[k] = rec
            series.append(rec)
        else:
            missing.append(d.isoformat())
            if not series and len(missing) >= 2:
                return {"status": "unavailable", "reason": "GES DISC OPeNDAP returned no IMERG data for the first requested days "
                        "(server unreachable, files not yet published, or the Earthdata account lacks GES DISC authorization)."}
        d += dt.timedelta(days=1)
    try:
        CACHE.write_text(json.dumps(cache))
    except OSError:
        pass
    if not series:
        return {"status": "unavailable", "reason": "No GPM IMERG daily files could be retrieved for this period.", "missing_days": missing}

    def window(end: str, days: int) -> dict:
        end_d = dt.date.fromisoformat(end)
        sel = [r for r in series if end_d - dt.timedelta(days=days) < dt.date.fromisoformat(r["date"]) <= end_d]
        return {"days_requested": days, "days_available": len(sel), "total_mm": round(sum(r["mean_mm"] for r in sel), 2) if sel else None}

    between = [r for r in series if earlier_date < r["date"] <= later_date]
    return {
        "status": "available",
        "source": "NASA GPM IMERG daily (GES DISC)",
        "bbox": bbox,
        "series": series,
        "missing_days": missing,
        "before_earlier_7d": window(earlier_date, 7),
        "before_later_7d": window(later_date, 7),
        "between_acquisitions": {"days_available": len(between), "total_mm": round(sum(r["mean_mm"] for r in between), 2) if between else None},
        "caveat": "Area-mean satellite precipitation estimates at ~10 km. Coincidence with radar change does not establish causation.",
    }
