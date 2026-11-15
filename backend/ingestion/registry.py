"""Local registry of study areas and observations (JSON files in data/reference)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend import config


def json_safe(o: Any) -> Any:
    """Replace NaN/inf (e.g. HDF5 _FillValue=NaN) with None so results are strict JSON."""
    import math

    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    return o


STUDY_AREAS_REL = "reference/study_areas.json"
OBSERVATIONS_REL = "reference/observations.json"


def _load(rel: str) -> list[dict]:
    from backend import storage

    text = storage.read_text(rel)
    return json_safe(json.loads(text)) if text else []


def _save(rel: str, items: list[dict]) -> None:
    from backend import storage

    storage.write_text(rel, json.dumps(json_safe(items), indent=2, default=str))


def study_areas() -> list[dict]:
    return _load(STUDY_AREAS_REL)


def get_study_area(area_id: str) -> dict | None:
    return next((a for a in study_areas() if a["id"] == area_id), None)


def upsert_study_area(area: dict) -> None:
    items = [a for a in study_areas() if a["id"] != area["id"]] + [area]
    _save(STUDY_AREAS_REL, items)


def observations() -> list[dict]:
    return _load(OBSERVATIONS_REL)


def get_observation(obs_id: str) -> dict | None:
    return next((o for o in observations() if o["id"] == obs_id), None)


def upsert_observation(obs: dict) -> None:
    items = observations()
    for i, o in enumerate(items):
        if o["id"] == obs["id"]:
            merged = {**o, **obs}
            items[i] = merged
            break
    else:
        items.append(obs)
    items.sort(key=lambda o: o.get("start_time", ""))
    _save(OBSERVATIONS_REL, items)


def processed_layer(obs: dict, study_area_id: str, frequency: str, term: str) -> dict[str, Any] | None:
    """Return the processed COG record for (study area, frequency, term) if it exists on disk."""
    rec = (obs.get("processed") or {}).get(study_area_id, {}).get(f"{frequency}_{term}")
    if rec:
        from backend import storage

        path = storage.local_file(rec["path"]) if not Path(rec["path"]).is_absolute() else config.resolve_data_path(rec["path"])
        if path is not None and path.exists():
            return {**rec, "path": str(path)}
    return None
