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


@router.get("/summary")
def summary() -> list[dict]:
    """Headline numbers of each study area's featured (or newest) analysis, for the overview table."""
    from backend.ingestion import registry
    from backend.processing import pipeline

    out = []
    results = pipeline.list_results()
    for area in registry.study_areas():
        fp = area.get("featured_pair")
        mine = [r for r in results if r["study_area_id"] == area["id"] and not r["subset"]]
        pick = next((r for r in mine if fp and r["earlier_date"] == fp[0] and r["later_date"] == fp[1]), mine[0] if mine else None)
        if not pick:
            continue
        r = pipeline.load_result(pick["id"]) or {}
        w = r.get("water") or {}
        acc = (r.get("validation") or {}).get("accuracy") or []
        opt = [a["open_water"]["f1"] for a in acc if a["product"] == "DSWX_HLS" and a["open_water"]["f1"] is not None]
        anyf = [a["open_water"]["f1"] for a in acc if a["open_water"]["f1"] is not None]
        sw = ((r.get("validation") or {}).get("swot") or {}).get("passes") or []
        out.append({"area_id": area["id"], "name": area["name"], "category": area.get("category"), "analysis_id": pick["id"],
                    "earlier_date": pick["earlier_date"], "later_date": pick["later_date"],
                    "water_earlier_km2": w.get("earlier_km2"), "water_later_km2": w.get("later_km2"),
                    "lost_km2": w.get("lost_km2"), "gained_km2": w.get("gained_km2"),
                    "best_f1": max(opt) if opt else (max(anyf) if anyf else None), "f1_reference": "optical" if opt else ("C-band" if anyf else None),
                    "swot_median_change_m": sw[0]["median_change_m"] if sw else None,
                    "lc_agreement_percent": ((r.get("sensor_comparison") or {}).get("stats") or {}).get("overall_agreement_percent")})
    return out
