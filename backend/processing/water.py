"""Open-water mapping from NISAR backscatter and water-change classes between two dates.

Smooth open water is a specular reflector, so it returns little energy to the radar: in L-band HH it is
typically well below the surrounding land. The water/land threshold is chosen per image with Otsu's method
on the speckle-filtered dB histogram, constrained to a physically plausible window, unless a fixed value
is configured. Flooded vegetation can be *brighter* than land (double bounce) and is not open water here.
"""
from __future__ import annotations

import numpy as np

from backend.processing.inundation import remove_small

NODATA, LAND, WATER = 0, 1, 2
STABLE_LAND, PERSISTENT_WATER, WATER_GAINED, WATER_LOST = 1, 2, 3, 4

WATER_CHANGE_LEGEND = [
    {"value": WATER_GAINED, "label": "Water gained", "description": "Land on the earlier date, open water on the later date", "color": "#22d3ee"},
    {"value": WATER_LOST, "label": "Water receded", "description": "Open water on the earlier date, land on the later date", "color": "#d97706"},
    {"value": PERSISTENT_WATER, "label": "Water on both dates", "description": "Open water on both dates", "color": "#1d4ed8"},
    {"value": STABLE_LAND, "label": "Land on both dates", "description": "No open water on either date", "color": "transparent"},
]

# Physically plausible window for the L-band HH open-water threshold. It only rules out absurd values;
# within it, Otsu chooses. (A tighter -14 dB cap clipped the Sylhet scenes, whose optimum is ~-12 dB.)
OTSU_BOUNDS_DB = (-24.0, -10.0)


# Otsu's effectiveness measure η = σ_B²/σ_T². A single Gaussian gives 2/π ≈ 0.64 whatever its shape, so a
# threshold is only trusted when η clearly exceeds that (real Sylhet scenes: 0.74-0.80).
MIN_SEPARABILITY = 0.7


def otsu_threshold(db: np.ndarray, bounds: tuple[float, float] = OTSU_BOUNDS_DB, bins: int = 256) -> float | None:
    """Otsu threshold of finite dB values, searched only inside ``bounds``. None if too few samples."""
    r = otsu(db, bounds, bins)
    return r[0] if r else None


def otsu(db: np.ndarray, bounds: tuple[float, float] = OTSU_BOUNDS_DB, bins: int = 256) -> tuple[float, float] | None:
    """(threshold, separability η = between-class / total variance). None if too few samples."""
    v = db[np.isfinite(db)]
    if v.size < 1000:
        return None
    lo, hi = np.percentile(v, [0.5, 99.5])
    hist, edges = np.histogram(v, bins=bins, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m = np.cumsum(hist * centers)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu0 = m / w0
        mu1 = (m[-1] - m) / w1
        between = w0 * w1 * (mu0 - mu1) ** 2
    ok = (centers >= bounds[0]) & (centers <= bounds[1]) & np.isfinite(between)
    if not ok.any():
        return None
    c, b = centers[ok], between[ok]
    # an empty gap between the modes gives a plateau of equal scores: take the middle of it
    top = c[b >= b.max() * (1 - 1e-6)]
    total_var = float(hist @ (centers - m[-1] / w0[-1]) ** 2)
    eta = float(b.max() / (w0[-1] * total_var)) if total_var > 0 else 0.0  # σ_B² / σ_T²
    return float((top.min() + top.max()) / 2), round(eta, 3)


def water_map(db: np.ndarray, threshold_db: float, valid: np.ndarray, min_pixels: int = 1) -> np.ndarray:
    out = np.zeros(db.shape, dtype="uint8")
    ok = valid & np.isfinite(db)
    out[ok] = LAND
    water = ok & (db < threshold_db)
    water = remove_small(water, min_pixels)
    out[water] = WATER
    return out


def water_change(earlier: np.ndarray, later: np.ndarray) -> np.ndarray:
    out = np.zeros(earlier.shape, dtype="uint8")
    ok = (earlier > 0) & (later > 0)
    ew, lw = earlier == WATER, later == WATER
    out[ok & ~ew & ~lw] = STABLE_LAND
    out[ok & ew & lw] = PERSISTENT_WATER
    out[ok & ~ew & lw] = WATER_GAINED
    out[ok & ew & ~lw] = WATER_LOST
    return out
