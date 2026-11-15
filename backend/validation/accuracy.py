"""Pixel-wise agreement between a predicted binary map and a reference map (confusion-matrix metrics)."""
from __future__ import annotations

import numpy as np


def binary_metrics(pred: np.ndarray, ref: np.ndarray, valid: np.ndarray) -> dict:
    """Precision, recall, F1, IoU, overall accuracy and Cohen's kappa over ``valid`` pixels.

    Metrics whose denominator is zero are reported as None rather than invented.
    """
    p, r = pred[valid].astype(bool), ref[valid].astype(bool)
    tp = int(np.count_nonzero(p & r))
    fp = int(np.count_nonzero(p & ~r))
    fn = int(np.count_nonzero(~p & r))
    tn = int(np.count_nonzero(~p & ~r))
    n = tp + fp + fn + tn

    def div(a: float, b: float) -> float | None:
        return round(a / b, 4) if b else None

    precision, recall = div(tp, tp + fp), div(tp, tp + fn)
    f1 = div(2 * tp, 2 * tp + fp + fn)
    iou = div(tp, tp + fp + fn)
    acc = div(tp + tn, n)
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n) if n else 0
    kappa = round((acc - pe) / (1 - pe), 4) if n and acc is not None and pe < 1 else None
    return {"pixels": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall,
            "f1": f1, "iou": iou, "overall_accuracy": acc, "kappa": kappa,
            "predicted_fraction": div(tp + fp, n), "reference_fraction": div(tp + fn, n)}


def cell_fraction_agreement(pred_e, pred_l, ref_e, ref_l, valid, factor: int = 5, min_valid: float = 0.5) -> dict:
    """Agreement of the change in water *fraction* per coarse cell (factor×factor pixels).

    More forgiving of sub-cell misregistration and speckle than pixel-exact scoring, and closer to how
    a planner would use the map ("how much of this 100 m cell drained?").
    """
    h, w = (valid.shape[0] // factor) * factor, (valid.shape[1] // factor) * factor

    def blocks(a):
        return a[:h, :w].reshape(h // factor, factor, w // factor, factor)

    v = blocks(valid).sum(axis=(1, 3))
    ok = v >= min_valid * factor * factor
    with np.errstate(invalid="ignore", divide="ignore"):
        fr = {k: blocks(x & valid).sum(axis=(1, 3)) / v for k, x in (("pe", pred_e), ("pl", pred_l), ("re", ref_e), ("rl", ref_l))}
    dp, dr = (fr["pl"] - fr["pe"])[ok], (fr["rl"] - fr["re"])[ok]
    if dp.size < 10:
        return {"cells": int(dp.size)}
    r = float(np.corrcoef(dp, dr)[0, 1]) if dp.std() > 0 and dr.std() > 0 else None
    sig = (np.abs(dp) >= 0.25) | (np.abs(dr) >= 0.25)
    same_dir = float((np.sign(dp[sig]) == np.sign(dr[sig])).mean()) if sig.any() else None
    return {"cells": int(dp.size), "cell_size_px": factor, "pearson_r": round(r, 3) if r is not None else None,
            "mean_abs_diff": round(float(np.abs(dp - dr).mean()), 4),
            "net_change_pred": round(float(dp.mean()), 4), "net_change_ref": round(float(dr.mean()), 4),
            "direction_agreement_where_changed": round(same_dir, 3) if same_dir is not None else None,
            "changed_cells": int(sig.sum())}
