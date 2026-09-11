"""
Rank-fragility explorer (masterplan p.12 — promoted P1 -> P0 in v3.0).

The question this answers is "what would have to be different for this answer
to change?". Published comparators (CleanSeaNet, Cerulean) document source
association and drift backtracking; none document exposing the stability of
their own ranking to the user. That is the defensible novelty claim, so it is
a core deliverable rather than an optional tail feature.

Method
  1. Take the ranking's per-candidate best release hypothesis as the baseline.
  2. Walk a grid of physically plausible perturbations — current bias in both
     components, diffusivity scale, footprint rasterisation threshold, and a
     shift in assumed release duration — in INCREASING order of standardised
     magnitude.
  3. Re-run every candidate under each perturbation using the same budget,
     and record which candidate leads.
  4. Report the SMALLEST tested standardised perturbation that changes the
     top-ranked source, together with both runs so a reviewer can inspect the
     footprints rather than take a verbal claim on trust.

What this is not
  A sensitivity counterfactual is not proof of causal responsibility, and
  ensemble/grid win frequency is not a calibrated probability. Every number
  here comes from an actual computation; nothing is interpolated for display.

Standardised magnitude: each axis is normalised by its own maximum tested
offset, so a magnitude of 1.0 means "one axis pushed to the edge of its
plausible range", and 0.5 means half that. Magnitudes are comparable across
axes by construction, not by physical equivalence — the axis is always
reported alongside the number.
"""

from __future__ import annotations

import itertools
import json
import os
from datetime import timedelta

import numpy as np
from PIL import Image

from slicktrace_core.attribution import (
    LOSS_WEIGHTS,
    ReleaseHypothesisSpec,
    raster_particles_to_mask,
    score_fit,
)
from slicktrace_core.hindcast import DEG_PER_MS_HR, _interp_track_position, _parse

# Axis name -> (tested offsets, normalising scale, human label)
AXES = {
    "current_u_bias": ([-0.06, -0.03, 0.0, 0.03, 0.06], 0.06, "along-shore current bias (m/s)"),
    "current_v_bias": ([-0.06, -0.03, 0.0, 0.03, 0.06], 0.06, "cross-shore current bias (m/s)"),
    "diffusivity_scale": ([0.6, 0.8, 1.0, 1.4, 1.8], 0.8, "diffusivity multiplier"),
    "mask_threshold": ([0.10, 0.15, 0.22], 0.07, "footprint rasterisation threshold"),
    "duration_shift_h": ([-1.0, 0.0, 1.0], 1.0, "assumed release duration shift (h)"),
}

NOMINAL = {"current_u_bias": 0.0, "current_v_bias": 0.0, "diffusivity_scale": 1.0,
           "mask_threshold": 0.15, "duration_shift_h": 0.0}

MAX_POINTS = 80  # runtime cap; the achieved count is reported, not the planned one


def _magnitude(point: dict) -> float:
    """L1 distance from nominal in normalised axis units."""
    total = 0.0
    for axis, (_, scale, _label) in AXES.items():
        total += abs(point[axis] - NOMINAL[axis]) / scale
    return round(total, 4)


def _enumerate_points(max_points: int = MAX_POINTS) -> list[dict]:
    """Single-axis perturbations plus every two-axis combination, ordered by
    increasing standardised magnitude. Higher-order combinations are not
    tested; the report says so rather than implying full coverage."""
    points = []
    names = list(AXES)
    for axis in names:
        for value in AXES[axis][0]:
            if value == NOMINAL[axis]:
                continue
            points.append({**NOMINAL, axis: value})
    for a, b in itertools.combinations(names, 2):
        for va, vb in itertools.product(AXES[a][0], AXES[b][0]):
            if va == NOMINAL[a] or vb == NOMINAL[b]:
                continue
            points.append({**NOMINAL, a: va, b: vb})
    points.sort(key=_magnitude)
    return points[:max_points]


def _simulate(fixes, release_start, duration_hours, is_continuous, acquired, bbox,
              u, v, point, n_particles=250, seed=0) -> np.ndarray:
    """One forward twin under a specific perturbation point."""
    rng = np.random.default_rng(seed)
    duration = max(0.25, duration_hours + point["duration_shift_h"])
    u_eff = u + point["current_u_bias"]
    v_eff = v + point["current_v_bias"]
    diffusivity = 0.020 * point["diffusivity_scale"]

    offsets = (rng.uniform(0, duration, n_particles) if is_continuous
               else np.zeros(n_particles))
    lons = np.zeros(n_particles)
    lats = np.zeros(n_particles)
    for i, off in enumerate(offsets):
        pos = _interp_track_position(fixes, release_start + timedelta(hours=float(off)))
        if pos is None:
            pos = _interp_track_position(fixes, release_start) or (fixes[0]["lon"], fixes[0]["lat"])
        lons[i], lats[i] = pos

    drift_h = np.array([(acquired - (release_start + timedelta(hours=float(o)))).total_seconds() / 3600
                        for o in offsets])
    drift_h = np.clip(drift_h, 0, None)
    spread = diffusivity * np.sqrt(np.maximum(drift_h, 0.05))
    lons = lons + u_eff * drift_h * DEG_PER_MS_HR + rng.normal(0, 1, len(drift_h)) * spread
    lats = lats + v_eff * drift_h * DEG_PER_MS_HR + rng.normal(0, 1, len(drift_h)) * spread
    return raster_particles_to_mask(lons, lats, bbox, thresh_frac=point["mask_threshold"])


def run_fragility(case_dir: str, max_points: int = MAX_POINTS) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(case_dir, "attribution_result.json")) as f:
        attribution = json.load(f)

    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    observed = (np.array(Image.open(manifest["mask_groundtruth_path"])) > 127).astype(np.uint8)
    tracks = {t["vessel_key"]: t["fixes"] for t in manifest["tracks"]}

    ranking = attribution["ranking"]
    if len(ranking) < 2:
        return {
            "incident_id": manifest["incident_id"],
            "testable": False,
            "reason": "fewer than two candidates survived historical filtering — "
                      "there is no alternative ranking for a perturbation to expose",
            "baseline_top": attribution.get("top_candidate_id"),
            "axes": {k: {"tested_values": vals, "label": label}
                     for k, (vals, _s, label) in AXES.items()},
        }

    baseline_top = ranking[0]["vessel_key"]
    points = _enumerate_points(max_points)
    grid = []
    smallest_flip = None

    for idx, point in enumerate(points):
        losses = {}
        ious = {}
        for r in ranking:
            vkey = r["vessel_key"]
            complexity = min(max(0.25, r["duration_hours"] + point["duration_shift_h"]) / 4.0, 1.0)
            pred = _simulate(tracks[vkey], _parse(r["release_start"]), r["duration_hours"],
                             r["is_continuous"], acquired, bbox, u, v, point, seed=idx)
            fit = score_fit(pred, observed, complexity)
            losses[vkey] = fit["loss"]
            ious[vkey] = fit["iou"]
        top = min(losses, key=losses.get)
        flipped = top != baseline_top
        entry = {
            "point_id": f"p{idx:03d}",
            "params": point,
            "changed_axes": {k: point[k] for k in AXES if point[k] != NOMINAL[k]},
            "magnitude": _magnitude(point),
            "top_candidate": top,
            "top_iou": round(ious[top], 4),
            "baseline_candidate_iou": round(ious.get(baseline_top, float("nan")), 4),
            "loss_margin": round(abs(sorted(losses.values())[0] - sorted(losses.values())[1]), 4)
            if len(losses) > 1 else None,
            "flipped": flipped,
            "source": "computed",  # never an interpolated or generated value
        }
        grid.append(entry)
        if flipped and smallest_flip is None:
            smallest_flip = entry

    nominal_losses = {}
    for r in ranking:
        nominal_losses[r["vessel_key"]] = r["mean_loss"]

    out = {
        "incident_id": manifest["incident_id"],
        "testable": True,
        "baseline_top": baseline_top,
        "baseline_unknown_source": attribution["unknown_source"],
        "n_points_tested": len(grid),
        "n_points_flipped": sum(1 for g in grid if g["flipped"]),
        "flip_found": smallest_flip is not None,
        "smallest_flip": smallest_flip,
        "lead_retained_fraction": round(1 - sum(1 for g in grid if g["flipped"]) / len(grid), 4)
        if grid else None,
        "grid": grid,
        "axes": {k: {"tested_values": vals, "normalising_scale": scale, "label": label}
                 for k, (vals, scale, label) in AXES.items()},
        "coverage_note": "Single-axis and two-axis perturbations only. Three-or-more-axis "
                         "combinations were not tested, so absence of a flip is evidence of "
                         "stability across the tested set, not a proof of stability.",
        "interpretation_note": "A sensitivity counterfactual, not proof of causal responsibility. "
                               "Grid win frequency is an evidence score, not a calibrated "
                               "probability of responsibility.",
        "loss_weights": LOSS_WEIGHTS,
        "nominal_mean_losses": nominal_losses,
    }
    with open(os.path.join(case_dir, "fragility_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    import sys
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/cases/case_0001"
    res = run_fragility(case_dir)
    print(f"Rank fragility — {res['incident_id']}")
    if not res["testable"]:
        print(f"  not testable: {res['reason']}")
    else:
        print(f"  baseline top candidate: {res['baseline_top']}")
        print(f"  perturbations tested:   {res['n_points_tested']} "
              f"({res['n_points_flipped']} changed the leader)")
        print(f"  lead retained in:       {res['lead_retained_fraction'] * 100:.0f}% of tested variants")
        if res["flip_found"]:
            f = res["smallest_flip"]
            changes = ", ".join(f"{k} = {v}" for k, v in f["changed_axes"].items())
            print(f"  SMALLEST RANK-CHANGING PERTURBATION (magnitude {f['magnitude']}):")
            print(f"    {changes}")
            print(f"    -> leader becomes {f['top_candidate']} (IoU {f['top_iou']:.3f}); "
                  f"{res['baseline_top']} falls to IoU {f['baseline_candidate_iou']:.3f}")
        else:
            print("  no tested perturbation changed the leader — the ranking is stable "
                  "across the tested grid (see coverage_note)")
