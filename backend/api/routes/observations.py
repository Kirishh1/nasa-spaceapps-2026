from fastapi import APIRouter, HTTPException, Query
from shapely.geometry import shape

from backend.ingestion import rcm, registry

router = APIRouter(tags=["observations"])


def _summary(o: dict, area_id: str | None) -> dict:
    processed = (o.get("processed") or {}).get(area_id, {}) if area_id else {}
    ingested = {k: True for k, rec in processed.items() if registry.processed_layer(o, area_id, *k.split("_", 1))}
    out = {k: o.get(k) for k in ("id", "sensor", "band", "product_type", "product_version", "date", "start_time", "end_time",
                                 "track", "frame", "stack_id", "pass_direction", "polarizations", "footprint", "size_bytes",
                                 "browse_url", "qa_report_url", "range_bandwidth_mhz")}
    out["ingested_layers"] = sorted(ingested)
    out["available_for_analysis"] = bool(ingested)
    if not ingested:
        out["unavailable_reason"] = "Listed in NASA CMR but not yet downloaded/processed for this study area."
    return out


@router.get("/observations")
def list_observations(study_area: str | None = Query(None), sensor: str = Query("NISAR")) -> dict:
    sensor = sensor.upper()
    if sensor == "RCM":
        return {"sensor": "RCM", **rcm.discover_local_rcm(study_area or "")}
    obs = [o for o in registry.observations() if o.get("sensor") == sensor]
    area = registry.get_study_area(study_area) if study_area else None
    if study_area and not area:
        raise HTTPException(404, f"Unknown study area {study_area}")
    if area:
        g = shape(area["geometry"])
        obs = [o for o in obs if o.get("footprint") and shape(o["footprint"]).intersects(g)]
    return {"sensor": sensor, "status": "available" if obs else "unavailable", "observations": [_summary(o, study_area) for o in obs]}


@router.get("/observations/{obs_id}")
def get_observation(obs_id: str) -> dict:
    o = registry.get_observation(obs_id)
    if not o:
        raise HTTPException(404, f"Unknown observation {obs_id}")
    return o
