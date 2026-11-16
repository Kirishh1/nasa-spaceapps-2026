"""Upload the processed demo data from data/ to the Vercel Blob store used by the deployed API.

Usage (from repo root, after scripts/fetch_demo.py):
    .venv/bin/python scripts/upload_to_blob.py                       # registry, frames, stored analysis "sylhet_demo"
    .venv/bin/python scripts/upload_to_blob.py --analyses sylhet_demo other_id
    .venv/bin/python scripts/upload_to_blob.py --dry-run

Credentials: BLOB_READ_WRITE_TOKEN in .env (copy it from the Blob store's page in the Vercel dashboard).
SARPULSE_BLOB_ACCESS must match the store (default "private"); SARPULSE_BLOB_PREFIX defaults to "sarpulse".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config, storage  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyses", nargs="*", default=None,
                    help="stored analysis ids (default: the Sylhet analyses plus <area>_featured for every other area)")
    ap.add_argument("--terms", nargs="*", default=["A_HHHH"], help="processed frame layers to upload (HV is not used by default analyses)")
    ap.add_argument("--areas", nargs="*", default=None, help="study areas (default: all in the registry)")
    ap.add_argument("--all", action="store_true", help="re-upload files that are already in the store")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stage", help="copy the same files into this directory (e.g. data_bundle) instead of uploading")
    a = ap.parse_args()
    areas = a.areas or [x["id"] for x in json.loads((config.DATA_DIR / "reference/study_areas.json").read_text())]
    if a.analyses is None:
        a.analyses = ["sylhet_monsoon", "sylhet_recession", "sylhet_optical_check", "sylhet_late", "sylhet_demo"] + \
            [f"{x}_featured" for x in areas if x != "sylhet_haor" and config.analysis_dir(f"{x}_featured").joinpath("result.json").exists()]

    files: list[tuple[str, Path]] = []
    obs = json.loads((config.DATA_DIR / "reference/observations.json").read_text())
    # Frames: every processed frame for the main study area; for other areas only the frames the uploaded analyses use
    # (Blob storage is limited). Registry entries for frames that are not uploaded are dropped from the uploaded copy.
    used_frames = set()
    for aid in a.analyses:
        rp = config.analysis_dir(aid) / "result.json"
        if rp.exists():
            rr = json.loads(rp.read_text())
            used_frames |= {rr["earlier"]["id"], rr["later"]["id"]}
    for o in obs:
        for area_id in list((o.get("processed") or {})):
            if area_id != "sylhet_haor" and o["id"] not in used_frames:
                del o["processed"][area_id]
    for o in obs:  # make every layer path relative so it resolves inside the store
        for layers in (o.get("processed") or {}).values():
            for key, rec in layers.items():
                rel = config.to_data_relative(config.resolve_data_path(rec["path"]))
                rec["path"] = rel
                if key in a.terms:
                    files.append((rel, config.DATA_DIR / rel))
        for area in (o.get("processed") or {}):
            meta = config.DATA_DIR / "processed/observations" / o["id"] / "metadata.json"
            if meta.exists():
                files.append((config.to_data_relative(meta), meta))
    used_cband: set[tuple] = set()
    for aid in a.analyses:
        d = config.analysis_dir(aid)
        if not (d / "result.json").exists():
            sys.exit(f"analysis {aid} not found in {d}")
        res = json.loads((d / "result.json").read_text())
        sc = res.get("sensor_comparison") or {}
        if sc.get("status") == "available":
            used_cband |= {(sc["earlier"]["date"], sc["earlier"]["track"]), (sc["later"]["date"], sc["later"]["track"])}
        files += [(f"processed/analyses/{aid}/{f.name}", f) for f in sorted(d.iterdir(), key=lambda f: f.name == "result.json")]

    # OPERA references: every water map (small) and only the C-band passes the uploaded analyses use
    extra_json = []
    for area in areas:
        refs_path = config.REFERENCE_DIR / f"references_{area}.json"
        refs = json.loads(refs_path.read_text()) if refs_path.exists() else []
        for r in refs:
            if r["kind"] in ("water", "water_change_candidate", "jrc", "worldcover", "worldpop", "hls_rgb") or (r["kind"] == "cband" and (r["date"], r["track"]) in used_cband):  # HAND is not used at runtime
                files.append((r["path"], config.DATA_DIR / r["path"]))
        extra_json += [f"reference/{n}_{area}.json" for n in ("references", "water_timeline", "rainfall", "swot", "nisar_season", "soil_moisture")]
    extra_json += [f"reference/diagnostics_{aid}.json" for aid in a.analyses]

    files = [(rel, p) for rel, p in dict.fromkeys(files) if p.exists()]
    if a.stage:
        import shutil

        root = Path(a.stage).resolve()
        if root.exists():
            shutil.rmtree(root)
        for rel, p in files:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, root / rel)
        for rel in extra_json + ["reference/study_areas.json"]:
            if (config.DATA_DIR / rel).exists():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(config.DATA_DIR / rel, root / rel)
        (root / "reference/observations.json").write_text(json.dumps(obs, indent=2))
        total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        print(f"staged {len(files)} files, {total / 1e6:.1f} MB -> {root}")
        return
    if not a.all and not a.dry_run:  # skip files already in the store (same path and size)
        storage.MODE = "blob"
        start = len(storage.PREFIX) + 1
        have = {b.pathname[start:]: b.size for b in storage._blob().query_blobs(prefix=f"{storage.PREFIX}/")}
        files = [(rel, p) for rel, p in files if have.get(rel) != p.stat().st_size or rel.startswith("processed/analyses/")]
    total = sum(p.stat().st_size for _, p in files)
    print(f"{len(files)} files, {total / 1e6:.1f} MB -> Blob prefix '{storage.PREFIX}/' (access={storage.ACCESS})")
    if a.dry_run:
        for rel, p in files:
            print(f"  {p.stat().st_size / 1e6:7.1f} MB  {rel}")
        return

    storage.MODE = "blob"
    for rel, p in files:
        storage.upload_file(rel, p)
        print(f"  uploaded {rel}")
    for rel in extra_json:
        if (config.DATA_DIR / rel).exists():
            storage.write_text(rel, (config.DATA_DIR / rel).read_text())
    storage.write_text("reference/study_areas.json", (config.DATA_DIR / "reference/study_areas.json").read_text())
    storage.write_text("reference/observations.json", json.dumps(obs, indent=2))  # last: registry points at uploaded files
    print("done")


if __name__ == "__main__":
    main()
