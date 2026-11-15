"""Central configuration: paths and constants shared across the backend."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.environ.get("SARPULSE_DATA_DIR", REPO_ROOT / "data")).resolve()
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
ANALYSES_DIR = PROCESSED_DIR / "analyses"

STUDY_AREAS_FILE = REFERENCE_DIR / "study_areas.json"
OBSERVATIONS_FILE = REFERENCE_DIR / "observations.json"

for _d in (RAW_DIR, PROCESSED_DIR, REFERENCE_DIR, ANALYSES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CMR_URL = "https://cmr.earthdata.nasa.gov/search"

# Collection concept IDs confirmed by querying CMR (2026-11-14).
NISAR_GCOV_COLLECTIONS = {
    "NISAR_L2_GCOV_V1": "C3622241360-ASF",            # validated, from 2025-10-28
    "NISAR_L2_GCOV_PROVISIONAL_V1": "C2854338529-ASF",
    "NISAR_L2_GCOV_BETA_V1": "C3622214170-ASF",
}
DEFAULT_NISAR_COLLECTION = "NISAR_L2_GCOV_V1"
