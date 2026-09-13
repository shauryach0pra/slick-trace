"""
Detect and characterise the slick in a case scene (PS part (a)).

Runs the classical baseline detector over the case's SAR-like scene, vectorises
the retained region, and measures it. Geometry is computed on the pixel grid
using the manifest's `pixel_spacing_m`, which is a LOCAL PLANAR approximation
valid over a scene this size — it is not a reprojection into the declared
metric CRS, and the output says so rather than implying more rigour than the
method has.

Ground-truth IoU is reported because these are synthetic cases where the truth
mask exists. On real imagery that field would be absent, not zero.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slicktrace_core.baseline_detector import predict_mask, iou  # noqa: E402

CASES_DIR = "data/cases"


def _boundary_lonlat(mask: np.ndarray, bbox: dict) -> list[list[float]]:
    """Trace the mask outline and map it to lon/lat via the scene bbox."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure()
    try:
        cs = plt.contour(mask.astype(float), levels=[0.5])
        segs = [seg for level in cs.allsegs for seg in level if len(seg) > 3]
        if not segs:
            return []
        verts = max(segs, key=len)
    finally:
        plt.close(fig)

    h, w = mask.shape
    out = []
    for x, y in verts:
        lon = bbox["min_lon"] + (x / (w - 1)) * (bbox["max_lon"] - bbox["min_lon"])
        lat = bbox["max_lat"] - (y / (h - 1)) * (bbox["max_lat"] - bbox["min_lat"])
        out.append([round(float(lon), 5), round(float(lat), 5)])
    # thin the outline: a 200-vertex polygon renders identically to a 60-vertex one
    step = max(1, len(out) // 60)
    return out[::step]


def characterise(case_dir: str) -> dict:
    manifest = json.load(open(os.path.join(case_dir, "manifest.json")))
    scene = np.array(Image.open(os.path.join(case_dir, "scene.png")).convert("L"))
    pred = predict_mask(scene)

    truth_path = os.path.join(case_dir, "mask_groundtruth.png")
    truth = (np.array(Image.open(truth_path).convert("L")) > 127).astype(np.uint8)

    spacing_m = float(manifest["pixel_spacing_m"])
    n_px = int(pred.sum())

    if n_px == 0:
        return {
            "incident_id": manifest["incident_id"],
            "detector": "classical baseline (local-contrast threshold, "
                        "connected components, uniformity rejection)",
            "detected": False,
            "case_state": "no_slick",
            "note": "No region survived the detector. A no-slick case must not "
                    "proceed into a forced vessel ranking.",
        }

    ys, xs = np.nonzero(pred)
    cx, cy = xs.mean(), ys.mean()
    coords = np.stack([xs - cx, ys - cy])
    cov = np.cov(coords)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]

    # 2-sigma extent along each principal axis, in metres
    major_m = 4.0 * math.sqrt(max(evals[0], 1e-9)) * spacing_m
    minor_m = 4.0 * math.sqrt(max(evals[1], 1e-9)) * spacing_m
    vx, vy = evecs[0, 0], evecs[1, 0]
    # image y grows downward, so negate for a true-north bearing
    bearing = (math.degrees(math.atan2(vx, -vy))) % 180.0

    area_km2 = n_px * (spacing_m ** 2) / 1e6

    # perimeter from boundary pixels, corrected for the staircase effect that
    # makes a pixelated outline ~11% longer than the underlying smooth curve
    from scipy.ndimage import binary_erosion, binary_fill_holes
    # Perimeter measures the region OUTLINE, so interior speckle holes are
    # filled first. Without this every single-pixel hole that survived the
    # darkness threshold contributes its own closed boundary: on case_0001 that
    # was 87 holes turning a 145-pixel outline into 458, and a 71 km perimeter
    # into 179 km. Filling applies to the measurement copy only — `pred` is
    # untouched, because changing the mask would silently alter the IoU this
    # detector is scored on.
    outline_src = binary_fill_holes(pred.astype(bool))
    boundary_px = int((outline_src & ~binary_erosion(outline_src)).sum())
    n_holes_filled = int(outline_src.sum() - pred.sum())
    # Correction calibrated empirically, not assumed: a 4-connected boundary
    # count on a digitised disc measures 0.89x the true circumference, stable
    # across radii 10-40 px. The previous constant here was 0.90, which pushed
    # the estimate the wrong way and drove the isoperimetric ratio below 1.0 —
    # geometrically impossible for any closed shape.
    BOUNDARY_COUNT_BIAS = 0.89
    perimeter_km = boundary_px * spacing_m / BOUNDARY_COUNT_BIAS / 1000.0

    return {
        "incident_id": manifest["incident_id"],
        "detector": "classical baseline (local-contrast threshold, "
                    "connected components, uniformity rejection)",
        "detected": True,
        "case_state": manifest.get("case_state", "potential_slick"),
        "geometry": {
            "area_km2": round(area_km2, 2),
            "perimeter_km": round(perimeter_km, 2),
            "interior_holes_filled_px": n_holes_filled,
            "major_axis_km": round(major_m / 1000.0, 2),
            "minor_axis_km": round(minor_m / 1000.0, 2),
            "elongation": round(major_m / max(minor_m, 1e-9), 2),
            "orientation_deg_from_north": round(bearing, 1),
            "centroid": [
                round(float(manifest["bbox"]["min_lon"]
                      + (cx / (pred.shape[1] - 1))
                      * (manifest["bbox"]["max_lon"] - manifest["bbox"]["min_lon"])), 5),
                round(float(manifest["bbox"]["max_lat"]
                      - (cy / (pred.shape[0] - 1))
                      * (manifest["bbox"]["max_lat"] - manifest["bbox"]["min_lat"])), 5),
            ],
        },
        "polygon": _boundary_lonlat(pred, manifest["bbox"]),
        "agreement_with_truth_mask": {
            "iou": round(float(iou(pred, truth)), 4),
            "note": "Available because this is a synthetic case with a generator "
                    "truth mask. On real imagery no such label exists.",
        },
        "measurement_note": (
            f"Geometry measured on the pixel grid at {spacing_m} m spacing — a local "
            "planar approximation over a scene of this size, not a reprojection into "
            f"{manifest.get('metric_crs', 'the declared metric CRS')}. Axis lengths are "
            "2-sigma extents along the principal axes."
        ),
        "boundary_note": (
            "SAR darkness is not proof of oil. Look-alikes (low wind, biogenic films) "
            "dampen backscatter too; detection confidence is kept separate from source "
            "confidence throughout."
        ),
    }


def main() -> None:
    cases = sorted(d for d in os.listdir(CASES_DIR)
                   if os.path.isdir(os.path.join(CASES_DIR, d)))
    for case_id in cases:
        case_dir = os.path.join(CASES_DIR, case_id)
        result = characterise(case_dir)
        out = os.path.join(case_dir, "detection_result.json")
        with open(out, "w") as fh:
            json.dump(result, fh, indent=2)
        if result["detected"]:
            g = result["geometry"]
            print(f"  {case_id}: {g['area_km2']} km², elongation {g['elongation']}, "
                  f"bearing {g['orientation_deg_from_north']}°, "
                  f"IoU vs truth {result['agreement_with_truth_mask']['iou']}")
        else:
            print(f"  {case_id}: no slick detected")


if __name__ == "__main__":
    main()


def run_detection(case_dir: str) -> dict:
    """Pipeline-stage entry point: characterise one case and write its artifact."""
    result = characterise(case_dir)
    with open(os.path.join(case_dir, "detection_result.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    return result
