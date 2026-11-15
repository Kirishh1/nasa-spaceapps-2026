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


def _stored_json(rel: str) -> dict | None:
    import json

    from backend import storage

    text = storage.read_text(rel)
    return json.loads(text) if text else None


@router.get("/study-areas/{area_id}/nisar-season")
def nisar_season(area_id: str) -> dict:
    """Open-water fraction for every processed NISAR frame, with per-date reference agreement."""
    d = _stored_json(f"reference/nisar_season_{area_id}.json")
    return {"status": "available", **d} if d else {"status": "unavailable", "series": []}


@router.get("/study-areas/{area_id}/swot")
def swot_levels(area_id: str) -> dict:
    """SWOT median lake-level change per pass through the season (per-lake observations and outlines omitted)."""
    d = _stored_json(f"reference/swot_{area_id}.json")
    if not d:
        return {"status": "unavailable", "passes": []}
    passes = [{"pass": p["pass"], "stable_lakes": p["stable_lakes"],
               "series": [{k: s[k] for k in ("date", "lakes", "median_wse_change_m")} for s in p["series"]]} for p in d["passes"]]
    return {"status": "available", "product": d["product"], "passes": passes}


@router.get("/study-areas/{area_id}/soil-moisture")
def soil_moisture(area_id: str) -> dict:
    d = _stored_json(f"reference/soil_moisture_{area_id}.json")
    return {"status": "available", **d} if d else {"status": "unavailable", "series": []}


@router.get("/study-areas/{area_id}/display-layers")
def display_layers(area_id: str) -> dict:
    """Reference imagery for display (e.g. NASA HLS true colour), served as XYZ tiles."""
    from backend.ingestion import references

    out = []
    for r in references.load(area_id):
        if r["kind"] == "hls_rgb":
            name = r["path"].rsplit("/", 1)[-1].removesuffix(".tif")
            out.append({"id": name, "kind": "rgb", "date": r["date"], "title": f"True colour, NASA HLS {r['date']}",
                        "tiles": f"/api/ref-tiles/{area_id}/{name}/{{z}}/{{x}}/{{y}}.png"})
    return {"layers": out}
