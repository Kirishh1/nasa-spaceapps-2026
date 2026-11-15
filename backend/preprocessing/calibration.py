"""Radiometric conversions and speckle filtering. All filtering is done in linear power."""
from __future__ import annotations

import numpy as np


def linear_to_db(power: np.ndarray) -> np.ndarray:
    """10*log10(power); non-positive or non-finite values become NaN."""
    out = np.full(power.shape, np.nan, dtype="float32")
    ok = np.isfinite(power) & (power > 0)
    out[ok] = 10.0 * np.log10(power[ok])
    return out


def uniform_filter(a: np.ndarray, size: int) -> np.ndarray:
    """Moving-window mean with mirrored edges, matching scipy.ndimage.uniform_filter(mode="reflect")
    for odd window sizes. Implemented with an integral image so the deployed API needs no SciPy."""
    if size % 2 == 0:
        raise ValueError("window size must be odd")
    r = size // 2
    p = np.pad(np.asarray(a, dtype="float64"), r, mode="symmetric")
    ii = np.zeros((p.shape[0] + 1, p.shape[1] + 1))
    ii[1:, 1:] = p.cumsum(0).cumsum(1)
    s = ii[size:, size:] - ii[:-size, size:] - ii[size:, :-size] + ii[:-size, :-size]
    return s / (size * size)


def _nan_uniform(x: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(x)
    filled = np.where(valid, x, 0.0).astype("float64")
    w = uniform_filter(valid.astype("float64"), size)
    s = uniform_filter(filled, size)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = s / w
    return mean, w


def boxcar(power: np.ndarray, size: int) -> np.ndarray:
    mean, _ = _nan_uniform(power, size)
    out = mean.astype("float32")
    out[~np.isfinite(power)] = np.nan
    return out


def lee_filter(power: np.ndarray, size: int = 5, looks: float = 1.0) -> np.ndarray:
    """Classic Lee speckle filter (Lee 1980) on linear power, NaN-aware.

    `looks` is the equivalent number of looks of the input (GCOV is already multilooked, so
    noise variance is lower than single-look); Cu^2 = 1/looks.
    """
    mean, _ = _nan_uniform(power, size)
    mean_sq, _ = _nan_uniform(power.astype("float64") ** 2, size)
    var = np.maximum(mean_sq - mean**2, 0)
    cu2 = 1.0 / max(looks, 1e-6)
    with np.errstate(invalid="ignore", divide="ignore"):
        ci2 = var / (mean**2)
        w = np.clip(1.0 - cu2 / ci2, 0.0, 1.0)
    w = np.nan_to_num(w, nan=0.0)
    out = (mean + w * (power - mean)).astype("float32")
    out[~np.isfinite(power)] = np.nan
    return out


def speckle_filter(power: np.ndarray, method: str = "lee", size: int = 5, looks: float = 1.0) -> np.ndarray:
    if method == "none" or size <= 1:
        return power.astype("float32")
    if method == "boxcar":
        return boxcar(power, size)
    if method == "lee":
        return lee_filter(power, size, looks)
    raise ValueError(f"Unknown speckle filter: {method}")
