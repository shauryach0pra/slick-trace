#!/usr/bin/env python3
"""
Evaluate a trained U-Net on the same splits, with the same metrics, as the
classical baseline - and write the result where the validation report reads it.

WHY THIS IS SEPARATE FROM TRAINING
    The training script selects on validation IoU. A model evaluated only by
    the quantity it was selected on has not been independently measured, so
    this runs afterwards and reports the full metric set on both val and test.

WHAT IS AND IS NOT COMPARABLE
    The classical detector applies Lee speckle filtering before thresholding;
    the U-Net sees raw scenes and learns its own features. That asymmetry is
    deliberate - forcing a fixed preprocessing step on a convolutional model
    handicaps it - but it means the comparison is between two complete
    detectors, not two architectures. Stated here so the table is read
    correctly.

    Both are evaluated on identical splits with identical metrics: pixel IoU
    and recall on oil scenes, and per-scene false-positive rates on look-alike
    and clean scenes.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slicktrace_core.unet_model import UNet  # noqa: E402


def _predict(model, scene: np.ndarray, thresh: float) -> np.ndarray:
    x = torch.from_numpy(scene.astype(np.float32) / 255.0)[None, None]
    with torch.no_grad():
        return (torch.sigmoid(model(x))[0, 0].numpy() > thresh).astype(np.uint8)


def evaluate(model, split_dir: str, thresh: float) -> dict:
    ious, recalls, precisions = [], [], []
    fp_look = n_look = fp_clean = n_clean = 0

    for sp in sorted(glob.glob(os.path.join(split_dir, "*_scene.png"))):
        base = os.path.basename(sp)
        scene = np.array(Image.open(sp).convert("L"))
        pred = _predict(model, scene, thresh)

        if "oil" in base:
            truth = (np.array(Image.open(sp.replace("_scene.png", "_mask.png"))
                              .convert("L")) > 127).astype(np.uint8)
            inter = int((pred & truth).sum())
            union = int((pred | truth).sum())
            ious.append(inter / union if union else 1.0)
            recalls.append(inter / max(int(truth.sum()), 1))
            precisions.append(inter / max(int(pred.sum()), 1) if pred.sum() else 0.0)
        elif "lookalike" in base:
            n_look += 1
            fp_look += int(pred.sum() > 0)
        elif "clean" in base:
            n_clean += 1
            fp_clean += int(pred.sum() > 0)

    return {
        "iou_on_oil": round(float(np.mean(ious)), 4) if ious else None,
        "recall_on_oil": round(float(np.mean(recalls)), 4) if recalls else None,
        "precision_on_oil": round(float(np.mean(precisions)), 4) if precisions else None,
        "false_positive_rate_lookalike": round(fp_look / n_look, 4) if n_look else None,
        "false_positive_rate_clean": round(fp_clean / n_clean, 4) if n_clean else None,
        "n_oil": len(ious), "n_lookalike": n_look, "n_clean": n_clean,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="data/detection/unet.pt")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="data/detection/unet_eval.json")
    args = ap.parse_args()

    if not os.path.exists(args.checkpoint):
        print(f"No checkpoint at {args.checkpoint} - train first.")
        raise SystemExit(1)

    # Read the width from the checkpoint rather than assuming it: a hardcoded
    # base that disagrees with the trained model fails with a hundred lines of
    # shape mismatches and no statement of the actual cause.
    state = torch.load(args.checkpoint, map_location="cpu")
    base = int(state["enc1.0.weight"].shape[0])
    model = UNet(in_channels=1, out_channels=1, base=base)
    model.load_state_dict(state)
    print(f"loaded checkpoint with base={base}")
    model.eval()

    out = {
        "checkpoint": args.checkpoint,
        "decision_threshold": args.threshold,
        "val": evaluate(model, "data/detection/val", args.threshold),
        "test": evaluate(model, "data/detection/test", args.threshold),
        "preprocessing_note": (
            "The U-Net sees raw scenes; the classical baseline applies Lee speckle "
            "filtering before thresholding. The comparison is therefore between two "
            "complete detectors, not two architectures."
        ),
        "training_set_note": (
            "Trained on 60 oil-bearing 128x128 patches. That is a small positive set "
            "for a segmentation network, and overfitting is the expected failure mode; "
            "the test-split figures are the ones to read."
        ),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    for split in ("val", "test"):
        m = out[split]
        print(f"{split:<5} IoU {m['iou_on_oil']}  recall {m['recall_on_oil']}  "
              f"precision {m['precision_on_oil']}  "
              f"FP look {m['false_positive_rate_lookalike']}  "
              f"FP clean {m['false_positive_rate_clean']}")
    print(f"\nWritten: {args.out}")


if __name__ == "__main__":
    main()
