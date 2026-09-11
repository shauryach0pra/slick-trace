"""
Forward-replay attribution engine (masterplan p.10 — the central
differentiator). Operates on the candidates surviving historical filtering
(varuna_core.hindcast), NOT the full vessel list.

Pipeline per candidate vessel:
  1. Sample release hypotheses: several plausible (release_start, duration,
     pulse-vs-continuous) combinations along the vessel's own track.
  2. For each hypothesis, run forward twins under a SHARED ensemble of
     wind/current + diffusivity perturbations (same perturbation set used
     for every candidate — an unfair advantage to one candidate from a
     mismatched ensemble would invalidate the comparison).
  3. Rasterize each simulated footprint the same way the "observed" mask
     was made, and score fit: IoU, boundary distance, area error, plus a
     complexity penalty for longer/continuous releases (Occam).
  4. Aggregate per candidate (best hypothesis by mean ensemble loss), rank,
     and only name a top candidate if it clears an absolute fit gate —
     otherwise report unknown_source explicitly rather than forcing a pick.

Also implements a NAIVE baseline (nearest vessel to the slick at/near
observation time) run over the FULL, unfiltered vessel list — this is the
thing the masterplan requires beating (p.4, p.15), and case_0001 is
specifically constructed so the naive baseline falls for the decoy trap.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt

from varuna_core.hindcast import _interp_track_position, _parse, DEG_PER_MS_HR

IMG_SIZE = 256

# Shared across every candidate/hypothesis — required for a fair comparison.
ENSEMBLE_VARIANTS = [
    {"name": "nominal", "du": 0.0, "dv": 0.0, "diffusivity_scale": 1.0},
    {"name": "current+20pct", "du": 0.03, "dv": 0.0, "diffusivity_scale": 1.0},
    {"name": "current-20pct", "du": -0.03, "dv": 0.0, "diffusivity_scale": 1.0},
    {"name": "cross-current+", "du": 0.0, "dv": 0.03, "diffusivity_scale": 1.0},
    {"name": "cross-current-", "du": 0.0, "dv": -0.03, "diffusivity_scale": 1.0},
    {"name": "high-diffusivity", "du": 0.0, "dv": 0.0, "diffusivity_scale": 1.8},
]

LOSS_WEIGHTS = dict(a_iou=0.5, b_boundary=0.2, c_area=0.2, d_complexity=0.1)
ABSTENTION_IOU_GATE = 0.30  # below this, refuse to name a top candidate


@dataclass
class ReleaseHypothesisSpec:
    candidate_id: str
    vessel_key: str
    release_start: datetime
    duration_hours: float
    is_continuous: bool


@dataclass
class HypothesisResult:
    candidate_id: str
    vessel_key: str
    release_start: str
    duration_hours: float
    is_continuous: bool
    mean_iou: float
    mean_loss: float
    ensemble_win_count: int  # how many of N ensemble variants this was the best candidate for
    n_ensemble: int


def lonlat_to_px(lon_arr, lat_arr, bbox, img_size=IMG_SIZE):
    xs = ((lon_arr - bbox["min_lon"]) / (bbox["max_lon"] - bbox["min_lon"]) * img_size).astype(int)
    ys = ((bbox["max_lat"] - lat_arr) / (bbox["max_lat"] - bbox["min_lat"]) * img_size).astype(int)
    return np.clip(xs, 0, img_size - 1), np.clip(ys, 0, img_size - 1)


def raster_particles_to_mask(lon, lat, bbox, img_size=IMG_SIZE, sigma=3, thresh_frac=0.15):
    mask = np.zeros((img_size, img_size), dtype=np.uint8)
    xs, ys = lonlat_to_px(lon, lat, bbox, img_size)
    mask[ys, xs] = 1
    blurred = gaussian_filter(mask.astype(float), sigma=sigma)
    if blurred.max() == 0:
        return blurred.astype(np.uint8)
    return (blurred > blurred.max() * thresh_frac).astype(np.uint8)


def sample_release_hypotheses(vessel_key: str, fixes: list[dict], acquired: datetime,
                                n_start_samples: int = 3) -> list[ReleaseHypothesisSpec]:
    """Sample release_start options spread across the vessel's own observed
    track window (bounded by its actual fixes — no extrapolation), crossed
    with duration options covering both a short pulse and continuous
    moving discharges."""
    times = [_parse(f["t_utc"]) for f in fixes]
    if not times:
        return []
    t_min, t_max = min(times), max(times)
    # only consider start times that leave the vessel time to still be
    # "before" acquisition (a release can't start after the image)
    t_max_valid = min(t_max, acquired)
    if t_min >= t_max_valid:
        return []
    starts = np.linspace(0, 1, n_start_samples)
    hyps = []
    for frac in starts:
        start_t = t_min + (t_max_valid - t_min) * frac
        for duration, continuous in [(0.5, False), (2.0, True), (4.0, True)]:
            hyps.append(ReleaseHypothesisSpec(
                candidate_id=f"{vessel_key}_{start_t.strftime('%H%M')}_{duration}h",
                vessel_key=vessel_key, release_start=start_t,
                duration_hours=duration, is_continuous=continuous,
            ))
    return hyps


def simulate_hypothesis(hyp: ReleaseHypothesisSpec, fixes: list[dict], u: float, v: float,
                         variant: dict, acquired: datetime, bbox: dict,
                         n_particles: int = 250, seed: int = 0) -> np.ndarray:
    """Forward-advect particles released along the vessel's track (or at a
    single point for a pulse) from release_start to acquired, under the
    forcing field plus this ensemble variant's perturbation."""
    rng = np.random.default_rng(seed)
    u_eff, v_eff = u + variant["du"], v + variant["dv"]
    diffusivity_base = 0.020 * variant["diffusivity_scale"]  # matches synth_generator's true-data physics

    release_offsets_hr = (rng.uniform(0, hyp.duration_hours, n_particles)
                           if hyp.is_continuous else np.zeros(n_particles))
    lons = np.zeros(n_particles)
    lats = np.zeros(n_particles)
    for i, off_hr in enumerate(release_offsets_hr):
        t_release_i = hyp.release_start + timedelta(hours=float(off_hr))
        pos = _interp_track_position(fixes, t_release_i)
        if pos is None:
            # fall back to nearest endpoint if slightly outside due to rounding
            pos = _interp_track_position(fixes, hyp.release_start)
            if pos is None:
                pos = (fixes[0]["lon"], fixes[0]["lat"])
        lons[i], lats[i] = pos

    drift_hours = np.array([(acquired - (hyp.release_start + timedelta(hours=float(o)))).total_seconds() / 3600
                             for o in release_offsets_hr])
    drift_hours = np.clip(drift_hours, 0, None)
    spread = diffusivity_base * np.sqrt(np.maximum(drift_hours, 0.05))  # grows with elapsed drift time

    lons = lons + u_eff * drift_hours * DEG_PER_MS_HR + rng.normal(0, 1, len(drift_hours)) * spread
    lats = lats + v_eff * drift_hours * DEG_PER_MS_HR + rng.normal(0, 1, len(drift_hours)) * spread

    return raster_particles_to_mask(lons, lats, bbox)


def _boundary_distance(pred: np.ndarray, truth: np.ndarray) -> float:
    """Symmetric surface distance approximation (pixel units): average, over
    disagreement pixels on each side, of distance to the nearest pixel of
    the other mask."""
    if pred.sum() == 0 and truth.sum() == 0:
        return 0.0
    if pred.sum() == 0 or truth.sum() == 0:
        return float(max(pred.shape))  # maximal penalty, no overlap possible
    dist_to_truth = distance_transform_edt(1 - truth)
    dist_to_pred = distance_transform_edt(1 - pred)
    fp = (pred == 1) & (truth == 0)
    fn = (truth == 1) & (pred == 0)
    vals = []
    if fp.any():
        vals.append(dist_to_truth[fp].mean())
    if fn.any():
        vals.append(dist_to_pred[fn].mean())
    return float(np.mean(vals)) if vals else 0.0


def score_fit(pred: np.ndarray, truth: np.ndarray, complexity_penalty: float) -> dict:
    pred_b, truth_b = pred.astype(bool), truth.astype(bool)
    inter = np.logical_and(pred_b, truth_b).sum()
    union = np.logical_or(pred_b, truth_b).sum()
    iou = float(inter / union) if union > 0 else (1.0 if pred_b.sum() == truth_b.sum() == 0 else 0.0)
    boundary = _boundary_distance(pred, truth) / max(pred.shape)  # normalize to [0,~1]
    area_err = (abs(pred_b.sum() - truth_b.sum()) / truth_b.sum()) if truth_b.sum() > 0 else float(pred_b.sum() > 0)
    area_err = min(area_err, 3.0) / 3.0  # cap + normalize
    w = LOSS_WEIGHTS
    loss = (w["a_iou"] * (1 - iou) + w["b_boundary"] * boundary
            + w["c_area"] * area_err + w["d_complexity"] * complexity_penalty)
    return {"iou": iou, "boundary_distance_norm": boundary, "relative_area_error_norm": area_err, "loss": loss}


def run_attribution(case_dir: str, candidate_vessel_keys: list[str] | None = None) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    observed_mask = (np.array(Image.open(manifest["mask_groundtruth_path"])) > 127).astype(np.uint8)

    if candidate_vessel_keys is None:
        hm_path = os.path.join(case_dir, "historical_mapping.json")
        with open(hm_path) as f:
            hm = json.load(f)
        candidate_vessel_keys = [a["vessel_key"] for a in hm["assessments"] if a["status"] == "candidate"]

    tracks_by_key = {tr["vessel_key"]: tr["fixes"] for tr in manifest["tracks"]}

    per_candidate_best: dict[str, HypothesisResult] = {}
    all_hypothesis_results: list[HypothesisResult] = []

    for vkey in candidate_vessel_keys:
        fixes = tracks_by_key[vkey]
        hyps = sample_release_hypotheses(vkey, fixes, acquired)
        best_for_vessel = None
        for hyp in hyps:
            complexity_penalty = min(hyp.duration_hours / 4.0, 1.0)
            ious, losses = [], []
            for vi, variant in enumerate(ENSEMBLE_VARIANTS):
                pred = simulate_hypothesis(hyp, fixes, u, v, variant, acquired, bbox, seed=vi)
                fit = score_fit(pred, observed_mask, complexity_penalty)
                ious.append(fit["iou"])
                losses.append(fit["loss"])
            result = HypothesisResult(
                candidate_id=hyp.candidate_id, vessel_key=vkey,
                release_start=hyp.release_start.isoformat(), duration_hours=hyp.duration_hours,
                is_continuous=hyp.is_continuous, mean_iou=float(np.mean(ious)),
                mean_loss=float(np.mean(losses)), ensemble_win_count=0, n_ensemble=len(ENSEMBLE_VARIANTS),
            )
            all_hypothesis_results.append(result)
            if best_for_vessel is None or result.mean_loss < best_for_vessel.mean_loss:
                best_for_vessel = result
        if best_for_vessel is not None:
            per_candidate_best[vkey] = best_for_vessel

    # ensemble win counts: for each variant, which candidate's BEST hypothesis wins
    for vi, variant in enumerate(ENSEMBLE_VARIANTS):
        variant_losses = {}
        for vkey in candidate_vessel_keys:
            fixes = tracks_by_key[vkey]
            best = per_candidate_best.get(vkey)
            if best is None:
                continue
            # re-simulate best hypothesis under this specific variant for the win tally
            hyp = ReleaseHypothesisSpec(best.candidate_id, vkey, _parse(best.release_start),
                                          best.duration_hours, best.is_continuous)
            complexity_penalty = min(hyp.duration_hours / 4.0, 1.0)
            pred = simulate_hypothesis(hyp, fixes, u, v, variant, acquired, bbox, seed=vi)
            fit = score_fit(pred, observed_mask, complexity_penalty)
            variant_losses[vkey] = fit["loss"]
        if variant_losses:
            winner = min(variant_losses, key=variant_losses.get)
            per_candidate_best[winner].ensemble_win_count += 1

    ranking = sorted(per_candidate_best.values(), key=lambda r: r.mean_loss)
    top = ranking[0] if ranking else None
    unknown_source = (top is None) or (top.mean_iou < ABSTENTION_IOU_GATE)

    out = {
        "incident_id": manifest["incident_id"],
        "candidates_considered": candidate_vessel_keys,
        "ranking": [r.__dict__ for r in ranking],
        "top_candidate_id": None if unknown_source else top.vessel_key,
        "unknown_source": unknown_source,
        "abstention_iou_gate": ABSTENTION_IOU_GATE,
        "loss_weights": LOSS_WEIGHTS,
        "n_ensemble_variants": len(ENSEMBLE_VARIANTS),
    }
    with open(os.path.join(case_dir, "attribution_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


def run_naive_baseline(case_dir: str) -> dict:
    """Nearest-vessel-at-observation-time heuristic, run over the FULL,
    unfiltered vessel list. This is the thing the pipeline must beat."""
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    observed_mask = (np.array(Image.open(manifest["mask_groundtruth_path"])) > 127).astype(np.uint8)
    ys, xs = np.where(observed_mask)
    bbox = manifest["bbox"]
    centroid_lon = bbox["min_lon"] + (xs.mean() / IMG_SIZE) * (bbox["max_lon"] - bbox["min_lon"])
    centroid_lat = bbox["max_lat"] - (ys.mean() / IMG_SIZE) * (bbox["max_lat"] - bbox["min_lat"])
    acquired = _parse(manifest["acquired_utc"])

    scored = []
    for tr in manifest["tracks"]:
        fixes = tr["fixes"]
        times = [_parse(f["t_utc"]) for f in fixes]
        # nearest-at-observation: use position at acquisition time if available,
        # else the single closest-in-time fix (still "near observation", the
        # naive real-world shortcut of "whichever ship was closest when we saw it")
        pos = _interp_track_position(fixes, acquired)
        if pos is None:
            closest_fix = min(fixes, key=lambda f: abs((_parse(f["t_utc"]) - acquired).total_seconds()))
            pos = (closest_fix["lon"], closest_fix["lat"])
        dist = float(np.hypot(pos[0] - centroid_lon, pos[1] - centroid_lat))
        scored.append({"vessel_key": tr["vessel_key"], "distance_deg": dist})

    scored.sort(key=lambda s: s["distance_deg"])
    out = {"incident_id": manifest["incident_id"], "method": "naive_nearest_at_observation",
           "ranking": scored, "top_candidate_id": scored[0]["vessel_key"] if scored else None}
    with open(os.path.join(case_dir, "naive_baseline_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    case_dir = "data/cases/case_0001"
    baseline = run_naive_baseline(case_dir)
    print("=== Naive historical-proximity baseline (full vessel list) ===")
    for r in baseline["ranking"]:
        print(f"  {r['vessel_key']:16s} distance={r['distance_deg']:.4f} deg")
    print(f"  -> naive top pick: {baseline['top_candidate_id']}\n")

    attribution = run_attribution(case_dir)
    print(f"=== Forward-replay attribution (candidates from historical filtering) ===")
    for r in attribution["ranking"]:
        print(f"  {r['vessel_key']:16s} mean_iou={r['mean_iou']:.3f}  mean_loss={r['mean_loss']:.4f}  "
              f"won {r['ensemble_win_count']}/{r['n_ensemble']} ensemble variants  "
              f"(release {r['duration_hours']}h {'continuous' if r['is_continuous'] else 'pulse'})")
    if attribution["unknown_source"]:
        print("  -> UNKNOWN SOURCE (no candidate cleared the absolute fit gate)")
    else:
        print(f"  -> top candidate: {attribution['top_candidate_id']}")
