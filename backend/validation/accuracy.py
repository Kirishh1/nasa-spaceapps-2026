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
