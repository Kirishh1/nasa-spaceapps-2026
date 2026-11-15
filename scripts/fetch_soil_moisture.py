"""Daily basin-mean soil moisture from NASA SMAP L3 Enhanced (SPL3SMP_E, 9 km EASE-Grid 2.0), via NASA's
Earthdata cloud OPeNDAP service (server-side subset). AM and PM retrievals are averaged where valid.
SMAP does not retrieve soil moisture over open water, so flooded cells are missing by design.
Writes reference/soil_moisture_<area>.json.

Usage: .venv/bin/python scripts/fetch_soil_moisture.py --area sylhet_haor --start 2026-06-01 --end 2026-11-15
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from pyproj import Transformer  # noqa: E402

from backend import storage  # noqa: E402
from backend.environmental_context.precipitation import _opener  # noqa: E402
from backend.ingestion import registry  # noqa: E402

CONCEPT = "C2938664763-NSIDC_CPRD"
CELL, X0, Y0 = 9008.055210146, -17367530.44, 7314540.83  # EASE-Grid 2.0 global 9 km
URL = "https://opendap.earthdata.nasa.gov/collections/{c}/granules/{g}.dap.csv?dap4.ce={v}%5B{r0}:1:{r1}%5D%5B{c0}:1:{c1}%5D"


def main() -> None:
    import earthaccess

    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-15")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    w, s, e, n = area["bbox"]
    t = Transformer.from_crs(4326, 6933, always_xy=True)
    xs, ys = t.transform([w, e], [s, n])
    c0, c1 = sorted(int((x - X0) / CELL) for x in xs)
    r0, r1 = sorted(int((Y0 - y) / CELL) for y in ys)
    earthaccess.login(strategy="environment")
    grans = earthaccess.search_data(short_name="SPL3SMP_E", temporal=(a.start, a.end))
    op = _opener()

    def one(g):
        ur = g["umm"]["GranuleUR"]
        date = g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10]
        vals = []
        for var in ("/Soil_Moisture_Retrieval_Data_AM/soil_moisture", "/Soil_Moisture_Retrieval_Data_PM/soil_moisture_pm"):
            try:
                txt = op.open(URL.format(c=CONCEPT, g=ur, v=var, r0=r0, r1=r1, c0=c0, c1=c1), timeout=60).read().decode()
            except Exception:  # noqa: BLE001
                continue
            for line in txt.splitlines():
                if line.startswith("/Soil"):
                    vals += [float(x) for x in line.split(",")[1:] if x.strip()]
        v = np.array(vals)
        v = v[(v >= 0) & (v <= 1)]
        return {"date": date, "mean_m3m3": round(float(v.mean()), 4), "cells": int(v.size)} if v.size else {"date": date, "mean_m3m3": None, "cells": 0}

    with ThreadPoolExecutor(8) as ex:
        series = sorted(ex.map(one, grans), key=lambda r: r["date"])
    valid = [r for r in series if r["mean_m3m3"] is not None]
    storage.write_text(f"reference/soil_moisture_{a.area}.json", json.dumps({"study_area": a.area, "product": "SPL3SMP_E", "grid_rows": [r0, r1], "grid_cols": [c0, c1], "series": series}, indent=1))
    print(f"{len(valid)} of {len(series)} days with valid retrievals")
    import collections
    m = collections.defaultdict(list)
    for r in valid:
        m[r["date"][:7]].append(r["mean_m3m3"])
    print({k: (round(float(np.mean(v)), 3), len(v)) for k, v in sorted(m.items())})


if __name__ == "__main__":
    main()
