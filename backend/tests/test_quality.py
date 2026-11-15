from backend.preprocessing.quality import check_pair

FP = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
FP_FAR = {"type": "Polygon", "coordinates": [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]]}


def obs(i, date, **kw):
    base = {"id": i, "sensor": "NISAR", "product_type": "GCOV", "product_version": "1.0", "start_time": f"{date}T00:00:00Z",
            "date": date, "track": 10, "frame": 5, "pass_direction": "ASCENDING", "polarizations": {"A": ["HH", "HV"]},
            "range_bandwidth_mhz": {"A": "20"}, "footprint": FP}
    base.update(kw)
    return base


def codes(c):
    return {e["code"] for e in c.errors}


def test_compatible_pair():
    c = check_pair(obs("a", "2026-10-01"), obs("b", "2026-10-13"), "A", "HH")
    assert c.ok, c.errors


def test_reversed_dates():
    assert "date_order" in codes(check_pair(obs("a", "2026-10-13"), obs("b", "2026-10-01"), "A", "HH"))


def test_polarization_missing():
    c = check_pair(obs("a", "2026-10-01"), obs("b", "2026-10-13", polarizations={"A": ["HH"]}), "A", "HV")
    assert "polarization_unavailable" in codes(c)


def test_geometry_mismatch_blocks_unless_allowed():
    e, l = obs("a", "2026-10-01"), obs("b", "2026-10-13", track=11, pass_direction="DESCENDING")
    assert "geometry_differs" in codes(check_pair(e, l, "A", "HH"))
    c = check_pair(e, l, "A", "HH", allow_cross_geometry=True)
    assert c.ok and any(w["code"] == "geometry_differs" for w in c.warnings)


def test_no_overlap():
    assert "no_overlap" in codes(check_pair(obs("a", "2026-10-01"), obs("b", "2026-10-13", footprint=FP_FAR), "A", "HH"))


def test_sensor_mismatch():
    assert "sensor_mismatch" in codes(check_pair(obs("a", "2026-10-01"), obs("b", "2026-10-13", sensor="RCM"), "A", "HH"))
