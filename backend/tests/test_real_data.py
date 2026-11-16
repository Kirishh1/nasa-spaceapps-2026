"""Tests on REAL NISAR results (the stored Sylhet analysis). Skipped when data/ is not present (e.g. CI clone).

They recompute headline numbers from the stored rasters, so a figure in the README or app cannot drift
from what the data say.
"""
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from backend.processing import water

# the test session isolates SARPULSE_DATA_DIR in a temp dir; real data lives in the repo's data/ folder
D = Path(__file__).resolve().parents[2] / "data/processed/analyses/sylhet_monsoon"
pytestmark = pytest.mark.skipif(not (D / "result.json").exists(), reason="real analysis data not present")


def _res():
    return json.loads((D / "result.json").read_text())


def test_water_change_areas_match_raster():
    r = _res()
    with rasterio.open(D / "water_change.tif") as s:
        wc = s.read(1)
        px = abs(s.transform.a * s.transform.e) / 1e6
    assert r["earlier"]["date"] == "2026-06-18" and r["later"]["date"] == "2026-10-16"
    assert abs((wc == water.WATER_LOST).sum() * px - r["water"]["lost_km2"]) < 0.05
    assert abs((wc == water.WATER_GAINED).sum() * px - r["water"]["gained_km2"]) < 0.05
    assert 300 < r["water"]["lost_km2"] < 315 and 5 < r["water"]["gained_km2"] < 15


def test_same_product_version_and_track():
    r = _res()
    assert r["earlier"]["product_version"] == r["later"]["product_version"]
    assert r["earlier"]["track"] == r["later"]["track"]
    assert abs(r["validation"]["radiometric_stability"]["median_delta_db"]) <= 0.5


def test_landcover_agreement_has_counts_and_intervals():
    rows = {x["class"]: x for x in _res()["sensor_comparison"]["by_landcover"]}
    wet = rows[90]
    assert wet["cells"] > 10000 and wet["agree_percent_ci95"][0] < wet["agree_percent"] < wet["agree_percent_ci95"][1]
    total = sum(wet[k] for k in ("agree_stable", "agree_decrease", "agree_increase", "only_l", "only_c", "opposite"))
    assert total == wet["cells"]


def test_optical_validation_is_single_date_not_change():
    v = _res()["validation"]
    for a in v["accuracy"]:
        assert "open_water" in a and a["nisar_date"] in ("2026-06-18", "2026-10-16")
    assert all("water_lost" in c for c in v["change_accuracy"])
    best_change = max(c["water_lost"]["f1"] or 0 for c in v["change_accuracy"])
    best_date = max(a["open_water"]["f1"] or 0 for a in v["accuracy"])
    assert best_change < best_date  # the change score is reported separately and is lower


def test_impact_numbers_consistent():
    im = _res()["impact"]
    assert im["cropland_emerged_km2"] <= _res()["water"]["lost_km2"]
    assert im["people_within_1km_of_receded_water"] <= im["people_in_area"]
    assert np.isfinite(im["volume_change_km3_approx"])
