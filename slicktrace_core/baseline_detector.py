"""
Baseline detector (classical CV, no ML training needed).

Per the masterplan (p.9): "use a single second architecture only if the
baseline is complete and the result would change a decision." This is that
baseline — cheap, fast, runs anywhere, and gives a number the real U-Net has
to beat before it's worth the added complexity.

Method:
  1. Threshold scene intensity relative to local background statistics.
  2. Connected-component label the thresholded regions.
  3. Reject small regions (noise) and reject "patchy" regions whose internal
     darkening is uneven — a crude physical stand-in for "real oil dampens
     capillary waves fairly uniformly across the slick, most look-alikes
     (wind shadows, biogenic slicks) don't."
  4. What survives is the predicted oil mask.

This is deliberately simple. It's expected to do OK on clean+oil separation
and only partially reject look-alikes — that gap is exactly the number that
justifies training the U-Net next.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_opening


@dataclass
class DetectionMetrics:
    iou_on_oil: float
    # Masterplan p.15 asks for recall >= 0.85 and precision alongside IoU, and
    # is explicit that pixel accuracy is not a substitute. These are pixel-level
    # and computed on oil scenes only: on a look-alike or clean scene the truth
    # mask is empty, so recall is undefined and precision is always 0 whenever
    # anything is predicted — which is what the false-positive rates below
    # measure, per scene rather than per pixel.
    recall_on_oil: float
    precision_on_oil: float
    false_positive_rate_lookalike: float
    false_positive_rate_clean: float
    n_oil: int
    n_lookalike: int
    n_clean: int


def predict_mask(scene: np.ndarray, dark_thresh_pct: float = 65,
                  min_region_px: int = 60, uniformity_std_max: float = 45.0,
                  speckle_window: int = 7) -> np.ndarray:
    """scene: uint8 grayscale array. Returns binary predicted mask (uint8, 0/1).

    Lee speckle filtering is applied first, and the darkness threshold is 0.65
    rather than 0.75 because of it. Both were measured, not assumed: filtering
    alone raises recall, and the filtered scene tolerates a stricter threshold,
    so the false-positive rate on look-alike scenes stays at zero. Threshold
    chosen on the training split before val or test were examined.

        raw, 0.75      val IoU 0.677  recall 0.682  FP 0.000
        Lee 7x7, 0.65  val IoU 0.857  recall 0.860  FP 0.000

    Pass speckle_window=0 to disable filtering, which is what the benchmark
    comparison in the validation report uses to measure the filter's own
    contribution.
    """
    if speckle_window:
        from slicktrace_core.speckle import lee_filter
        scene = lee_filter(scene, speckle_window)
    bg_level = np.median(scene)
    threshold = bg_level * (dark_thresh_pct / 100.0)
    candidate = (scene < threshold).astype(np.uint8)
    candidate = binary_opening(candidate, iterations=1).astype(np.uint8)

    labeled, n = label(candidate)
    pred = np.zeros_like(candidate)
    for region_id in range(1, n + 1):
        region_mask = labeled == region_id
        area = int(region_mask.sum())
        if area < min_region_px:
            continue
        region_vals = scene[region_mask].astype(float)
        if region_vals.std() > uniformity_std_max:
            continue  # too patchy -> treat as look-alike, reject
        pred[region_mask] = 1
    return pred


def iou(pred: np.ndarray, truth: np.ndarray) -> float:
    pred_b, truth_b = pred.astype(bool), truth.astype(bool)
    inter = np.logical_and(pred_b, truth_b).sum()
    union = np.logical_or(pred_b, truth_b).sum()
    return float(inter / union) if union > 0 else 1.0


def recall_precision(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    """Pixel-level recall and precision on a scene that contains oil.

    Returned as a pair because they trade off: this detector rejects patchy
    regions, which raises precision and costs recall. Reporting either alone
    would hide that.
    """
    pred_b, truth_b = pred.astype(bool), truth.astype(bool)
    tp = float(np.logical_and(pred_b, truth_b).sum())
    fn = float(np.logical_and(~pred_b, truth_b).sum())
    fp = float(np.logical_and(pred_b, ~truth_b).sum())
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    # No prediction at all on a scene that does contain oil is a total miss,
    # not undefined precision — scoring it nan would quietly drop the worst
    # cases out of the average.
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    return recall, precision


def evaluate_split(split_dir: str = "data/detection/val") -> DetectionMetrics:
    scene_paths = sorted(glob.glob(os.path.join(split_dir, "*_scene.png")))
    ious, recalls, precisions, fp_lookalike, fp_clean = [], [], [], [], []
    n_oil = n_lookalike = n_clean = 0

    for sp in scene_paths:
        base = sp[: -len("_scene.png")]
        mask_path = base + "_mask.png"
        kind = os.path.basename(base).split("_")[1]  # train_<kind>_####  or val_<kind>_####

        scene = np.array(Image.open(sp))
        truth = (np.array(Image.open(mask_path)) > 127).astype(np.uint8)
        pred = predict_mask(scene)

        if kind == "oil":
            n_oil += 1
            ious.append(iou(pred, truth))
            r, pr = recall_precision(pred, truth)
            recalls.append(r)
            precisions.append(pr)
        elif kind == "lookalike":
            n_lookalike += 1
            fp_lookalike.append(1 if pred.sum() > 0 else 0)
        elif kind == "clean":
            n_clean += 1
            fp_clean.append(1 if pred.sum() > 0 else 0)

    return DetectionMetrics(
        iou_on_oil=float(np.mean(ious)) if ious else float("nan"),
        recall_on_oil=float(np.nanmean(recalls)) if recalls else float("nan"),
        precision_on_oil=float(np.mean(precisions)) if precisions else float("nan"),
        false_positive_rate_lookalike=float(np.mean(fp_lookalike)) if fp_lookalike else float("nan"),
        false_positive_rate_clean=float(np.mean(fp_clean)) if fp_clean else float("nan"),
        n_oil=n_oil, n_lookalike=n_lookalike, n_clean=n_clean,
    )


# Backwards-compatible alias: `evaluate` was the original name.
evaluate = evaluate_split


if __name__ == "__main__":
    import sys
    split = sys.argv[1] if len(sys.argv) > 1 else "data/detection/val"
    m = evaluate_split(split)
    print(f"[baseline detector | {os.path.basename(split)} set: {m.n_oil} oil, {m.n_lookalike} lookalike, {m.n_clean} clean]")
    print(f"  IoU on true oil slicks:            {m.iou_on_oil:.3f}")
    print(f"  Recall on true oil slicks:          {m.recall_on_oil:.3f}")
    print(f"  Precision on true oil slicks:       {m.precision_on_oil:.3f}")
    print(f"  False-positive rate on look-alikes: {m.false_positive_rate_lookalike:.3f}")
    print(f"  False-positive rate on clean water: {m.false_positive_rate_clean:.3f}")
