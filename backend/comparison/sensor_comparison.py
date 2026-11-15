"""Compare independently derived change maps from two sensors (e.g. NISAR L-band vs RCM C-band).

Raw backscatter values are never subtracted across sensors. Each sensor's change-class raster is
aggregated to a common coarser grid: each cell takes the dominant class among valid pixels (if valid
coverage ≥ min_valid_fraction), and the cells are then compared.
"""
from __future__ import annotations

import numpy as np

from backend.processing.change_detection import DECREASE, INCREASE, LIMITED, NODATA


def aggregate_classes(cls: np.ndarray, factor: int, min_valid_fraction: float = 0.5, min_change_fraction: float = 0.3) -> np.ndarray:
    """Aggregate a class raster by an integer factor. A cell is 'decrease'/'increase' when that class covers
    ≥ min_change_fraction of its valid pixels, otherwise 'limited'; NODATA when valid coverage is too low."""
    h, w = (cls.shape[0] // factor) * factor, (cls.shape[1] // factor) * factor
    c = cls[:h, :w].reshape(h // factor, factor, w // factor, factor)
    n = factor * factor
    valid = (c != NODATA).sum(axis=(1, 3))
    dec = (c == DECREASE).sum(axis=(1, 3))
    inc = (c == INCREASE).sum(axis=(1, 3))
    out = np.full(valid.shape, NODATA, dtype="uint8")
    ok = valid >= min_valid_fraction * n
    with np.errstate(invalid="ignore", divide="ignore"):
        fd = np.where(valid > 0, dec / valid, 0)
        fi = np.where(valid > 0, inc / valid, 0)
    out[ok] = LIMITED
    out[ok & (fd >= min_change_fraction) & (fd >= fi)] = DECREASE
    out[ok & (fi >= min_change_fraction) & (fi > fd)] = INCREASE
    return out
