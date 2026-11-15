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
    ap.add_argument("--analyses", nargs="*", default=["sylhet_monsoon", "sylhet_late", "sylhet_demo"], help="stored analysis ids to upload")
    ap.add_argument("--terms", nargs="*", default=["A_HHHH"], help="processed frame layers to upload (HV is not used by default analyses)")
    ap.add_argument("--area", default="sylhet_haor")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files: list[tuple[str, Path]] = []
    obs = json.loads((config.DATA_DIR / "reference/observations.json").read_text())
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
    refs_path = config.REFERENCE_DIR / f"references_{a.area}.json"
    refs = json.loads(refs_path.read_text()) if refs_path.exists() else []
    for r in refs:
        if r["kind"] == "water" or (r["date"], r["track"]) in used_cband:
            files.append((r["path"], config.DATA_DIR / r["path"]))
    extra_json = [f"reference/references_{a.area}.json", f"reference/water_timeline_{a.area}.json"]

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
