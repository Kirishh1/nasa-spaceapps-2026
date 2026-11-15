"""Blob storage mode against an in-memory fake of the vercel.blob sync SDK (no network)."""
import contextlib
import json
import types

import pytest

from backend import storage
from backend.tests.test_pipeline_api import CFG, setup  # noqa: F401  (module fixture reused)


class FakeBlob(types.SimpleNamespace):
    class BlobNotFoundError(Exception):
        pass

    def __init__(self):
        super().__init__(store={}, puts=[])

    def put_blob(self, pathname, body, *, access, content_type=None, allow_overwrite=False, **_):
        assert access == "private" and allow_overwrite
        self.store[pathname] = bytes(body)
        self.puts.append(pathname)

    def get_blob(self, pathname, *, access):
        if pathname not in self.store:
            raise self.BlobNotFoundError(pathname)
        return types.SimpleNamespace(body=self.store[pathname])

    @contextlib.contextmanager
    def stream_blob(self, pathname, *, access):
        if pathname not in self.store:
            raise self.BlobNotFoundError(pathname)
        data = self.store[pathname]
        yield (data[i:i + 65536] for i in range(0, len(data), 65536))

    def query_blobs(self, *, prefix=None, **_):
        return [types.SimpleNamespace(pathname=k) for k in sorted(self.store) if k.startswith(prefix or "")]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = FakeBlob()
    monkeypatch.setattr(storage, "MODE", "blob")
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(storage, "_blob", lambda: f)
    return f


def test_text_roundtrip_and_missing(fake):
    assert storage.read_text("reference/observations.json") is None
    storage.write_text("reference/observations.json", json.dumps([{"id": "x"}]))
    assert json.loads(storage.read_text("reference/observations.json")) == [{"id": "x"}]
    assert "sarpulse/reference/observations.json" in fake.store


def test_local_file_downloads_once(fake, tmp_path):
    fake.store["sarpulse/processed/a.tif"] = b"x" * 200_000
    p = storage.local_file("processed/a.tif")
    assert p.read_bytes() == b"x" * 200_000
    fake.store.clear()  # second call must come from the cache
    assert storage.local_file("processed/a.tif") == p
    assert storage.local_file("processed/missing.tif") is None


def test_list_files_strips_prefix(fake):
    fake.store["sarpulse/processed/analyses/a1/result.json"] = b"{}"
    fake.store["sarpulse/processed/analyses/a1/delta_db.tif"] = b""
    assert storage.list_files("processed/analyses", "result.json") == ["processed/analyses/a1/result.json"]


def test_pipeline_end_to_end_in_blob_mode(setup, fake, monkeypatch):
    """Mirror the locally prepared synthetic dataset into the fake store, then run the API purely from Blob."""
    from fastapi.testclient import TestClient

    from backend import config
    from backend.api.main import app
    from backend.api.routes import analysis as route

    for rel in ("reference/study_areas.json",):
        fake.store[f"sarpulse/{rel}"] = (config.DATA_DIR / rel).read_bytes()
    obs = json.loads((config.DATA_DIR / "reference/observations.json").read_text())
    for o in obs:
        for layers in (o.get("processed") or {}).values():
            for rec in layers.values():
                rel = config.to_data_relative(rec["path"])
                fake.store[f"sarpulse/{rel}"] = config.resolve_data_path(rel).read_bytes()
                rec["path"] = rel
    fake.store["sarpulse/reference/observations.json"] = json.dumps(obs).encode()
    monkeypatch.setattr(route, "SYNC", True)
    c = TestClient(app)
    r = c.post("/api/analysis", json={"study_area_id": "test", "earlier_id": "e", "later_id": "l", "config": CFG})
    assert r.status_code == 200, r.json()
    aid = r.json()["id"]
    assert f"sarpulse/processed/analyses/{aid}/result.json" in fake.store
    assert fake.puts[-1].endswith("result.json")  # written last, so listed results are complete
    assert c.get(f"/api/analysis/{aid}").json()["status"] == "complete"
    assert any(a["id"] == aid for a in c.get("/api/analyses", params={"study_area": "test"}).json())


def test_exists_uses_listing_not_download(fake, monkeypatch):
    import time

    monkeypatch.setattr(time, "monotonic", lambda: 5.0)  # a freshly booted instance: clock near zero
    monkeypatch.setattr(storage, "_listing", {"at": None, "keys": set()})
    fake.store["sarpulse/processed/x.tif"] = b"abc"
    calls = []
    orig = fake.stream_blob
    fake.stream_blob = lambda *a, **k: calls.append(a) or orig(*a, **k)
    assert storage.exists("processed/x.tif") is True
    assert storage.exists("processed/missing.tif") is False
    assert calls == []
