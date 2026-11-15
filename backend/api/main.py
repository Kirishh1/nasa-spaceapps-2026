"""SAR-Pulse FastAPI application.

Run from the repository root:  .venv/bin/uvicorn backend.api.main:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import analysis, observations, study_areas, tiles

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="SAR-Pulse API",
    version="0.1.0",
    description="Temporal NISAR backscatter change detection with transparent metadata and uncertainty.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(study_areas.router, prefix="/api")
app.include_router(observations.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(tiles.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    from backend import config
    from backend.ingestion import registry

    return {
        "status": "ok",
        "data_dir": str(config.DATA_DIR),
        "study_areas": len(registry.study_areas()),
        "observations": len(registry.observations()),
    }
