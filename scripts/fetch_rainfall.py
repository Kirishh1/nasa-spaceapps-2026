"""Daily area-mean rainfall for a study area from NASA GPM IMERG Late daily V07 (GES DISC), via NASA's
Earthdata cloud OPeNDAP service. Writes reference/rainfall_<area>.json, read by the API (no runtime calls).

Usage: .venv/bin/python scripts/fetch_rainfall.py --area sylhet_haor --start 2026-06-01 --end 2026-11-15
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import storage  # noqa: E402
from backend.environmental_context import precipitation as gpm  # noqa: E402
from backend.ingestion import registry  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-15")
    a = ap.parse_args()
    area = registry.get_study_area(a.area)
    opener = gpm._opener()
    if opener is None:
        sys.exit("EARTHDATA_TOKEN missing")
    d0, d1 = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    with ThreadPoolExecutor(8) as ex:
        recs = list(ex.map(lambda d: gpm.daily_mean_cloud(d, tuple(area["bbox"]), opener), days))
    series = [r for r in recs if r]
    missing = [d.isoformat() for d, r in zip(days, recs) if not r]
    storage.write_text(f"reference/rainfall_{a.area}.json", json.dumps({"study_area": a.area, "bbox": area["bbox"], "series": series, "missing_days": missing}, indent=1))
    tot = sum(r["mean_mm"] for r in series)
    print(f"{len(series)} days retrieved, {len(missing)} missing; season total {tot:.0f} mm (area mean)")


if __name__ == "__main__":
    main()
