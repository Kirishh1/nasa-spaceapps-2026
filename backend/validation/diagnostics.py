"""Diagnostics that explain validation numbers rather than add new ones.

* ``landcover_agreement_detail``: L-band vs C-band change-class agreement per land-cover class, split into
  "both stable" and "both changed the same way", with Cohen's kappa and a spatial block-bootstrap 95% interval.
  Agreement where both bands report no significant change is real agreement but says little about change
  detection, so it is reported separately.
* ``edge_buffer_change_f1``: change-map agreement after excluding pixels within k pixels of any water/land
  boundary (in either map, on either date). This is a diagnostic of *where* disagreement sits, never a
  replacement accuracy figure.
* ``error_budget``: per-date water-map disagreement area (FP + FN) compared with the size of the change.
"""
from __future__ import annotations

import numpy as np

from backend.comparison import disagreement as dis
from backend.processing.change_detection import DECREASE, INCREASE, LIMITED, NODATA


def _kappa3(a: np.ndarray, b: np.ndarray) -> float | None:
    """Cohen's kappa over three classes (decrease / limited / increase)."""
    n = a.size
    if n == 0:
        return None
    classes = (DECREASE, LIMITED, INCREASE)
    po = float((a == b).mean())
    pe = sum(float((a == c).mean()) * float((b == c).mean()) for c in classes)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def landcover_agreement_detail(a_cells: np.ndarray, b_cells: np.ndarray, lc_cells: np.ndarray, names: dict[int, str],
                               block: int = 50, n_boot: int = 500, min_cells: int = 25, seed: int = 0) -> list[dict]:
    """Per land-cover class detail on aggregated grids (a = NISAR, b = C-band). ``block`` cells per bootstrap block
    (50 × 100 m = 5 km), so the interval respects spatial autocorrelation."""
    agreement, _ = dis.compare(a_cells, b_cells)
    rng = np.random.default_rng(seed)
    by, bx = np.indices(agreement.shape)
    block_id = (by // block) * (agreement.shape[1] // block + 1) + (bx // block)
    out = []
    for code, name in names.items():
        m = (lc_cells == code) & (agreement > 0)
        n = int(m.sum())
        if n < min_cells:
            continue
        ag = agreement[m]
        cnt = {k: int((ag == v).sum()) for k, v in [("agree_stable", dis.AGREE_STABLE), ("agree_decrease", dis.AGREE_DECREASE),
                                                     ("agree_increase", dis.AGREE_INCREASE), ("only_l", dis.ONLY_A),
                                                     ("only_c", dis.ONLY_B), ("opposite", dis.OPPOSITE)]}
        agree = cnt["agree_stable"] + cnt["agree_decrease"] + cnt["agree_increase"]
        changed = n - cnt["agree_stable"]
        # bootstrap over spatial blocks
        ids = block_id[m]
        agree_mask = np.isin(ag, [dis.AGREE_STABLE, dis.AGREE_DECREASE, dis.AGREE_INCREASE])
        uniq, inv = np.unique(ids, return_inverse=True)
        tot_b = np.bincount(inv, minlength=len(uniq)).astype(float)
        agr_b = np.bincount(inv, weights=agree_mask, minlength=len(uniq))
        boots = []
        if len(uniq) >= 5:
            for _ in range(n_boot):
                pick = rng.integers(0, len(uniq), len(uniq))
                t = tot_b[pick].sum()
                if t:
                    boots.append(100 * agr_b[pick].sum() / t)
        out.append({
            "class": code, "name": name, "cells": n, "blocks": int(len(uniq)), **cnt,
            "agree_percent": round(100 * agree / n, 1),
            "agree_stable_percent": round(100 * cnt["agree_stable"] / n, 1),
            "agree_change_percent": round(100 * (cnt["agree_decrease"] + cnt["agree_increase"]) / n, 1),
            "either_changed_percent": round(100 * changed / n, 1),
            "change_agreement_where_either_changed_percent": round(100 * (cnt["agree_decrease"] + cnt["agree_increase"]) / changed, 1) if changed else None,
            "l_band_only_percent": round(100 * cnt["only_l"] / n, 1),
            "c_band_only_percent": round(100 * cnt["only_c"] / n, 1),
            "opposite_percent": round(100 * cnt["opposite"] / n, 1),
            "kappa": _kappa3(a_cells[m], b_cells[m]),
            "agree_percent_ci95": [round(float(np.percentile(boots, 2.5)), 1), round(float(np.percentile(boots, 97.5)), 1)] if boots else None,
        })
    return out


def boundary(mask: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Pixels whose 4-neighbourhood contains the other class."""
    m = mask & valid
    b = np.zeros_like(m)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        s = np.roll(np.roll(m, dy, 0), dx, 1)
        b |= s != m
    b[0, :] = b[-1, :] = b[:, 0] = b[:, -1] = False
    return b & valid


def dilate(mask: np.ndarray, r: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(r):
        o = out.copy()
        o[1:] |= out[:-1]
        o[:-1] |= out[1:]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def edge_buffer_change_f1(pred_lost: np.ndarray, ref_lost: np.ndarray, valid: np.ndarray, edges: np.ndarray,
                          radii=(0, 1, 2, 3, 5)) -> list[dict]:
    from backend.validation.accuracy import binary_metrics

    out = []
    for r in radii:
        keep = valid & ~(dilate(edges, r) if r else np.zeros_like(edges))
        m = binary_metrics(pred_lost, ref_lost, keep)
        out.append({"exclude_within_px": r, "kept_fraction": round(float(keep.sum() / max(1, valid.sum())), 3),
                    "f1": m["f1"], "precision": m["precision"], "recall": m["recall"]})
    return out


__all__ = ["landcover_agreement_detail", "edge_buffer_change_f1", "boundary", "dilate", "NODATA"]
