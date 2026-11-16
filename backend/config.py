"""Central configuration: paths and constants shared across the backend."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

# A deployment can ship its data inside the bundle (data_bundle/, built by scripts/upload_to_blob.py --stage);
# when present it is used read-only and takes precedence over remote storage.
BUNDLE_DIR = REPO_ROOT / "data_bundle"
BUNDLED = bool(os.environ.get("VERCEL")) and "SARPULSE_DATA_DIR" not in os.environ and (BUNDLE_DIR / "reference" / "study_areas.json").exists()
DATA_DIR = Path(os.environ.get("SARPULSE_DATA_DIR", BUNDLE_DIR if BUNDLED else REPO_ROOT / "data")).resolve()
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
# Results that ship with the data (read-only is fine) ...
STORED_ANALYSES_DIR = PROCESSED_DIR / "analyses"
# ... and where new analyses are written. On Vercel only /tmp is writable, so default there.
_default_results = Path("/tmp/sarpulse/analyses") if os.environ.get("VERCEL") else STORED_ANALYSES_DIR
ANALYSES_DIR = Path(os.environ.get("SARPULSE_RESULTS_DIR", _default_results)).resolve()

STUDY_AREAS_FILE = REFERENCE_DIR / "study_areas.json"
OBSERVATIONS_FILE = REFERENCE_DIR / "observations.json"

for _d in (RAW_DIR, PROCESSED_DIR, REFERENCE_DIR, ANALYSES_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:  # read-only filesystem (e.g. serverless); writes go to ANALYSES_DIR only
        pass


def analysis_dir(analysis_id: str) -> Path:
    """Directory of an analysis: newly computed results first, then results shipped with the data."""
    for base in (ANALYSES_DIR, STORED_ANALYSES_DIR):
        d = base / analysis_id
        if (d / "result.json").exists():
            return d
    return ANALYSES_DIR / analysis_id


def resolve_data_path(p: str) -> Path:
    """Stored layer paths are relative to DATA_DIR; older absolute paths are remapped onto it."""
    path = Path(p)
    if not path.is_absolute():
        return DATA_DIR / path
    if path.exists():
        return path
    parts = path.parts
    if "data" in parts:
        return DATA_DIR.joinpath(*parts[len(parts) - parts[::-1].index("data"):])
    return path


def to_data_relative(p: str | Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(DATA_DIR))
    except ValueError:
        return str(p)

CMR_URL = "https://cmr.earthdata.nasa.gov/search"

# Collection concept IDs confirmed by querying CMR (2026-11-14).
NISAR_GCOV_COLLECTIONS = {
    "NISAR_L2_GCOV_V1": "C3622241360-ASF",            # validated, from 2025-10-28
    "NISAR_L2_GCOV_PROVISIONAL_V1": "C2854338529-ASF",
    "NISAR_L2_GCOV_BETA_V1": "C3622214170-ASF",
}
DEFAULT_NISAR_COLLECTION = "NISAR_L2_GCOV_V1"
