"""Lookup of the OPERA reference products fetched by scripts/fetch_reference.py."""
from __future__ import annotations

import datetime as dt
import json

from backend import storage


def load(area_id: str) -> list[dict]:
    text = storage.read_text(f"reference/references_{area_id}.json")
    return json.loads(text) if text else []


def _days(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def water_refs(refs: list[dict], nisar_date: str) -> list[dict]:
    """Water references matched to a NISAR date (one per product)."""
    return [r for r in refs if r["kind"] == "water" and r["nisar_date"] == nisar_date]


def cband_pair(refs: list[dict], earlier: str, later: str) -> tuple[dict, dict] | None:
    """Same-track Sentinel-1 passes nearest to the two NISAR dates, minimising the total date offset."""
    best = None
    tracks = {r["track"] for r in refs if r["kind"] == "cband"}
    for t in tracks:
        e = [r for r in refs if r["kind"] == "cband" and r["track"] == t and earlier in r["nisar_dates"]]
        l = [r for r in refs if r["kind"] == "cband" and r["track"] == t and later in r["nisar_dates"]]
        if not e or not l:
            continue
        re_ = min(e, key=lambda r: _days(r["date"], earlier))
        rl = min(l, key=lambda r: _days(r["date"], later))
        if re_["date"] >= rl["date"]:
            continue
        cost = _days(re_["date"], earlier) + _days(rl["date"], later)
        if best is None or cost < best[0]:
            best = (cost, re_, rl)
    return (best[1], best[2]) if best else None


def change_pairs(refs: list[dict], earlier: str, later: str, max_total_offset: int = 12) -> list[tuple[dict, dict]]:
    """Same-orbit DSWx-S1 pairs bracketing the two NISAR dates (one per orbit, smallest total offset)."""
    cands = [r for r in refs if r["kind"] == "water_change_candidate"]
    out = []
    for t in {r["track"] for r in cands}:
        e = [r for r in cands if r["track"] == t and r["nisar_date"] == earlier]
        l = [r for r in cands if r["track"] == t and r["nisar_date"] == later]
        if not e or not l:
            continue
        re_ = min(e, key=lambda r: r["offset_days"])
        rl = min(l, key=lambda r: r["offset_days"])
        if re_["date"] < rl["date"] and re_["offset_days"] + rl["offset_days"] <= max_total_offset:
            out.append((re_, rl))
    return sorted(out, key=lambda p: p[0]["offset_days"] + p[1]["offset_days"])
