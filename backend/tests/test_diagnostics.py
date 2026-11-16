"""Synthetic-raster tests for the validation diagnostics (no satellite data needed)."""
import numpy as np

from backend.comparison import disagreement as dis
from backend.processing.change_detection import DECREASE, INCREASE, LIMITED
from backend.validation import diagnostics as dg


def test_landcover_detail_separates_stable_from_change_agreement():
    a = np.full((100, 100), LIMITED, "uint8")
    b = a.copy()
    lc = np.full((100, 100), 10, "uint8")
    lc[:, 50:] = 90
    # wetland half: both decrease on a quarter, C-only change on another quarter
    a[:50, 50:] = DECREASE
    b[:50, 50:] = DECREASE
    b[50:, 50:] = INCREASE
    rows = {r["class"]: r for r in dg.landcover_agreement_detail(a, b, lc, {10: "Tree", 90: "Wetland"}, block=10, n_boot=50)}
    tree, wet = rows[10], rows[90]
    assert tree["agree_percent"] == 100 and tree["agree_stable_percent"] == 100 and tree["agree_change_percent"] == 0
    assert wet["agree_percent"] == 50 and wet["agree_change_percent"] == 50 and wet["c_band_only_percent"] == 50
    assert wet["agree_percent_ci95"][0] <= 50 <= wet["agree_percent_ci95"][1]
    assert wet["cells"] == 5000 and wet["agree_decrease"] == 2500


def test_kappa_is_zero_for_independent_maps_and_one_for_identical():
    rng = np.random.default_rng(1)
    a = rng.choice([DECREASE, LIMITED, INCREASE], size=(200, 200)).astype("uint8")
    b = rng.choice([DECREASE, LIMITED, INCREASE], size=(200, 200)).astype("uint8")
    assert abs(dg._kappa3(a, b)) < 0.03
    assert dg._kappa3(a, a) == 1.0


def test_edge_buffer_excludes_boundary_pixels():
    w = np.zeros((40, 40), bool)
    w[10:30, 10:30] = True
    valid = np.ones_like(w)
    edges = dg.boundary(w, valid)
    assert edges[10, 20] and edges[9, 20] and not edges[20, 20] and not edges[0, 0]
    pred = w.copy()
    ref = np.zeros_like(w)
    ref[11:29, 11:29] = True  # reference lacks a 1-pixel rim
    rows = dg.edge_buffer_change_f1(pred, ref, valid, edges, radii=(0, 2))
    assert rows[0]["f1"] < 1.0 and rows[1]["f1"] == 1.0 and rows[1]["kept_fraction"] < rows[0]["kept_fraction"]


def test_agreement_codes_cover_all_cases():
    a = np.array([[LIMITED, DECREASE, INCREASE, DECREASE, LIMITED, DECREASE]], "uint8")
    b = np.array([[LIMITED, DECREASE, INCREASE, LIMITED, INCREASE, INCREASE]], "uint8")
    out, stats = dis.compare(a, b)
    assert out.tolist() == [[dis.AGREE_STABLE, dis.AGREE_DECREASE, dis.AGREE_INCREASE, dis.ONLY_A, dis.ONLY_B, dis.OPPOSITE]]
    assert stats["overall_agreement_percent"] == 50.0
