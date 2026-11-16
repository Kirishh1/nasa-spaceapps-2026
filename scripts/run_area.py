"""End-to-end processing of one study area from scripts/demo_areas.json.

1. Stream every NISAR frame of the area's stack (only the study-area window is read).
2. Fetch OPERA water references for every NISAR date (no C-band yet).
3. Compute NISAR's season series (water fraction + per-date validation).
4. Choose the featured pair from evidence: the largest change in NISAR open-water fraction between two dates that
   both have an independent reference (optical preferred). The choice uses NISAR water fractions and reference
   availability only, never agreement scores, so validation is not tuned by the selection.
5. Fetch C-band near the chosen dates, the OPERA timeline, SWOT, GPM rainfall, SMAP soil moisture and context layers.
6. Run the analysis for the featured pair (analysis id "<area>_featured").

Usage: .venv/bin/python scripts/run_area.py --area okavango
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PY = sys.executable


def run(*args: str) -> None:
    print(f"$ {' '.join(args)}", flush=True)
    subprocess.run([PY, *args], cwd=ROOT, check=True)


def choose_pair(area_id: str) -> tuple[str, str]:
    """The season span: earliest and latest NISAR dates that both have an independent reference (optical preferred).

    Deliberately not "the largest change": that rule picks out whichever date has the noisiest water estimate.
    The span uses only dates and reference availability, never agreement scores or NISAR results."""
    from backend import storage

    season = json.loads(storage.read_text(f"reference/nisar_season_{area_id}.json"))["series"]
    for need in ({"DSWX_HLS"}, None):
        dates = sorted({e["date"] for e in season
                        if e["validation"] and (need is None or need & {v["product"] for v in e["validation"]})})
        if len(dates) >= 2:
            return dates[0], dates[-1]
    dates = sorted({e["date"] for e in season})
    return dates[0], dates[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--skip-frames", action="store_true")
    ap.add_argument("--from-pair", action="store_true", help="skip frames and references; recompute pair onwards")
    a = ap.parse_args()
    area = a.area
    if not (a.skip_frames or a.from_pair):
        run("scripts/fetch_demo.py", "--area", area, "--max-granules", "20")
    if not a.from_pair:
        run("scripts/fetch_reference.py", "--area", area, "--no-rtc")
    run("scripts/nisar_season.py", "--area", area)

    e, l = choose_pair(area)
    print(f"featured pair for {area}: {e} -> {l}", flush=True)
    run("scripts/fetch_reference.py", "--area", area, "--rtc-dates", e, l)
    run("scripts/opera_timeline.py", "--area", area, "--start", "2026-06-01", "--end", "2026-11-15")
    from backend import storage
    from backend.ingestion import references

    refs = json.loads(storage.read_text(f"reference/references_{area}.json"))
    hls = sorted({r["date"] for d in (e, l) for r in references.water_refs(refs, d) if r["product"] == "DSWX_HLS"})
    for script in ("fetch_swot.py", "fetch_rainfall.py", "fetch_soil_moisture.py", "fetch_context.py"):
        extra = ["--hls-dates", *hls] if script == "fetch_context.py" else []
        try:
            run(f"scripts/{script}", "--area", area, *extra)
        except subprocess.CalledProcessError as ex:  # context layers are optional; report and continue
            print(f"WARNING: {script} failed for {area}: {ex}", flush=True)

    from backend.ingestion import registry
    from backend.processing.pipeline import run_analysis

    ar = registry.get_study_area(area)
    ar["featured_pair"] = [e, l]
    registry.upsert_study_area(ar)
    obs = {o["date"]: o["id"] for o in sorted(registry.observations(), key=lambda o: o["id"])  # newest reprocessing wins
           if registry.has_processed_layer(o, area, "A", "HHHH")}
    r = run_analysis(area, obs[e], obs[l], {}, analysis_id=f"{area}_featured")
    w, v = r["water"], r["validation"]
    print(json.dumps({"area": area, "pair": [e, l], "water_km2": [w["earlier_km2"], w["later_km2"]], "lost": w["lost_km2"], "gained": w["gained_km2"],
                      "f1": [(x["product"], x["date"], x["open_water"]["f1"]) for x in v["accuracy"]],
                      "calibration_db": v["radiometric_stability"].get("median_delta_db"),
                      "swot": [(p["pass"], p["median_change_m"]) for p in (v.get("swot") or {}).get("passes", [])],
                      "lc_agree": (r["sensor_comparison"].get("stats") or {}).get("overall_agreement_percent")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
