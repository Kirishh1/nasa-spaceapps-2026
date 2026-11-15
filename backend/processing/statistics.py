"""Statistics computed strictly from processed arrays."""
from __future__ import annotations

import math

import numpy as np

from backend.processing import change_detection as cd
from backend.processing import inundation as inu


def _km2(n: int, px_m2: float) -> float:
    return round(n * px_m2 / 1e6, 4)


def noise_reference(delta_db: np.ndarray, change_class: np.ndarray, threshold_db: float | None) -> dict:
    """Robust spread of ΔB and the share of pixels a zero-mean Gaussian of that spread would push past
    the threshold. A large excess of observed over expected exceedances indicates change beyond the
    bulk ΔB scatter; the Gaussian is a reference, not a speckle model."""
    d = delta_db[change_class > 0]
    if not d.size or threshold_db is None:
        return {}
    med = float(np.median(d))
    sigma = 1.4826 * float(np.median(np.abs(d - med)))
    expected = math.erfc(threshold_db / (sigma * math.sqrt(2))) if sigma > 0 else 0.0
    observed = float(np.count_nonzero(np.abs(d) >= threshold_db)) / d.size
    return {"robust_sigma_db": round(sigma, 3), "threshold_in_sigma": round(threshold_db / sigma, 2) if sigma else None,
            "expected_exceedance_percent_gaussian": round(100 * expected, 2), "observed_exceedance_percent": round(100 * observed, 2)}


def change_statistics(
    delta_db: np.ndarray,
    change_class: np.ndarray,
    inundation: np.ndarray,
    analysis_mask: np.ndarray,
    pixel_area_m2: float,
    earlier_db: np.ndarray,
    later_db: np.ndarray,
    threshold_db: float | None = None,
) -> dict:
    total = int(np.count_nonzero(analysis_mask))
    valid = int(np.count_nonzero(change_class > 0))
    n_dec = int(np.count_nonzero(change_class == cd.DECREASE))
    n_inc = int(np.count_nonzero(change_class == cd.INCREASE))
    n_lim = int(np.count_nonzero(change_class == cd.LIMITED))
    n_ow = int(np.count_nonzero(inundation == inu.OPEN_WATER))
    n_vf = int(np.count_nonzero(inundation == inu.VEGETATED))
    d = delta_db[(change_class > 0)]
    hist_counts, hist_edges = np.histogram(d, bins=60, range=(-15, 15)) if d.size else (np.zeros(60, int), np.linspace(-15, 15, 61))

    def pct(n: int, base: int) -> float:
        return round(100.0 * n / base, 3) if base else 0.0

    def dist(a: np.ndarray) -> dict:
        a = a[np.isfinite(a) & analysis_mask]
        if not a.size:
            return {}
        p = np.percentile(a, [5, 25, 50, 75, 95])
        return {"mean": round(float(a.mean()), 3), "std": round(float(a.std()), 3),
                "p05": round(float(p[0]), 3), "p25": round(float(p[1]), 3), "median": round(float(p[2]), 3),
                "p75": round(float(p[3]), 3), "p95": round(float(p[4]), 3)}

    return {
        "pixel_area_m2": pixel_area_m2,
        "analyzed_pixels": total,
        "analyzed_area_km2": _km2(total, pixel_area_m2),
        "valid_pixels": valid,
        "valid_percent": pct(valid, total),
        "missing_pixels": total - valid,
        "missing_area_km2": _km2(total - valid, pixel_area_m2),
        "classes": {
            "significant_decrease": {"pixels": n_dec, "area_km2": _km2(n_dec, pixel_area_m2), "percent_of_valid": pct(n_dec, valid)},
            "significant_increase": {"pixels": n_inc, "area_km2": _km2(n_inc, pixel_area_m2), "percent_of_valid": pct(n_inc, valid)},
            "limited_change": {"pixels": n_lim, "area_km2": _km2(n_lim, pixel_area_m2), "percent_of_valid": pct(n_lim, valid)},
        },
        "significant_change_area_km2": _km2(n_dec + n_inc, pixel_area_m2),
        "potential_inundation": {
            "open_water": {"pixels": n_ow, "area_km2": _km2(n_ow, pixel_area_m2), "percent_of_valid": pct(n_ow, valid)},
            "vegetated": {"pixels": n_vf, "area_km2": _km2(n_vf, pixel_area_m2), "percent_of_valid": pct(n_vf, valid)},
        },
        "delta_db": dist(delta_db),
        "noise_reference": noise_reference(delta_db, change_class, threshold_db),
        "earlier_db": dist(earlier_db),
        "later_db": dist(later_db),
        "histogram": {"edges": [round(float(e), 3) for e in hist_edges], "counts": [int(c) for c in hist_counts],
                      "clipped_below": int(np.count_nonzero(d < -15)), "clipped_above": int(np.count_nonzero(d > 15))},
    }
