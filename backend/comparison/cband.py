"""Independent C-band (Sentinel-1, OPERA RTC-S1) change map and its comparison with NISAR L-band.

The C-band change map is derived exactly like the NISAR one (Lee filter in linear power, dB, ΔB,
±threshold classes) from its own two acquisitions; raw backscatter is never differenced across sensors.
Both class maps are then aggregated to a common coarser grid and compared cell by cell, overall and
per ESA WorldCover land-cover class, which is where wavelength-dependent behaviour shows up.
"""
from __future__ import annotations

import numpy as np
import rasterio

from backend.comparison import disagreement as dis
from backend.comparison.sensor_comparison import aggregate_classes
from backend.preprocessing.calibration import linear_to_db, speckle_filter
from backend.processing import change_detection as cd

LANDCOVER_NAMES = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up", 60: "Bare/sparse",
                   80: "Permanent water", 90: "Herbaceous wetland", 95: "Mangroves"}
RTC_S1_LOOKS = 4.0  # approximate equivalent number of looks of OPERA RTC-S1 30 m backscatter


def cband_change(vv_earlier: str, vv_later: str, mask: np.ndarray, threshold_db: float, filt: str, size: int):
    with rasterio.open(vv_earlier) as a, rasterio.open(vv_later) as b:
        e, l = a.read(1).astype("float32"), b.read(1).astype("float32")
    for x in (e, l):
        x[~np.isfinite(x) | (x <= 0)] = np.nan
    edb = linear_to_db(speckle_filter(e, filt, size, RTC_S1_LOOKS))
    ldb = linear_to_db(speckle_filter(l, filt, size, RTC_S1_LOOKS))
    delta = cd.difference_db(edb, ldb)
    return delta, cd.classify(delta, threshold_db, mask)


def _block_majority(lc: np.ndarray, factor: int, classes=tuple(LANDCOVER_NAMES)) -> np.ndarray:
    h, w = (lc.shape[0] // factor) * factor, (lc.shape[1] // factor) * factor
    b = lc[:h, :w].reshape(h // factor, factor, w // factor, factor)
    counts = np.stack([(b == c).sum(axis=(1, 3)) for c in classes])
    out = np.array(classes, dtype="uint8")[counts.argmax(0)]
    out[counts.max(0) == 0] = 0
    return out


def compare(nisar_cls: np.ndarray, cband_cls: np.ndarray, landcover: np.ndarray | None, factor: int, transform) -> dict:
    a = aggregate_classes(nisar_cls, factor)
    b = aggregate_classes(cband_cls, factor)
    agreement, stats = dis.compare(a, b)
    by_lc = []
    if landcover is not None:
        lc = _block_majority(landcover, factor)
        for code, name in LANDCOVER_NAMES.items():
            m = (lc == code) & (agreement > 0)
            n = int(m.sum())
            if n < 25:
                continue
            cnt = {k: int(((agreement == v) & m).sum()) for k, v in
                   [("agree", None), ("only_l", dis.ONLY_A), ("only_c", dis.ONLY_B), ("opposite", dis.OPPOSITE)] if v}
            agree = int(np.isin(agreement[m], [dis.AGREE_STABLE, dis.AGREE_DECREASE, dis.AGREE_INCREASE]).sum())
            by_lc.append({"class": code, "name": name, "cells": n,
                          "agree_percent": round(100 * agree / n, 1),
                          "l_band_only_percent": round(100 * cnt["only_l"] / n, 1),
                          "c_band_only_percent": round(100 * cnt["only_c"] / n, 1),
                          "opposite_percent": round(100 * cnt["opposite"] / n, 1)})
    agg_transform = transform * transform.scale(factor, factor)
    return {"agreement": agreement, "transform": agg_transform, "stats": stats, "by_landcover": by_lc,
            "cell_size_m": abs(transform.a) * factor}
