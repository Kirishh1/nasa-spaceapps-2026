"""Uncertainty report and reference-data consistency checks."""
from __future__ import annotations

import numpy as np

from backend.processing import inundation as inu
from backend.validation.reference_data import SOURCES

FALSE_POSITIVE_SOURCES = [
    "Wind roughening of open water can raise backscatter and hide or mimic change.",
    "Changes in soil moisture alter the dielectric constant and backscatter without inundation.",
    "Crop harvest, ploughing, or vegetation phenology change backscatter between dates.",
    "Smooth surfaces such as roads, tarmac, dry sand, or radar shadow also give low returns and can look like water.",
    "Residual speckle produces isolated false detections, especially with small filter windows.",
    "Differences in acquisition geometry (incidence angle) affect backscatter even within the same track.",
    "Flooded vegetation may increase backscatter (double bounce), so decrease-only rules under-detect it.",
    "L-band penetrates vegetation canopies more deeply than C-band, so the same event can look different at the two wavelengths.",
]


def reference_consistency(inundation: np.ndarray, change_class: np.ndarray, occurrence: np.ndarray | None, landcover: np.ndarray | None) -> dict:
    out: dict = {"independently_validated": False,
                 "statement": "These results have not been independently validated against event-specific ground truth (e.g. field surveys or concurrent optical flood maps)."}
    valid = change_class > 0
    if occurrence is not None:
        occ_ok = valid & (occurrence != 255)
        ow = (inundation == inu.OPEN_WATER) & occ_ok
        n_ow = int(ow.sum())
        base = occ_ok.sum()
        hist_water_all = float(((occurrence > 0) & occ_ok).sum() / base) if base else None
        out["jrc_surface_water"] = {
            "source": SOURCES["jrc_gsw"],
            "open_water_candidates_evaluated": n_ow,
            "fraction_candidates_in_historically_wet_pixels": round(float(((occurrence > 0) & ow).sum() / n_ow), 4) if n_ow else None,
            "fraction_candidates_in_permanent_water": round(float(((occurrence >= 90) & ow).sum() / n_ow), 4) if n_ow else None,
            "baseline_fraction_historically_wet": round(hist_water_all, 4) if hist_water_all is not None else None,
            "interpretation": (
                "If candidates fall in historically wet pixels much more often than the baseline, they are spatially "
                "consistent with known floodplains/wetlands. Candidates in permanent water (≥90% occurrence) more likely "
                "reflect wind or water-surface changes than new inundation. This is a consistency check, not validation."
            ),
        }
        if hist_water_all is not None and hist_water_all > 0.5:
            out["jrc_surface_water"]["caveat"] = (
                f"{hist_water_all:.0%} of all valid pixels have been water at some point since 1984, so this check "
                "discriminates weakly in this floodplain: candidates landing in historically wet pixels is expected."
            )
    else:
        out["jrc_surface_water"] = {"status": "unavailable", "reason": "JRC Global Surface Water tiles could not be read."}
    if landcover is not None:
        lc_ok = valid & (landcover > 0)
        classes, counts = np.unique(landcover[lc_ok], return_counts=True)
        names = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up", 60: "Bare/sparse vegetation",
                 70: "Snow and ice", 80: "Permanent water", 90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}
        dec = (change_class == 1) & lc_ok
        inc = (change_class == 3) & lc_ok
        rows = []
        for c, n in zip(classes, counts):
            m = landcover == c
            rows.append({"class": int(c), "name": names.get(int(c), str(c)), "pixels": int(n),
                         "percent_decrease": round(100 * float((dec & m).sum()) / n, 2),
                         "percent_increase": round(100 * float((inc & m).sum()) / n, 2)})
        out["landcover_breakdown"] = {"source": SOURCES["worldcover"], "rows": sorted(rows, key=lambda r: -r["pixels"])}
    else:
        out["landcover_breakdown"] = {"status": "unavailable", "reason": "ESA WorldCover tiles could not be read."}
    return out


def uncertainty_report(earlier: dict, later: dict, config: dict, compat: dict, alignment_notes: list[str], stats: dict, pixel_spacing: list[float]) -> dict:
    return {
        "observations": [
            {k: o.get(k) for k in ("id", "sensor", "band", "product_type", "product_version", "start_time", "track", "frame", "pass_direction")}
            for o in (earlier, later)
        ],
        "polarization": config["polarization"],
        "frequency": config["frequency"],
        "pixel_spacing_m": pixel_spacing,
        "method": {
            "quantity": "GCOV diagonal covariance term (RTC gamma-naught, linear power) converted to dB",
            "speckle_filter": f"{config['speckle_filter']} ({config['filter_size']}×{config['filter_size']}) in linear power",
            "change": "ΔB = B_later − B_earlier (dB)",
            "threshold_db": config["threshold_db"],
            "open_water_threshold_db": config["water_threshold_db"],
            "min_region_m2": config["min_region_m2"],
        },
        "missing_data_percent": round(100 - stats["valid_percent"], 3),
        "alignment": alignment_notes,
        "compatibility_warnings": compat.get("warnings", []),
        "false_positive_sources": FALSE_POSITIVE_SOURCES,
        "interpretation_caveat": (
            "A backscatter change is a change in the radar return, not a direct measurement of water extent or depth. "
            "Potential inundation flags are consistent with, but do not prove, surface-water change."
        ),
    }
