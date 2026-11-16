"""Shrink data_bundle/ to fit a 500 MB serverless function (with ~185 MB of Python dependencies).

Keeps: the four featured analyses; the Sylhet featured-pair NISAR frames (so a live Sylhet re-run works);
water references, land cover, JRC and population for Sylhet; true-colour images at the featured dates for every
area; every JSON. Drops: other stored analyses, other frames, Sentinel-1 RTC rasters (stored analyses keep their
C-band comparison; a live re-run reports C-band as unavailable). Registry entries are pruned to what ships.
Usage: .venv/bin/python scripts/slim_bundle.py [data_bundle]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

B = Path(sys.argv[1] if len(sys.argv) > 1 else "data_bundle").resolve()
KEEP_ANALYSES = {"sylhet_monsoon", "okavango_featured", "tonle_sap_featured", "atchafalaya_featured"}

for d in (B / "processed/analyses").iterdir():
    if d.name not in KEEP_ANALYSES:
        shutil.rmtree(d)

# frames: only the Sylhet featured pair
res = json.loads((B / "processed/analyses/sylhet_monsoon/result.json").read_text())
keep_frames = {res["earlier"]["id"], res["later"]["id"]}
obs = json.loads((B / "reference/observations.json").read_text())
for o in obs:
    if o["id"] not in keep_frames:
        o["processed"] = {}
        shutil.rmtree(B / "processed/observations" / o["id"], ignore_errors=True)
(B / "reference/observations.json").write_text(json.dumps(obs, indent=2))

# references: featured-date true colour everywhere; Sylhet keeps its validation/context rasters; no RTC rasters
for refs_path in (B / "reference").glob("references_*.json"):
    area = refs_path.stem.removeprefix("references_")
    refs = json.loads(refs_path.read_text())
    an = {"sylhet_haor": "sylhet_monsoon"}.get(area, f"{area}_featured")
    rp = B / "processed/analyses" / an / "result.json"
    hls_dates = set()
    if rp.exists():
        r = json.loads(rp.read_text())
        hls_dates = {a["date"] for a in r["validation"]["accuracy"] if a["product"] == "DSWX_HLS"}
    kept = []
    for r in refs:
        f = B / r["path"]
        keep = (r["kind"] == "hls_rgb" and r.get("date") in hls_dates) or \
               (area == "sylhet_haor" and r["kind"] in ("water", "water_change_candidate", "worldcover", "jrc", "worldpop"))
        if keep and f.exists():
            kept.append(r)
        elif f.exists():
            f.unlink()
    refs_path.write_text(json.dumps(kept, indent=1))
# true-colour images are display-only: store them JPEG-compressed (about 10x smaller)
import rasterio  # noqa: E402
from rasterio.shutil import copy as rcopy  # noqa: E402

for f in B.glob("processed/reference/*/hls_rgb_*.tif"):
    with rasterio.open(f) as src:
        done = (src.compression and src.compression.name.upper() == "JPEG")
    if not done:
        tmp = f.with_suffix(".jpeg.tif")
        rcopy(f, tmp, driver="COG", compress="JPEG", quality=85)
        tmp.replace(f)
for p in sorted(B.rglob("*"), reverse=True):  # remove empty dirs
    if p.is_dir() and not any(p.iterdir()):
        p.rmdir()
total = sum(p.stat().st_size for p in B.rglob("*") if p.is_file())
print(f"bundle now {total / 1e6:.1f} MB")
