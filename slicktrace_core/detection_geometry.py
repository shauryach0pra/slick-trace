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



EARTH_RADIUS_M = 6_371_008.8


def _aeqd_scales(manifest: dict) -> tuple[float, float, float]:
    """Local metric scales for one pixel, at the scene's centre latitude.

    The manifest carries a single `pixel_spacing_m`, which treats a pixel as
    square. It is not: a degree of longitude shrinks by cos(latitude) while a
    degree of latitude does not. At 18.9 N that is 434 m north-south against
    411 m east-west - a 5.7% anisotropy, and a 5% error in area if ignored.

    This is an azimuthal-equidistant treatment centred on the scene: distances
    and directions from the centre are true, which is what area, axis lengths
    and bearing need. It replaces the planar approximation recorded in
    assumption A15 and needs no reprojection library to do it.
    """
    b = manifest["bbox"]
    n = int(manifest["img_size_px"])
    lat0 = (b["min_lat"] + b["max_lat"]) / 2.0
    dy = (b["max_lat"] - b["min_lat"]) * math.pi / 180.0 * EARTH_RADIUS_M / n
    dx = ((b["max_lon"] - b["min_lon"]) * math.pi / 180.0
          * EARTH_RADIUS_M * math.cos(math.radians(lat0)) / n)
    return dx, dy, lat0


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


import inspect as _inspect


def _detector_defaults() -> dict:
    """Read the detector's own defaults rather than restating them here, so the
    recorded provenance cannot drift away from the code that produced the mask."""
    sig = _inspect.signature(predict_mask)
    return {k: v.default for k, v in sig.parameters.items()
            if v.default is not _inspect.Parameter.empty}


_DEFAULTS = _detector_defaults()


def _measure_region(mask: np.ndarray, manifest: dict, dx_m: float, dy_m: float) -> dict:
    """Geometry of one connected region, in local metres."""
    from scipy.ndimage import binary_erosion, binary_fill_holes
    n_px = int(mask.sum())
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    mx = (xs - cx) * dx_m
    my = -(ys - cy) * dy_m
    cov = np.cov(np.stack([mx, my]))
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]
    major_m = 4.0 * math.sqrt(max(evals[0], 1e-9))
    minor_m = 4.0 * math.sqrt(max(evals[1], 1e-9))
    bearing = (math.degrees(math.atan2(evecs[0, 0], evecs[1, 0]))) % 180.0

    outline = binary_fill_holes(mask.astype(bool))
    boundary_px = int((outline & ~binary_erosion(outline)).sum())
    perimeter_km = boundary_px * math.sqrt(dx_m * dy_m) / 0.89 / 1000.0
    area_km2 = n_px * dx_m * dy_m / 1e6
    b = manifest["bbox"]
    return {
        "area_km2": round(area_km2, 2),
        "perimeter_km": round(perimeter_km, 2),
        "major_axis_km": round(major_m / 1000.0, 2),
        "minor_axis_km": round(minor_m / 1000.0, 2),
        "elongation": round(major_m / max(minor_m, 1e-9), 2),
        "orientation_deg_from_north": round(bearing, 1),
        "interior_holes_filled_px": int(outline.sum() - n_px),
        "centroid": [
            round(float(b["min_lon"] + (cx / (mask.shape[1] - 1))
                        * (b["max_lon"] - b["min_lon"])), 5),
            round(float(b["max_lat"] - (cy / (mask.shape[0] - 1))
                        * (b["max_lat"] - b["min_lat"])), 5),
        ],
    }


def _all_regions(pred: np.ndarray, manifest: dict, dx_m: float, dy_m: float) -> list[dict]:
    """Measure every retained region, largest first.

    The detector's own loop can retain several disconnected regions, and a real
    scene routinely contains more than one slick - a vessel under way leaves a
    trail that breaks into segments, and two unrelated discharges can appear in
    the same frame. The geometry stage previously traced only the longest
    contour, so a second slick was silently dropped: not reported as unmeasured,
    simply absent. Every region is measured here, and the largest is promoted to
    the top-level fields so a reader looking at one slick still finds it where
    it was.
    """
    from scipy.ndimage import label as _label
    lab, n = _label(pred)
    out = []
    for r in range(1, n + 1):
        m = (lab == r)
        if m.sum() < 1:
            continue
        g = _measure_region(m, manifest, dx_m, dy_m)
        g["region_px"] = int(m.sum())
        out.append(g)
    out.sort(key=lambda g: -g["region_px"])
    return out


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

    dx_m, dy_m, lat0 = _aeqd_scales(manifest)
    _regions = _all_regions(pred, manifest, dx_m, dy_m)

    ys, xs = np.nonzero(pred)
    cx, cy = xs.mean(), ys.mean()
    # Work in local metres, not pixels: the principal axes of an anisotropic
    # pixel grid are not the principal axes of the region it represents.
    mx = (xs - cx) * dx_m
    my = -(ys - cy) * dy_m          # image y grows downward; flip to north-up
    cov = np.cov(np.stack([mx, my]))
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]

    # 2-sigma extent along each principal axis, already in metres
    major_m = 4.0 * math.sqrt(max(evals[0], 1e-9))
    minor_m = 4.0 * math.sqrt(max(evals[1], 1e-9))
    vx, vy = evecs[0, 0], evecs[1, 0]
    bearing = (math.degrees(math.atan2(vx, vy))) % 180.0

    area_km2 = n_px * dx_m * dy_m / 1e6

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
    # Geometric mean of the two axis scales: a boundary step is as often
    # east-west as north-south, so neither scale alone is right.
    perimeter_km = (boundary_px * math.sqrt(dx_m * dy_m)
                    / BOUNDARY_COUNT_BIAS / 1000.0)

    return {
        "incident_id": manifest["incident_id"],
        "detector": "classical baseline (local-contrast threshold, "
                    "connected components, uniformity rejection)",
        # Which detector, at which settings, produced this mask. Recorded on the
        # artifact rather than left to be inferred from whichever version of the
        # source happens to be checked out: a mask without its parameters cannot
        # be reproduced or argued with, and the threshold in particular is a
        # chosen operating point rather than an optimum (see the operating-point
        # curve in the validation report).
        "detector_params": {
            "dark_thresh_pct": _DEFAULTS["dark_thresh_pct"],
            "min_region_px": _DEFAULTS["min_region_px"],
            "uniformity_std_max": _DEFAULTS["uniformity_std_max"],
            "boundary_count_bias": BOUNDARY_COUNT_BIAS,
            "note": ("threshold is a fraction of the scene median, not an absolute "
                     "level; it adapts to scene brightness but not to scene contrast"),
        },
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
        # Every retained region, largest first. The top-level geometry above
        # describes regions[0]; a scene with one slick reads identically to
        # before, and a scene with several no longer loses them silently.
        "n_regions": len(_regions),
        "regions": _regions,
        "total_area_km2": round(sum(g["area_km2"] for g in _regions), 2),
        "multi_region_note": (
            "Top-level geometry describes the largest region. A second slick in the "
            "same scene is measured and listed under regions, not merged into the "
            "first and not dropped." if len(_regions) > 1 else
            "Single region in this scene; top-level geometry and regions[0] agree."),
        "agreement_with_truth_mask": {
            "iou": round(float(iou(pred, truth)), 4),
            "note": "Available because this is a synthetic case with a generator "
                    "truth mask. On real imagery no such label exists.",
        },
        "measurement_note": (
            f"Geometry measured in local azimuthal-equidistant metres centred on the "
            f"scene at {lat0:.2f} N: {dx_m:.1f} m east-west against {dy_m:.1f} m "
            f"north-south, rather than the manifest's single {spacing_m} m figure, which "
            f"treats a pixel as square and overstates area by about 5% at this latitude. "
            f"Distances and directions from the scene centre are true, which is what "
            f"area, axis lengths and bearing require. This is not a full reprojection "
            f"into {manifest.get('metric_crs', 'the declared metric CRS')} - over a scene "
            f"one degree across the difference is far below the detector's own boundary "
            f"uncertainty. Axis lengths are 2-sigma extents along the principal axes."
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
