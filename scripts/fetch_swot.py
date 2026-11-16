"""Independent water-level evidence from NASA/CNES SWOT (KaRIn interferometric altimetry): lake water-surface
elevation (WSE) and area for Prior Lake Database lakes in the study area, through the season.

SWOT measures water height directly. This is a different physical quantity and a different instrument from every
water-extent map in the app, so it is the closest available independent check on whether the wetlands drained.

* Product: SWOT_L2_HR_LakeSP_prior_D (NASA PO.DAAC), continent-wide shapefiles per pass.
* Passes over the area are detected from the first 21-day cycle, then only those passes are fetched.
* Kept: quality_f <= 1 (good/suspect), partial_f == 0, valid WSE and area; lakes seen on >= 60% of a pass's dates.
Writes reference/swot_<area>.json.

Usage: .venv/bin/python scripts/fetch_swot.py --area sylhet_haor --start 2026-06-01 --end 2026-11-15
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from backend import config, storage  # noqa: E402
from backend.ingestion import registry  # noqa: E402

SHORT_NAME = "SWOT_L2_HR_LakeSP_prior_D"
FILL = -1e9


def read_geometries(path: Path, bbox) -> dict[str, dict]:
    """Prior Lake Database outlines (lon/lat GeoJSON) for lakes in bbox."""
    from pyogrio.raw import read
    from shapely import wkb
    from shapely.geometry import mapping

    meta, _, geoms, fields = read(f"/vsizip/{path}", bbox=tuple(bbox), read_geometry=True)
    if geoms is None or not len(geoms):
        return {}
    ids = dict(zip(meta["fields"], fields))["lake_id"]
    return {str(i): mapping(wkb.loads(bytes(g))) for i, g in zip(ids, geoms) if g is not None}


def read_lakes(path: Path, bbox) -> list[dict]:
    from pyogrio.raw import read

    meta, _, _, fields = read(f"/vsizip/{path}", bbox=tuple(bbox), read_geometry=False)
    if not fields or not len(fields[0]):
        return []
    d = dict(zip(meta["fields"], fields))
    out = []
    for i in range(len(d["lake_id"])):
        wse, area = float(d["wse"][i]), float(d["area_total"][i])
        if wse <= FILL or area <= FILL or int(d["quality_f"][i]) > 1 or int(d["partial_f"][i]) != 0:
            continue
        out.append({"lake_id": str(d["lake_id"][i]), "name": str(d["lake_name"][i] or ""), "time": str(d["time_str"][i]),
                    "wse_m": round(wse, 3), "wse_u_m": round(float(d["wse_u"][i]), 3), "area_km2": round(area, 4),
                    "quality_f": int(d["quality_f"][i])})
    return out


def main() -> None:
    import earthaccess

    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-15")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    bbox = area["bbox"]
    earthaccess.login(strategy="environment")
    grans = earthaccess.search_data(short_name=SHORT_NAME, temporal=(a.start, a.end), bounding_box=tuple(bbox))
    pass_of = lambda g: re.search(r"_\d{3}_(\d{3})_[A-Z]{2}_", g["umm"]["GranuleUR"]).group(1)  # noqa: E731
    raw = config.RAW_DIR / "swot"

    # 1) detect passes that observe lakes here, from the first cycle
    first_end = (dt.date.fromisoformat(a.start) + dt.timedelta(days=21)).isoformat()
    first = [g for g in grans if g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10] <= first_end]
    passes = set()
    for g, f in zip(first, earthaccess.download(first, local_path=str(raw)) if first else []):
        if read_lakes(Path(f), bbox):
            passes.add(pass_of(g))
    print("passes observing lakes here:", sorted(passes))

    # 2) all cycles for those passes
    sel = [g for g in grans if pass_of(g) in passes]
    files = earthaccess.download(sel, local_path=str(raw)) if sel else []
    by_pass: dict[str, dict[str, list[dict]]] = {}
    granules: dict[str, list[str]] = {}
    outlines: dict[str, dict] = {}
    for g, f in zip(sel, files):
        outlines.update(read_geometries(Path(f), bbox))
        p = pass_of(g)
        date = g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10]
        lakes = read_lakes(Path(f), bbox)
        if lakes:
            by_pass.setdefault(p, {}).setdefault(date, []).extend(lakes)
            granules.setdefault(p, []).append(g["umm"]["GranuleUR"])

    # 3) per pass: a stable set of lakes, then total area and median WSE change through time
    out = {"study_area": a.area, "product": SHORT_NAME, "passes": [], "outlines": {}}
    for p, dates in sorted(by_pass.items()):
        counts: dict[str, int] = {}
        for lakes in dates.values():
            for lk in {x["lake_id"] for x in lakes}:
                counts[lk] = counts.get(lk, 0) + 1
        stable = {lk for lk, n in counts.items() if n >= 0.6 * len(dates)}
        if len(stable) < 3:
            continue
        first_wse: dict[str, float] = {}
        series = []
        for date in sorted(dates):
            obs = {x["lake_id"]: x for x in dates[date] if x["lake_id"] in stable}
            for lk, x in obs.items():
                first_wse.setdefault(lk, x["wse_m"])
            dwse = [x["wse_m"] - first_wse[lk] for lk, x in obs.items()]
            series.append({"date": date, "lakes": len(obs), "total_area_km2": round(sum(x["area_km2"] for x in obs.values()), 2),
                           "obs": [{"id": lk, "wse_m": x["wse_m"], "wse_u_m": x["wse_u_m"], "area_km2": x["area_km2"]} for lk, x in obs.items()],
                           "median_wse_change_m": round(float(np.median(dwse)), 3) if dwse else None,
                           "median_wse_u_m": round(float(np.median([x["wse_u_m"] for x in obs.values()])), 3) if obs else None})
        out["passes"].append({"pass": p, "stable_lakes": len(stable), "granules": granules[p], "series": series})
        out["outlines"].update({lk: outlines[lk] for lk in stable if lk in outlines})
        print(f"pass {p}: {len(stable)} stable lakes, {len(series)} dates: " +
              ", ".join(f"{s['date']} {s['total_area_km2']} km² Δwse {s['median_wse_change_m']} m ({s['lakes']})" for s in series))
    storage.write_text(f"reference/swot_{a.area}.json", json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
