"""Render scene / ground-truth / prediction triptychs for a few val samples
of each kind, plus the metrics headline, for demo screenshots."""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from varuna_core.baseline_detector import evaluate, iou, predict_mask


def render(split_dir: str = "data/detection/val", out_path: str = "data/detection/detection_demo.png",
           n_per_kind: int = 2):
    metrics = evaluate(split_dir)

    picks = []
    for kind in ["oil", "lookalike", "clean"]:
        paths = sorted(glob.glob(os.path.join(split_dir, f"*_{kind}_*_scene.png")))[:n_per_kind]
        picks.extend([(kind, p) for p in paths])

    fig, axes = plt.subplots(len(picks), 3, figsize=(7, 2.3 * len(picks)))
    for row, (kind, sp) in enumerate(picks):
        base = sp[: -len("_scene.png")]
        scene = np.array(Image.open(sp))
        truth = (np.array(Image.open(base + "_mask.png")) > 127).astype(np.uint8)
        pred = predict_mask(scene)
        this_iou = iou(pred, truth) if kind == "oil" else None

        for col, (img, title) in enumerate([
            (scene, f"{kind} — scene"),
            (truth * 255, "ground truth"),
            (pred * 255, f"baseline pred" + (f"  (IoU {this_iou:.2f})" if this_iou is not None else
                                               "  (should be empty)")),
        ]):
            ax = axes[row, col]
            ax.imshow(img, cmap="gray", vmin=0, vmax=255)
            ax.set_title(title, fontsize=8)
            ax.axis("off")

    fig.suptitle(
        f"Baseline detector (classical CV) — val set\n"
        f"IoU on oil: {metrics.iou_on_oil:.3f}  |  "
        f"FP rate look-alike: {metrics.false_positive_rate_lookalike:.2f}  |  "
        f"FP rate clean: {metrics.false_positive_rate_clean:.2f}",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path, metrics


if __name__ == "__main__":
    path, m = render()
    print(f"Saved {path}")
