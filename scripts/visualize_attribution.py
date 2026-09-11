"""Render the step-4 demo figure: naive historical-proximity baseline
(wrong pick) vs forward-replay pipeline (correct pick), plus the winning
candidate's simulated footprint overlaid on the actual observed slick."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from datetime import datetime

from varuna_core.attribution import (
    ReleaseHypothesisSpec, simulate_hypothesis, ENSEMBLE_VARIANTS,
)
from varuna_core.hindcast import _parse



def _load_truth(case_dir: str) -> tuple[str | None, str | None]:
    """Dev-only. Returns (true_vessel_key, near_decoy_key), either of which may
    be None — absent-source cases have no true vessel in the manifest at all.
    Nothing shown to a reviewer may depend on this file."""
    path = os.path.join(case_dir, "truth.json")
    if not os.path.exists(path):
        return None, None
    with open(path) as f:
        truth = json.load(f)
    roles = truth.get("roles", {})
    near = next((k for k, v in roles.items() if v == "near_decoy"), None)
    return truth.get("true_vessel_key"), near

def render(case_dir: str = "data/cases/case_0001", out_path: str | None = None):
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(case_dir, "naive_baseline_result.json")) as f:
        baseline = json.load(f)
    with open(os.path.join(case_dir, "attribution_result.json")) as f:
        attribution = json.load(f)

    # Ground truth lives in a dev-only sidecar, never in the manifest and never
    # on the API. Absent-source cases legitimately have no true key.
    true_key, decoy_near_key = _load_truth(case_dir)
    observed_mask = (np.array(Image.open(manifest["mask_groundtruth_path"])) > 127).astype(np.uint8)
    bbox = manifest["bbox"]

    fig = plt.figure(figsize=(11, 4.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.1, 1.0])

    # --- panel 1: naive baseline ranking ---
    ax = fig.add_subplot(gs[0])
    keys = [r["vessel_key"] for r in baseline["ranking"]]
    dists = [r["distance_deg"] for r in baseline["ranking"]]
    wrong = baseline["top_candidate_id"] != true_key
    colors = ["#999999"] * len(keys)
    colors[0] = "#d62728" if wrong else "#2ca02c"  # top pick only
    labels = [f"{k}  (true source)" if k == true_key else k for k in keys]
    ax.barh(range(len(keys)), dists, color=colors)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("distance to slick (deg)", fontsize=8)
    ax.set_title(f"Naive historical-proximity baseline\ntop pick: {baseline['top_candidate_id']}"
                 f"{'  ✗ WRONG' if wrong else '  ✓'}", fontsize=9,
                 color="#d62728" if wrong else "#2ca02c")

    # --- panel 2: forward-replay ranking ---
    ax = fig.add_subplot(gs[1])
    keys2 = [r["vessel_key"] for r in attribution["ranking"]]
    ious2 = [r["mean_iou"] for r in attribution["ranking"]]
    correct = attribution["top_candidate_id"] == true_key
    colors2 = ["#999999"] * len(keys2)
    colors2[0] = "#2ca02c" if correct else "#d62728"
    labels2 = [f"{k}  (true source)" if k == true_key else k for k in keys2]
    ax.barh(range(len(keys2)), ious2, color=colors2)
    ax.set_yticks(range(len(keys2)))
    ax.set_yticklabels(labels2, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("mean IoU vs observed slick", fontsize=8)
    ax.axvline(attribution["abstention_iou_gate"], color="black", linestyle="--", linewidth=0.8)
    ax.text(attribution["abstention_iou_gate"], len(keys2) - 0.3, " abstention\n gate", fontsize=6)
    ax.set_title(f"Forward-replay attribution\ntop pick: {attribution['top_candidate_id']}"
                 f"{'  ✓ CORRECT' if correct else '  ✗ WRONG'}", fontsize=9,
                 color="#2ca02c" if correct else "#d62728")

    # --- panel 3: winning candidate's simulated footprint vs observed ---
    ax = fig.add_subplot(gs[2])
    top = attribution["ranking"][0]
    tracks_by_key = {tr["vessel_key"]: tr["fixes"] for tr in manifest["tracks"]}
    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    hyp = ReleaseHypothesisSpec(top["candidate_id"], top["vessel_key"], _parse(top["release_start"]),
                                  top["duration_hours"], top["is_continuous"])
    pred = simulate_hypothesis(hyp, tracks_by_key[top["vessel_key"]], u, v,
                                ENSEMBLE_VARIANTS[0], acquired, bbox, seed=0)

    rgb = np.zeros((*observed_mask.shape, 3))
    rgb[..., 0] = pred          # red = predicted
    rgb[..., 1] = observed_mask  # green = observed -> overlap shows yellow
    ax.imshow(rgb)
    ax.set_title(f"Top candidate footprint vs observed\n(IoU {top['mean_iou']:.2f}) "
                 f"— yellow=overlap", fontsize=9)
    ax.axis("off")

    fig.suptitle(f"{manifest['incident_id']} — forward-replay beats naive proximity  [SYNTHETIC]",
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])

    out_path = out_path or os.path.join(case_dir, "attribution_comparison.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    path = render()
    print(f"Saved {path}")
