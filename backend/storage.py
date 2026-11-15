"""Storage backends for SAR-Pulse data.

All data is addressed by a path relative to the data root, e.g.
``reference/observations.json`` or ``processed/analyses/<id>/delta_db.tif``.

* ``local`` (default): files live under ``config.DATA_DIR``. New analyses go to ``config.ANALYSES_DIR``.
* ``blob`` (``SARPULSE_STORAGE=blob``): files live in a Vercel Blob store under ``SARPULSE_BLOB_PREFIX``.
  Rasters are downloaded once per instance into a local cache, because GDAL/rio-tiler need
  file-like random access. Credentials come from the Vercel project (OIDC + ``BLOB_STORE_ID``) or
  ``BLOB_READ_WRITE_TOKEN``, and are read by the official ``vercel-blob`` SDK, never by this code.
"""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

from backend import config

MODE = os.environ.get("SARPULSE_STORAGE", "local").lower()
PREFIX = os.environ.get("SARPULSE_BLOB_PREFIX", "sarpulse").strip("/")
ACCESS = os.environ.get("SARPULSE_BLOB_ACCESS", "private")  # must match how the store was created
CACHE_DIR = Path(os.environ.get("SARPULSE_CACHE_DIR", "/tmp/sarpulse-cache" if os.environ.get("VERCEL") else config.DATA_DIR / ".blobcache"))

_lock = threading.Lock()


def is_blob() -> bool:
    return MODE == "blob"


def _blob():
    from vercel.blob import sync as blob  # imported lazily so local mode never needs the SDK

    return blob


def _key(rel: str) -> str:
    return f"{PREFIX}/{rel.lstrip('/')}"


def _local_path(rel: str) -> Path:
    """Where a relative path lives in local mode (new analyses may be in ANALYSES_DIR)."""
    parts = Path(rel).parts
    if len(parts) >= 3 and parts[0] == "processed" and parts[1] == "analyses":
        return config.analysis_dir(parts[2]).joinpath(*parts[3:])
    return config.resolve_data_path(rel)


# ---------------------------------------------------------------- reads

def read_text(rel: str) -> str | None:
    if not is_blob():
        p = _local_path(rel)
        return p.read_text() if p.exists() else None
    blob = _blob()
    try:
        return blob.get_blob(_key(rel), access=ACCESS).body.decode()
    except blob.BlobNotFoundError:
        return None


def local_file(rel: str) -> Path | None:
    """A local filesystem path for ``rel``, downloading it from Blob into the cache if needed."""
    if not is_blob():
        p = _local_path(rel)
        return p if p.exists() else None
    target = CACHE_DIR / rel
    if target.exists():
        return target
    blob = _blob()
    with _lock:
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            with blob.stream_blob(_key(rel), access=ACCESS) as dl, open(tmp, "wb") as fh:
                for chunk in dl:
                    fh.write(chunk)
        except blob.BlobNotFoundError:
            tmp.unlink(missing_ok=True)
            return None
        tmp.replace(target)
    return target


def list_files(prefix: str, suffix: str = "") -> list[str]:
    """Relative paths under ``prefix`` (recursive) ending with ``suffix``."""
    if not is_blob():
        out: set[str] = set()
        roots = [config.DATA_DIR / prefix]
        if prefix.strip("/") == "processed/analyses":
            roots += [config.ANALYSES_DIR, config.STORED_ANALYSES_DIR]
        for root in roots:
            if root.exists():
                for p in root.rglob(f"*{suffix}"):
                    if p.is_file():
                        out.add(f"{prefix.strip('/')}/{p.relative_to(root)}")
        return sorted(out)
    blob = _blob()
    start = len(PREFIX) + 1
    return sorted(item.pathname[start:] for item in blob.query_blobs(prefix=_key(prefix)) if item.pathname.endswith(suffix))


_listing: dict = {"at": None, "keys": set()}  # "at" is None until the first listing (monotonic clocks can start near 0)


def exists(rel: str, max_age_s: float = 300) -> bool:
    """Whether ``rel`` is stored, without downloading it (Blob mode uses one cached listing per instance)."""
    if not is_blob():
        return _local_path(rel).exists()
    if (CACHE_DIR / rel).exists():
        return True
    import time

    if _listing["at"] is None or time.monotonic() - _listing["at"] > max_age_s:
        start = len(PREFIX) + 1
        _listing["keys"] = {item.pathname[start:] for item in _blob().query_blobs(prefix=f"{PREFIX}/")}
        _listing["at"] = time.monotonic()
    return rel in _listing["keys"]


# ---------------------------------------------------------------- writes

def write_text(rel: str, text: str) -> None:
    if not is_blob():
        p = config.DATA_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return
    _blob().put_blob(_key(rel), text.encode(), access=ACCESS, content_type="application/json", allow_overwrite=True)


def upload_file(rel: str, src: Path) -> None:
    """Store a local file at ``rel`` (no-op in local mode when it is already there)."""
    if not is_blob():
        dst = _local_path(rel)
        if dst.resolve() != src.resolve():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        return
    ctype = {".tif": "image/tiff", ".json": "application/json"}.get(src.suffix, "application/octet-stream")
    _blob().put_blob(_key(rel), src.read_bytes(), access=ACCESS, content_type=ctype, allow_overwrite=True)
    cached = CACHE_DIR / rel
    if cached.resolve() != src.resolve():
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, cached)
