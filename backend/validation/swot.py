"""Lake water-level change from NASA/CNES SWOT between the passes closest to two NISAR dates.

For each SWOT pass, the observation dates nearest each NISAR date (within MAX_DAYS) are paired, and the
change in water-surface elevation (WSE) is computed per lake for lakes observed on both dates. This is
an altimetric measurement (height), independent of every water-extent map.
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np

from backend import storage

MAX_DAYS = 7


def _days(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


BUFFERS_M = (0, 100, 250, 500, 1000)


def _buffered(geom: dict, crs, buffer_m: float) -> dict:
    """Buffer a lon/lat polygon by metres (in the raster's projected CRS) and return lon/lat GeoJSON."""
    import shapely
    from pyproj import Transformer
    from shapely.geometry import mapping, shape

    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    inv = Transformer.from_crs(crs, 4326, always_xy=True)
    g = shapely.transform(shape(geom), lambda c: np.column_stack(fwd.transform(c[:, 0], c[:, 1])))
    g = g.buffer(buffer_m)
    return mapping(shapely.transform(g, lambda c: np.column_stack(inv.transform(c[:, 0], c[:, 1]))))


def lake_area_agreement(data: dict, pairs: list[dict], water_e, water_l, crs, transform, px_km2: float) -> dict:
    """Per-lake open-water area and area change: NISAR (inside each lake's outline) vs SWOT.

    Prior Lake Database outlines are dry-season extents, while SWOT assigns flood water around them to the
    lake. The outline buffer is therefore chosen so NISAR's *earlier-date* total lake area best matches SWOT's.
    The change comparison is never used to pick it, so the change scores are not tuned.
    """
    from backend.preprocessing.georeferencing import polygon_mask

    lakes = []
    for pp in pairs:
        ser = {s["date"]: s for s in next(p for p in data["passes"] if p["pass"] == pp["pass"])["series"]}
        se = {o["id"]: o for o in ser[pp["earlier_date"]]["obs"]}
        sl = {o["id"]: o for o in ser[pp["later_date"]]["obs"]}
        lakes += [(lk, pp["pass"], se[lk]["area_km2"], sl[lk]["area_km2"]) for lk in set(se) & set(sl) if data.get("outlines", {}).get(lk)]
    if len(lakes) < 5:
        return {"status": "unavailable", "lakes": len(lakes)}

    def measure(buf: float):
        rows = []
        for lk, ps, swe, swl in lakes:
            m = polygon_mask(_buffered(data["outlines"][lk], crs, buf), crs, transform, water_e.shape)
            if m.sum() < 25:
                continue
            ne, nl = float((water_e & m).sum() * px_km2), float((water_l & m).sum() * px_km2)
            rows.append({"lake_id": lk, "pass": ps, "nisar_earlier_km2": round(ne, 3), "nisar_change_km2": round(nl - ne, 3),
                         "swot_earlier_km2": swe, "swot_change_km2": round(swl - swe, 3)})
        return rows

    trials = {buf: measure(buf) for buf in BUFFERS_M}
    swot_total = {buf: sum(r["swot_earlier_km2"] for r in rows) for buf, rows in trials.items()}
    buf = min(trials, key=lambda b: abs(sum(r["nisar_earlier_km2"] for r in trials[b]) - swot_total[b]) if len(trials[b]) >= 5 else 1e9)
    rows = trials[buf]
    if len(rows) < 5:
        return {"status": "unavailable", "lakes": len(rows)}

    def corr(x, y):
        x, y = np.asarray(x), np.asarray(y)
        return round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() > 0 and y.std() > 0 else None

    def rank(x):
        return np.argsort(np.argsort(np.asarray(x)))

    a = [r["nisar_change_km2"] for r in rows]
    b = [r["swot_change_km2"] for r in rows]
    return {"status": "available", "lakes": len(rows), "outline_buffer_m": buf,
            "earlier_area_r": corr([r["nisar_earlier_km2"] for r in rows], [r["swot_earlier_km2"] for r in rows]),
            "nisar_earlier_total_km2": round(sum(r["nisar_earlier_km2"] for r in rows), 2),
            "swot_earlier_total_km2": round(sum(r["swot_earlier_km2"] for r in rows), 2),
            "change_r": corr(a, b), "change_spearman": corr(rank(a), rank(b)),
            "same_sign_fraction": round(float(np.mean(np.sign(a) == np.sign(b))), 3),
            "nisar_total_change_km2": round(float(np.sum(a)), 2), "swot_total_change_km2": round(float(np.sum(b)), 2),
            "rows": rows}


def lake_level_change(area_id: str, earlier: str, later: str) -> dict:
    text = storage.read_text(f"reference/swot_{area_id}.json")
    if not text:
        return {"status": "unavailable", "reason": "No SWOT lake data has been fetched for this area."}
    data = json.loads(text)
    passes = []
    for p in data["passes"]:
        ser = [s for s in p["series"] if s.get("obs")]
        e = min(ser, key=lambda s: _days(s["date"], earlier), default=None)
        l = min(ser, key=lambda s: _days(s["date"], later), default=None)
        if not e or not l or e is l or _days(e["date"], earlier) > MAX_DAYS or _days(l["date"], later) > MAX_DAYS:
            continue
        lo = {o["id"]: o for o in l["obs"]}
        d = [lo[o["id"]]["wse_m"] - o["wse_m"] for o in e["obs"] if o["id"] in lo]
        if len(d) < 3:
            continue
        d = np.array(d)
        unc = float(np.median([o["wse_u_m"] for o in e["obs"]] + [o["wse_u_m"] for o in l["obs"]]))
        passes.append({"pass": p["pass"], "earlier_date": e["date"], "later_date": l["date"], "lakes": int(d.size),
                       "median_change_m": round(float(np.median(d)), 2), "p25_m": round(float(np.percentile(d, 25)), 2),
                       "p75_m": round(float(np.percentile(d, 75)), 2),
                       "fraction_falling": round(float((d < 0).mean()), 3), "median_uncertainty_m": round(unc, 3)})
    if not passes:
        return {"status": "unavailable", "reason": f"No SWOT pass observed the same lakes within ±{MAX_DAYS} days of both NISAR dates."}
    return {"status": "available", "product": data["product"], "passes": passes, "_data": data,
            "note": "SWOT KaRIn water-surface elevation of Prior Lake Database lakes (quality good/suspect, not partial). "
                    "Change is computed per lake between the SWOT dates closest to the two NISAR passes."}
