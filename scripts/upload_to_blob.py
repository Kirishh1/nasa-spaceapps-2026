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
    ap.add_argument("--analyses", nargs="*", default=["sylhet_demo"], help="stored analysis ids to upload")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files: list[tuple[str, Path]] = []
    obs = json.loads((config.DATA_DIR / "reference/observations.json").read_text())
    for o in obs:  # make every layer path relative so it resolves inside the store
        for layers in (o.get("processed") or {}).values():
            for rec in layers.values():
                rel = config.to_data_relative(config.resolve_data_path(rec["path"]))
                rec["path"] = rel
                files.append((rel, config.DATA_DIR / rel))
        for area in (o.get("processed") or {}):
            meta = config.DATA_DIR / "processed/observations" / o["id"] / "metadata.json"
            if meta.exists():
                files.append((config.to_data_relative(meta), meta))
    for aid in a.analyses:
        d = config.analysis_dir(aid)
        if not (d / "result.json").exists():
            sys.exit(f"analysis {aid} not found in {d}")
        files += [(f"processed/analyses/{aid}/{f.name}", f) for f in sorted(d.iterdir(), key=lambda f: f.name == "result.json")]

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
    storage.write_text("reference/study_areas.json", (config.DATA_DIR / "reference/study_areas.json").read_text())
    storage.write_text("reference/observations.json", json.dumps(obs, indent=2))  # last: registry points at uploaded files
    print("done")


if __name__ == "__main__":
    main()
