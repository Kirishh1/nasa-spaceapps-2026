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


@router.get("/study-areas/{area_id}/timeline")
def water_timeline(area_id: str) -> dict:
    """Seasonal surface-water fraction from NASA OPERA DSWx (scripts/opera_timeline.py), if computed."""
    import json

    from backend import storage

    text = storage.read_text(f"reference/water_timeline_{area_id}.json")
    if not text:
        return {"status": "unavailable", "series": []}
    return {"status": "available", **json.loads(text)}
