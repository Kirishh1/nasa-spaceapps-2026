from fastapi import APIRouter, HTTPException

from backend.ingestion import registry

router = APIRouter(tags=["study-areas"])


@router.get("/study-areas")
def list_study_areas() -> list[dict]:
    return registry.study_areas()


@router.get("/study-areas/{area_id}")
def get_study_area(area_id: str) -> dict:
    a = registry.get_study_area(area_id)
    if not a:
        raise HTTPException(404, f"Unknown study area {area_id}")
    return a
