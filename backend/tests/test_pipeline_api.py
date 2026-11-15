"""End-to-end test on a *synthetic* GCOV-structured HDF5 fixture (test-only; never shown in the app)."""
import h5py
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.ingestion import nisar, registry

EPSG = 32615
X0, Y0, DX = 600000.0, 3300000.0, 20.0
N = 200


def make_gcov(path, hh, date):
    with h5py.File(path, "w") as f:
        g = f.create_group("/science/LSAR/GCOV/grids/frequencyA")
        g["xCoordinates"] = X0 + DX / 2 + DX * np.arange(N)
        g["yCoordinates"] = Y0 - DX / 2 - DX * np.arange(N)
        g["xCoordinateSpacing"] = DX
        g["yCoordinateSpacing"] = -DX
        p = g.create_dataset("projection", data=np.uint32(EPSG))
        p.attrs["epsg_code"] = EPSG
        d = g.create_dataset("HHHH", data=hh.astype("float32"))
        d.attrs["units"] = b"1"
        d.attrs["_FillValue"] = np.float32(np.nan)  # as in real GCOV files
        g["HVHV"] = (hh * 0.2).astype("float32")
        m = np.ones((N, N), "uint8")
        m[:, :5] = 255
        g["mask"] = m
        g["numberOfLooks"] = np.full((N, N), 4.0, "float32")
        i = f.create_group("/science/LSAR/identification")
        i["zeroDopplerStartTime"] = f"{date}T12:00:00".encode()
        i["trackNumber"] = 10
        i["productType"] = b"GCOV"


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    from rasterio.warp import transform_bounds

    tmp = tmp_path_factory.mktemp("gcov")
    rng = np.random.default_rng(1)
    base = rng.gamma(8, 0.05 / 8, (N, N))
    later = base.copy()
    later[50:120, 50:120] = rng.gamma(8, 0.003 / 8, (70, 70))  # dark patch (≈ -25 dB)
    files = []
    for name, arr, date in (("e", base, "2026-10-01"), ("l", later, "2026-10-13")):
        p = tmp / f"{name}.h5"
        make_gcov(p, arr, date)
        files.append((name, p, date))
    w, s, e, n = transform_bounds(f"EPSG:{EPSG}", "EPSG:4326", X0, Y0 - N * DX, X0 + N * DX, Y0)
    ring = [[w, s], [e, s], [e, n], [w, n], [w, s]]
    area = {"id": "test", "name": "Synthetic test area", "bbox": [w, s, e, n], "geometry": {"type": "Polygon", "coordinates": [ring]}}
    registry.upsert_study_area(area)
    for name, p, date in files:
        meta = nisar.inspect_gcov(p)
        assert meta["frequencies"]["A"]["epsg"] == EPSG
        assert set(meta["frequencies"]["A"]["covariance_terms"]) == {"HHHH", "HVHV"}
        rec = nisar.export_term_cog(p, config.PROCESSED_DIR / f"{name}_HHHH.tif", "A", "HHHH", tuple(area["bbox"]))
        assert rec["median_looks"] == 4.0
        registry.upsert_observation({
            "id": name, "sensor": "NISAR", "band": "L", "product_type": "GCOV", "product_version": "t", "date": date,
            "start_time": f"{date}T12:00:00Z", "track": 10, "frame": 1, "pass_direction": "ASCENDING",
            "polarizations": {"A": ["HH", "HV"]}, "range_bandwidth_mhz": {"A": "20"}, "footprint": area["geometry"],
            "processed": {"test": {"A_HHHH": rec}}, "file_metadata": meta,
        })
    return area


CFG = {"include_precipitation": False, "include_reference": False, "min_region_m2": 4000}


def test_pipeline_detects_dark_patch(setup):
    from backend.processing.pipeline import run_analysis

    r = run_analysis("test", "e", "l", CFG)
    s = r["statistics"]
    assert s["pixel_area_m2"] == 400.0
    # the 70x70 dark patch (4900 px) should be flagged as decrease and as potential open water
    assert 4000 < s["classes"]["significant_decrease"]["pixels"] < 5600
    assert s["potential_inundation"]["open_water"]["pixels"] > 4000
    assert s["missing_pixels"] >= 5 * N  # masked columns
    assert r["validation"]["independently_validated"] is False


def test_api_flow(setup):
    from backend.api.main import app

    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    obs = c.get("/api/observations", params={"study_area": "test"}).json()["observations"]
    assert all(o["available_for_analysis"] for o in obs)
    bad = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "l", "later_id": "e", "config": CFG})
    assert bad.status_code == 422 and any(e["code"] == "date_order" for e in bad.json()["errors"])
    hv = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "e", "later_id": "l", "config": {**CFG, "polarization": "HV"}})
    assert hv.status_code == 422 and any(e["code"] == "not_ingested" for e in hv.json()["errors"])
    rcm = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "e", "later_id": "l", "sensor": "RCM"})
    assert rcm.status_code == 422
    ok = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "e", "later_id": "l", "config": CFG})
    assert ok.status_code == 202
    aid = ok.json()["id"]
    import time

    for _ in range(100):
        st = c.get(f"/api/analysis/{aid}").json()
        if st["status"] != "running":
            break
        time.sleep(0.1)
    assert st["status"] == "complete", st
    layers = c.get(f"/api/analysis/{aid}/layers").json()["layers"]
    assert {l["id"] for l in layers} >= {"earlier_db", "later_db", "delta_db", "change_class", "inundation"}
    w, s, e, n = layers[0]["bounds"]
    lon, lat = (w + e) / 2, (s + n) / 2
    px = c.get(f"/api/analysis/{aid}/pixel", params={"lon": lon, "lat": lat}).json()
    assert px["values"]["change_class"] == 1 and px["values"]["delta_db"] < -3
    import morecantile

    t = morecantile.tms.get("WebMercatorQuad").tile(lon, lat, 13)
    for lid in ("delta_db", "change_class"):
        resp = c.get(f"/api/tiles/{aid}/{lid}/{t.z}/{t.x}/{t.y}.png")
        assert resp.status_code == 200 and resp.content[:4] == b"\x89PNG"


def test_api_sync_mode(setup, monkeypatch):
    from backend.api.main import app
    from backend.api.routes import analysis as route

    monkeypatch.setattr(route, "SYNC", True)
    c = TestClient(app)
    r = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "e", "later_id": "l", "config": CFG})
    assert r.status_code == 200 and r.json()["status"] == "complete"
    aid = r.json()["id"]
    assert c.get(f"/api/analysis/{aid}").json()["status"] == "complete"
    assert any(a["id"] == aid for a in c.get("/api/analyses", params={"study_area": "test"}).json())


def test_sources_lists_nasa_resources(setup):
    from backend.api.main import app

    c = TestClient(app)
    s = c.get("/api/sources").json()
    ids = {r["id"]: r for r in s["nasa"]}
    assert ids["nisar_gcov"]["status"] == "used" and "C3622241360-ASF" in ids["nisar_gcov"]["identifier"]
    assert ids["gpm_imerg"]["status"] in ("used", "integrated")
    assert all(r["links"] or r["id"] in ("rcm", "basemaps") for r in s["nasa"] + s["other"])


def test_water_maps_validated_against_reference(setup):
    """A synthetic DSWx-S1-style reference marking the dark patch as open water (class 1) must score highly."""
    import json

    import rasterio

    from backend import config, storage
    from backend.ingestion import opera
    from backend.processing.pipeline import run_analysis

    with rasterio.open(config.PROCESSED_DIR / "l_HHHH.tif") as s:
        crs, transform, shape = s.crs, s.transform, (s.height, s.width)
    ref = np.zeros(shape, "uint8")              # 0 = not water
    ref[50:120, 50:120] = 1                     # 1 = open water: the dark patch of the later frame
    ref[:, :5] = 255                            # no data where NISAR is masked
    rel = "processed/reference/test/dswx_s1_2026-10-13.tif"
    opera.write_cog(config.DATA_DIR / rel, ref, crs, transform, 255)
    storage.write_text("reference/references_test.json", json.dumps([
        {"kind": "water", "product": "DSWX_S1", "date": "2026-10-13", "nisar_date": "2026-10-13", "offset_days": 0,
         "track": "41", "observed_fraction": 0.97, "granules": ["synthetic"], "path": rel}]))
    r = run_analysis("test", "e", "l", {**CFG, "min_region_m2": 0})
    w = r["water"]
    assert w["gained_km2"] > 1.5 and w["lost_km2"] < 0.1          # 70x70 px x 400 m2 = 1.96 km2 of new water
    acc = r["validation"]["accuracy"]
    assert len(acc) == 1 and acc[0]["side"] == "later"
    m = acc[0]["open_water"]
    assert m["precision"] > 0.9 and m["recall"] > 0.9 and m["iou"] > 0.85
    assert len(acc[0]["threshold_sensitivity"]) == 7
    assert r["validation"]["independently_validated"] is True
    storage.write_text("reference/references_test.json", "[]")
