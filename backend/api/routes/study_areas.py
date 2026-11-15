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


@router.get("/study-areas/{area_id}/rainfall")
def rainfall(area_id: str) -> dict:
    """Season-long daily basin-mean rainfall from NASA GPM IMERG (scripts/fetch_rainfall.py), if computed."""
    import json

    from backend import storage

    text = storage.read_text(f"reference/rainfall_{area_id}.json")
    if not text:
        return {"status": "unavailable", "series": []}
    return {"status": "available", "source": "NASA GPM IMERG Late Run daily V07", **json.loads(text)}
