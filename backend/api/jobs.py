"""Minimal in-process job runner for analyses (results persisted to disk)."""
from __future__ import annotations

import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from backend.processing import pipeline

log = logging.getLogger("sarpulse.jobs")
_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def submit(study_area_id: str, earlier_id: str, later_id: str, cfg: dict, geometry: dict | None = None) -> str:
    aid = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[aid] = {"id": aid, "status": "running", "stage": "Queued"}

    def run():
        try:
            def progress(msg: str) -> None:
                with _lock:
                    _jobs[aid] = {"id": aid, "status": "running", "stage": msg}

            pipeline.run_analysis(study_area_id, earlier_id, later_id, cfg, analysis_id=aid, geometry=geometry, progress=progress)
            with _lock:
                _jobs[aid] = {"id": aid, "status": "complete"}
        except pipeline.AnalysisError as e:
            with _lock:
                _jobs[aid] = {"id": aid, "status": "failed", "errors": e.errors, "warnings": e.warnings}
        except Exception as e:  # noqa: BLE001
            log.error("analysis %s crashed: %s", aid, traceback.format_exc())
            with _lock:
                _jobs[aid] = {"id": aid, "status": "failed", "errors": [{"code": "internal_error", "message": str(e)}]}

    _executor.submit(run)
    return aid


def status(aid: str) -> dict | None:
    with _lock:
        return dict(_jobs[aid]) if aid in _jobs else None
