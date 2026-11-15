import numpy as np
import pytest
from rasterio.transform import from_origin

from backend.comparison.disagreement import AGREE_DECREASE, ONLY_A, OPPOSITE, compare
from backend.comparison.sensor_comparison import aggregate_classes
from backend.preprocessing.calibration import lee_filter, linear_to_db, speckle_filter
from backend.preprocessing.georeferencing import pixel_area_m2
from backend.processing import change_detection as cd
from backend.processing import inundation as inu
from backend.processing.statistics import change_statistics


def test_linear_to_db():
    out = linear_to_db(np.array([1.0, 0.1, 0.01, 0.0, -1.0, np.nan], dtype="float32"))
    np.testing.assert_allclose(out[:3], [0.0, -10.0, -20.0], atol=1e-5)
    assert np.isnan(out[3:]).all()


def test_delta_sign_and_nodata():
    e = np.array([[-10.0, -10.0, np.nan]])
    l = np.array([[-20.0, -5.0, -5.0]])
    d = cd.difference_db(e, l)
    assert d[0, 0] == pytest.approx(-10.0)  # later darker -> negative
    assert d[0, 1] == pytest.approx(5.0)
    assert np.isnan(d[0, 2])


def test_classify_threshold_and_mask():
    d = np.array([[-3.0, -2.9, 0.0, 2.9, 3.0, np.nan]])
    cls = cd.classify(d, 3.0)
    assert cls.tolist() == [[cd.DECREASE, cd.LIMITED, cd.LIMITED, cd.LIMITED, cd.INCREASE, cd.NODATA]]
    mask = np.array([[True, True, True, True, False, True]])
    assert cd.classify(d, 3.0, mask)[0, 4] == cd.NODATA
    with pytest.raises(ValueError):
        cd.classify(d, 0)


def test_speckle_filters_preserve_nan_and_constant():
    a = np.full((20, 20), 0.05, dtype="float32")
    a[5, 5] = np.nan
    for m in ("lee", "boxcar"):
        out = speckle_filter(a, m, 5, 4)
        assert np.isnan(out[5, 5])
        np.testing.assert_allclose(out[np.isfinite(out)], 0.05, rtol=1e-5)


def test_lee_reduces_variance():
    rng = np.random.default_rng(0)
    a = rng.gamma(4, 0.05 / 4, size=(100, 100)).astype("float32")
    assert lee_filter(a, 7, 4).std() < a.std()


def test_inundation_rules():
    cls = np.full((10, 10), cd.LIMITED, "uint8")
    later = np.full((10, 10), -10.0)
    cls[0:4, 0:4] = cd.DECREASE
    later[0:4, 0:4] = -22.0      # 16-pixel water-like region
    cls[9, 9] = cd.DECREASE
    later[9, 9] = -22.0          # isolated pixel -> removed
    cls[6:8, 0:2] = cd.DECREASE  # decrease but not water-like
    out, info = inu.potential_inundation(cls, later, -18.0, min_pixels=4)
    assert (out[0:4, 0:4] == inu.OPEN_WATER).all()
    assert out[9, 9] == inu.NONE
    assert (out[6:8, 0:2] == inu.NONE).all()
    assert info["vegetated_flooding_evaluated"] is False
    lc = np.full((10, 10), 40, "uint8")
    lc[6:10, 6:10] = 90
    cls[6:9, 6:9] = cd.INCREASE
    out2, _ = inu.potential_inundation(cls, later, -18.0, 4, lc)
    assert (out2[6:9, 6:9] == inu.VEGETATED).all()


def test_statistics_area_from_transform():
    t = from_origin(500000, 4000000, 20, 20)
    px = pixel_area_m2(t, "EPSG:32615")
    assert px == 400.0
    cls = np.full((100, 100), cd.LIMITED, "uint8")
    cls[:10, :] = cd.DECREASE
    cls[-5:, :] = cd.NODATA
    mask = np.ones_like(cls, bool)
    d = np.where(cls == cd.DECREASE, -5.0, 0.0).astype("float32")
    d[cls == cd.NODATA] = np.nan
    s = change_statistics(d, cls, np.where(cls > 0, inu.NONE, 0), mask, px, d, d)
    assert s["analyzed_area_km2"] == pytest.approx(10000 * 400 / 1e6)
    assert s["valid_pixels"] == 9500
    assert s["classes"]["significant_decrease"]["area_km2"] == pytest.approx(1000 * 400 / 1e6)
    assert s["missing_area_km2"] == pytest.approx(500 * 400 / 1e6)
    assert sum(s["histogram"]["counts"]) == 9500


def test_pixel_area_requires_projected():
    with pytest.raises(ValueError):
        pixel_area_m2(from_origin(0, 0, 0.001, 0.001), "EPSG:4326")


def test_sensor_comparison():
    a = np.full((8, 8), cd.LIMITED, "uint8")
    b = a.copy()
    a[:4, :4] = cd.DECREASE
    b[:4, :4] = cd.DECREASE
    a[4:, :4] = cd.DECREASE
    a[:4, 4:] = cd.INCREASE
    b[:4, 4:] = cd.DECREASE
    agg_a, agg_b = aggregate_classes(a, 4), aggregate_classes(b, 4)
    out, s = compare(agg_a, agg_b)
    assert out[0, 0] == AGREE_DECREASE and out[1, 0] == ONLY_A and out[0, 1] == OPPOSITE
    assert s["compared_cells"] == 4


def test_multilook_block_mean_and_coverage():
    from backend.ingestion.nisar import _multilook

    a = np.array([[1, 3, 2, np.nan], [1, 3, np.nan, np.nan]], dtype="float32")
    out = _multilook(a, 2)
    assert out[0, 0] == pytest.approx(2.0)
    assert np.isnan(out[0, 1])  # only 1 of 4 valid


def test_noise_reference_gaussian():
    from backend.processing.statistics import noise_reference

    rng = np.random.default_rng(0)
    d = rng.normal(0, 1.5, (400, 400)).astype("float32")
    cls = np.full(d.shape, cd.LIMITED, "uint8")
    r = noise_reference(d, cls, 3.0)
    assert r["robust_sigma_db"] == pytest.approx(1.5, rel=0.02)
    assert r["observed_exceedance_percent"] == pytest.approx(r["expected_exceedance_percent_gaussian"], abs=0.3)


def test_data_paths_relative_and_legacy_absolute():
    from backend import config

    assert config.resolve_data_path("processed/x.tif") == config.DATA_DIR / "processed/x.tif"
    legacy = "/Users/someone/elsewhere/data/processed/observations/a/b.tif"
    assert config.resolve_data_path(legacy) == config.DATA_DIR / "processed/observations/a/b.tif"
    assert config.to_data_relative(config.DATA_DIR / "processed" / "y.tif") == "processed/y.tif"


def test_binary_metrics_known_values():
    from backend.validation.accuracy import binary_metrics

    pred = np.array([1, 1, 1, 0, 0, 0, 0, 0], bool)
    ref = np.array([1, 1, 0, 1, 0, 0, 0, 0], bool)
    m = binary_metrics(pred, ref, np.ones(8, bool))
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 4)
    assert m["precision"] == pytest.approx(2 / 3, abs=1e-4) and m["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["iou"] == pytest.approx(0.5) and m["overall_accuracy"] == pytest.approx(0.75)
    assert m["kappa"] == pytest.approx(0.4667, abs=1e-3)
    empty = binary_metrics(np.zeros(4, bool), np.zeros(4, bool), np.ones(4, bool))
    assert empty["precision"] is None and empty["iou"] is None


def test_otsu_and_water_change():
    from backend.processing import water as w

    rng = np.random.default_rng(3)
    db = np.where(rng.random((200, 200)) < 0.4, rng.normal(-22, 1.0, (200, 200)), rng.normal(-9, 1.5, (200, 200)))
    t = w.otsu_threshold(db)
    assert -18 < t < -13
    valid = np.ones(db.shape, bool)
    e = w.water_map(db, t, valid)
    assert abs((e == w.WATER).mean() - 0.4) < 0.02
    later = e.copy()
    later[:10] = w.LAND
    ch = w.water_change(e, later)
    assert (ch[:10][e[:10] == w.WATER] == w.WATER_LOST).all()
    assert (ch[10:][e[10:] == w.WATER] == w.PERSISTENT_WATER).all()


def test_db_layers_roundtrip_int16(tmp_path):
    import rasterio
    from rasterio.transform import from_origin

    from backend.processing.pipeline import _write_cog

    a = np.array([[-12.345, 0.0, np.nan], [3.21, -25.0, 7.777]], dtype="float32")
    p = tmp_path / "x.tif"
    _write_cog(p, a, from_origin(500000, 4000000, 20, 20), "EPSG:32646", np.nan, db=True)
    with rasterio.open(p) as s:
        assert s.dtypes[0] == "int16" and s.scales[0] == pytest.approx(0.01)
        raw = s.read(1)
        back = np.where(raw == s.nodata, np.nan, raw * s.scales[0])
    assert np.isnan(back[0, 2])
    np.testing.assert_allclose(back[np.isfinite(a)], a[np.isfinite(a)], atol=0.006)


def test_dilate_square():
    from backend.processing.pipeline import _dilate

    m = np.zeros((7, 7), bool)
    m[3, 3] = True
    d = _dilate(m, 2)
    assert d.sum() == 25 and d[1, 1] and d[5, 5] and not d[0, 3]
