"""Temporal backscatter change detection: ΔB = B_later − B_earlier (dB)."""
from __future__ import annotations

import numpy as np

# Class codes for the change-classification raster (uint8, nodata = 0)
NODATA = 0
DECREASE = 1
LIMITED = 2
INCREASE = 3

CLASS_LEGEND = [
    {"value": DECREASE, "label": "Significant decrease", "description": "Backscatter decreased by more than the threshold", "color": "#2f7fd8"},
    {"value": LIMITED, "label": "Limited change", "description": "Difference below the selected threshold", "color": "#6b7280"},
    {"value": INCREASE, "label": "Significant increase", "description": "Backscatter increased by more than the threshold", "color": "#e8803a"},
    {"value": NODATA, "label": "No data", "description": "Insufficient or unavailable observations", "color": "transparent"},
]


def difference_db(earlier_db: np.ndarray, later_db: np.ndarray) -> np.ndarray:
    d = (later_db - earlier_db).astype("float32")
    d[~(np.isfinite(earlier_db) & np.isfinite(later_db))] = np.nan
    return d


def classify(delta_db: np.ndarray, threshold_db: float, analysis_mask: np.ndarray | None = None) -> np.ndarray:
    if threshold_db <= 0:
        raise ValueError("threshold_db must be positive")
    cls = np.full(delta_db.shape, NODATA, dtype="uint8")
    valid = np.isfinite(delta_db)
    if analysis_mask is not None:
        valid &= analysis_mask
    cls[valid] = LIMITED
    cls[valid & (delta_db <= -threshold_db)] = DECREASE
    cls[valid & (delta_db >= threshold_db)] = INCREASE
    return cls
