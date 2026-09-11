"""
Render a two-panel figure for one case:
  left  = synthetic SAR scene with detected/ground-truth slick contour
  right = vessel tracks in the origin envelope, colour-coded

Dev mode (--reveal-truth) additionally marks the true source vessel and the
near-but-innocent decoy, purely for building/debugging the attribution
engine — this flag must be OFF for anything shown to a judge, since it
reveals the hidden ground truth the ranking algorithm is supposed to find
on its own.
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def load_case(case_dir: str) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        return json.load(f)



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

def plot_case(case_dir: str, reveal_truth: bool = False, out_path: str | None = None):
    manifest = load_case(case_dir)
    scene = np.array(Image.open(manifest["image_path"]))
    mask = np.array(Image.open(manifest["mask_groundtruth_path"]))
    bbox = manifest["bbox"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))

    # --- left: SAR scene ---
    ax = axes[0]
    ax.imshow(scene, cmap="gray")
    ax.contour(mask, levels=[127], colors="#00e0c0", linewidths=1.5)
    ax.set_title(f"{manifest['incident_id']}  |  acquired {manifest['acquired_utc']}\n"
                 f"[SYNTHETIC — dev/demo data]", fontsize=9)
    ax.axis("off")

    # --- right: vessel tracks over the origin envelope ---
    ax = axes[1]
    ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
    ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
    ax.set_aspect("equal")
    ax.set_title("Candidate vessel tracks (origin envelope)", fontsize=9)
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")

    # Ground truth lives in a dev-only sidecar, never in the manifest and never
    # on the API. Absent-source cases legitimately have no true key.
    true_key, decoy_near_key = _load_truth(case_dir)
    # avoid red/orange for the neutral palette so the dev-only highlight colors
    # (reserved below) never collide with an "ordinary" vessel's color
    neutral_palette = ["#4c72b0", "#55a868", "#8172b2", "#937860", "#64b5cd", "#ccb974"]
    neutral_i = 0

    for tr in manifest["tracks"]:
        lons = [f["lon"] for f in tr["fixes"]]
        lats = [f["lat"] for f in tr["fixes"]]
        vkey = tr["vessel_key"]

        label = vkey
        lw = 1.2
        if reveal_truth and vkey == true_key:
            color, lw, label = "red", 2.5, f"{vkey} (TRUE SOURCE — dev only)"
        elif reveal_truth and vkey == decoy_near_key:
            color, lw, label = "orange", 2.0, f"{vkey} (nearest decoy — dev only)"
        else:
            color = neutral_palette[neutral_i % len(neutral_palette)]
            neutral_i += 1

        ax.plot(lons, lats, "-o", color=color, linewidth=lw, markersize=3, label=label)

    # mark scene centroid (roughly where the slick is)
    ax.scatter([sum(bbox[k] for k in ("min_lon", "max_lon")) / 2 - 0.13],
               [sum(bbox[k] for k in ("min_lat", "max_lat")) / 2 + 0.13],
               marker="*", s=180, color="#00b0a0", zorder=5, label="observed slick (approx)")

    ax.legend(fontsize=6, loc="lower left", framealpha=0.85)
    fig.tight_layout()

    out_path = out_path or os.path.join(case_dir, "case_overview.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", default="data/cases/case_0001")
    ap.add_argument("--reveal-truth", action="store_true",
                     help="DEV ONLY: overlay the hidden true source / near-decoy labels")
    args = ap.parse_args()
    path = plot_case(args.case_dir, reveal_truth=args.reveal_truth)
    print(f"Saved {path}")
