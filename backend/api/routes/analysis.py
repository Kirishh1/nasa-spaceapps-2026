import os
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.api import jobs
from backend.api.layers import LAYERS
from backend.api.schemas.models import AnalysisRequest
from backend.processing import pipeline

router = APIRouter(tags=["analysis"])


def _reject(e: pipeline.AnalysisError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(e), "errors": e.errors, "warnings": e.warnings})


def _preflight(req: AnalysisRequest):
    if req.sensor != "NISAR":
        raise pipeline.AnalysisError(
            "RCM data unavailable",
            [{"code": "rcm_unavailable", "message": "No compatible RCM observations are ingested for this study area; only NISAR analysis can run."}],
        )
    cfg = pipeline.resolve_config(req.config.model_dump())
    pre = pipeline.preflight(req.study_area_id, req.earlier_id, req.later_id, cfg)
    pipeline.subarea(pre[0], req.geometry)
    return cfg, pre


@router.get("/analyses")
def list_analyses(study_area: str | None = None):
    """Previously computed analyses (newest first), so a stored result can be reopened without recomputing."""
    return pipeline.list_results(study_area)


@router.post("/analysis/check")
def check_analysis(req: AnalysisRequest):
    """Validate a request without running it."""
    try:
        _, (*_, compat, _le, _ll) = _preflight(req)
    except pipeline.AnalysisError as e:
        return {"ok": False, "errors": e.errors, "warnings": e.warnings}
    return {"ok": True, "errors": [], "warnings": compat.warnings}


# On serverless platforms work may be frozen once a response is sent, and in-memory job state is
# not shared between instances, so analyses run inside the request there (about 20 s).
SYNC = bool(os.environ.get("VERCEL")) or os.environ.get("SARPULSE_SYNC_ANALYSIS") == "1"


@router.post("/analysis", status_code=202)
def start_analysis(req: AnalysisRequest):
    try:
        cfg, _ = _preflight(req)
    except pipeline.AnalysisError as e:
        return _reject(e)
    if SYNC:
        aid = uuid.uuid4().hex[:12]
        try:
            pipeline.run_analysis(req.study_area_id, req.earlier_id, req.later_id, cfg, analysis_id=aid, geometry=req.geometry)
        except pipeline.AnalysisError as e:
            return _reject(e)
        return JSONResponse(status_code=200, content={"id": aid, "status": "complete"})
    aid = jobs.submit(req.study_area_id, req.earlier_id, req.later_id, cfg, req.geometry)
    return {"id": aid, "status": "running"}


def _result_or_404(aid: str) -> dict:
    r = pipeline.load_result(aid)
    if r is None:
        st = jobs.status(aid)
        if st is None:
            raise HTTPException(404, f"Unknown analysis {aid}")
        raise HTTPException(409, detail=st)
    return r


@router.get("/analysis/{aid}")
def get_analysis(aid: str):
    r = pipeline.load_result(aid)
    if r is not None:
        return r
    st = jobs.status(aid)
    if st is None:
        raise HTTPException(404, f"Unknown analysis {aid}")
    return st


@router.get("/analysis/{aid}/statistics")
def get_statistics(aid: str):
    r = _result_or_404(aid)
    return {"id": aid, "statistics": r["statistics"], "validation": r["validation"], "inundation": r["inundation"]}


@router.get("/analysis/{aid}/layers")
def get_layers(aid: str):
    r = _result_or_404(aid)
    out = []
    for name in r["layers"]:
        spec = LAYERS[name]
        out.append({
            "id": name,
            "tiles": f"/api/tiles/{aid}/{name}/{{z}}/{{x}}/{{y}}.png",
            "bounds": r["grid"]["bounds_lonlat"],
            **{k: v for k, v in spec.items() if k != "colormap"},
            "colormap": spec.get("colormap"),
        })
    return {"id": aid, "layers": out, "study_area": r["study_area"]}
