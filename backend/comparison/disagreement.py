"""Agreement / disagreement between two aggregated change-class rasters on the same grid."""
from __future__ import annotations

import numpy as np

from backend.processing.change_detection import DECREASE, INCREASE, LIMITED, NODATA

AGREE_STABLE, AGREE_DECREASE, AGREE_INCREASE, ONLY_A, ONLY_B, OPPOSITE = 1, 2, 3, 4, 5, 6

COMPARISON_LEGEND = [
    {"value": AGREE_DECREASE, "label": "Both: decrease", "color": "#2f7fd8"},
    {"value": AGREE_INCREASE, "label": "Both: increase", "color": "#e8803a"},
    {"value": AGREE_STABLE, "label": "Both: limited change", "color": "#374151"},
    {"value": ONLY_A, "label": "Change in sensor A only", "color": "#c084fc"},
    {"value": ONLY_B, "label": "Change in sensor B only", "color": "#facc15"},
    {"value": OPPOSITE, "label": "Opposite directions", "color": "#ef4444"},
]


def compare(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, dict]:
    if a.shape != b.shape:
        raise ValueError("Aggregated class rasters must share a grid")
    out = np.zeros(a.shape, dtype="uint8")
    both = (a != NODATA) & (b != NODATA)
    ch_a = (a == DECREASE) | (a == INCREASE)
    ch_b = (b == DECREASE) | (b == INCREASE)
    out[both & (a == LIMITED) & (b == LIMITED)] = AGREE_STABLE
    out[both & (a == DECREASE) & (b == DECREASE)] = AGREE_DECREASE
    out[both & (a == INCREASE) & (b == INCREASE)] = AGREE_INCREASE
    out[both & ch_a & (b == LIMITED)] = ONLY_A
    out[both & ch_b & (a == LIMITED)] = ONLY_B
    out[both & ch_a & ch_b & (a != b)] = OPPOSITE
    n = int(both.sum())
    counts = {name: int((out == v).sum()) for name, v in
              [("agree_stable", AGREE_STABLE), ("agree_decrease", AGREE_DECREASE), ("agree_increase", AGREE_INCREASE),
               ("only_a", ONLY_A), ("only_b", ONLY_B), ("opposite", OPPOSITE)]}
    changed_any = counts["agree_decrease"] + counts["agree_increase"] + counts["only_a"] + counts["only_b"] + counts["opposite"]
    return out, {
        "compared_cells": n,
        "counts": counts,
        "overall_agreement_percent": round(100 * (counts["agree_stable"] + counts["agree_decrease"] + counts["agree_increase"]) / n, 2) if n else None,
        "change_agreement_percent": round(100 * (counts["agree_decrease"] + counts["agree_increase"]) / changed_any, 2) if changed_any else None,
    }
