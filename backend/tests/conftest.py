"""Test configuration: isolate the data directory before backend modules are imported.

All rasters created here are synthetic test fixtures and are never shown in the application.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="sarpulse-test-")
os.environ["SARPULSE_DATA_DIR"] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
