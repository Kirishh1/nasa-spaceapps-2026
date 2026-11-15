"""Potential inundation-related change.

Rules (all must hold), applied to the co-polarized (HH or VV) channel:
  * open-water candidates: significant backscatter decrease AND later backscatter below an
    open-water threshold (smooth water is a specular reflector → low return), in a spatially
    connected region of at least `min_area_m2`.
  * vegetated-flooding candidates: significant backscatter *increase* inside mapped vegetation
    (trees / wetland / mangrove), consistent with — but not proof of — double-bounce
    scattering between standing water and stems. Only computed when a land-cover reference is supplied.

Outputs are *potential* indicators, not confirmed flood maps.
"""
from __future__ import annotations

import numpy as np
from rasterio.features import sieve

from backend.processing.change_detection import DECREASE, INCREASE

NONE = 1
OPEN_WATER = 2
VEGETATED = 3

INUNDATION_LEGEND = [
    {"value": OPEN_WATER, "label": "Potential open-water emergence", "description": "Decrease to low (water-like) backscatter in a connected area", "color": "#22d3ee"},
    {"value": VEGETATED, "label": "Potential flooded vegetation", "description": "Increase within mapped vegetation; consistent with double-bounce", "color": "#a3e635"},
    {"value": NONE, "label": "Not flagged", "description": "No inundation-consistent signal", "color": "transparent"},
]

# ESA WorldCover classes where double-bounce from flooded vegetation is plausible
VEGETATION_CLASSES = (10, 90, 95)  # tree cover, herbaceous wetland, mangroves


def remove_small(mask: np.ndarray, min_pixels: int) -> np.ndarray:
    """Drop 8-connected True regions smaller than ``min_pixels`` (GDAL sieve, bundled with rasterio).

    Sieving also fills small False holes; AND-ing with the input keeps the result a subset of ``mask``.
    """
    if min_pixels <= 1 or not mask.any():
        return mask
    kept = sieve(mask.astype("uint8"), size=int(min_pixels), connectivity=8).astype(bool)
    return kept & mask


def potential_inundation(
    change_class: np.ndarray,
    later_db: np.ndarray,
    water_threshold_db: float,
    min_pixels: int,
    landcover: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    out = np.zeros(change_class.shape, dtype="uint8")
    valid = change_class > 0
    out[valid] = NONE
    open_water = (change_class == DECREASE) & np.isfinite(later_db) & (later_db < water_threshold_db)
    open_water = remove_small(open_water, min_pixels)
    out[open_water] = OPEN_WATER
    info = {"vegetated_flooding_evaluated": landcover is not None}
    if landcover is not None:
        veg = np.isin(landcover, VEGETATION_CLASSES)
        vf = remove_small((change_class == INCREASE) & veg, min_pixels)
        out[vf & ~open_water] = VEGETATED
    else:
        info["vegetated_flooding_reason"] = "No land-cover reference available; flooded-vegetation candidates not evaluated."
    return out, info
