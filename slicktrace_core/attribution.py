"""
Forward-replay attribution engine (masterplan p.10 — the central
differentiator). Operates on the candidates surviving historical filtering
(slicktrace_core.hindcast), NOT the full vessel list.

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

from slicktrace_core.hindcast import _interp_track_position, _parse, DEG_PER_MS_HR

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


# Release start times are tried every hour across the vessel's own observed
# window. A fixed COUNT of starts (three: the window's start, middle and end)
# made the time resolution depend on how long a track happened to be; with
# full-day tracks that meant starts 12 h apart, so a release 6 h before the
# image was never tried. A fixed step gives every vessel the same resolution.
RELEASE_START_STEP_H = 1.0


def sample_release_hypotheses(vessel_key: str, fixes: list[dict], acquired: datetime,
                                step_hours: float = RELEASE_START_STEP_H) -> list[ReleaseHypothesisSpec]:
    """Release start times every `step_hours` across the vessel's own observed
    track window (bounded by its actual fixes - no extrapolation), crossed
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
    step = timedelta(hours=step_hours)
    n = int((t_max_valid - t_min) / step)
    starts = [t_min + k * step for k in range(n + 1)]
    if starts[-1] < t_max_valid:
        starts.append(t_max_valid)
    hyps = []
    for start_t in starts:
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


# Below this loss gap the top two candidates are not meaningfully separated and
# the ranking should not be read as a preference. Chosen as a guard rather than
# tuned: named cases here separate by 0.15-0.34, abstained cases by 0.004-0.006,
# so 0.05 sits in the empty band between them and trips on neither today.
def _release_age(case_dir: str, manifest: dict, top: dict | None,
                 unknown_source: bool = False) -> dict:
    """Age of the slick, as a bounded interval derived from transport.

    The problem statement asks for age "if feasible". From a single scene it is
    not feasible in the usual sense: slick area depends on volume, oil
    properties and forcing, none of which is known here, so a Fay spreading
    calculation would produce a number with unstated uncertainty spanning
    orders of magnitude. That route is deliberately not taken.

    What the reconstruction does support is a release-time interval. The
    hindcast records the hours-before-acquisition at which each candidate was
    inside the backward origin envelope. For the leading candidate, the earliest
    and latest such hour bound when a release from that vessel could have
    started and still explain the observation. The point estimate is the
    best-fitting release in the hypothesis search.

    The confidence field cannot express high, by construction. The interval
    comes from a transport model over synthetic forcing, bounded by a
    hypothesis grid of finite resolution, and both bounds are as uncertain as
    the envelope that produced them.
    """
    from datetime import datetime
    import json as _json, os as _os

    out = {
        "estimable": False, "hours": None, "hours_low": None, "hours_high": None,
        "confidence": "unavailable", "method": None, "caveat": None,
    }
    if top is None or unknown_source:
        out["caveat"] = ("no candidate cleared the absolute fit gate, so there is no "
                         "release to date. An age derived from a candidate the system "
                         "declined to endorse would contradict the abstention that "
                         "produced it: the slick exists, its origin does not resolve, "
                         "and neither does its age.")
        return out

    try:
        acq = datetime.fromisoformat(manifest["acquired_utc"])
        rel = datetime.fromisoformat(str(top["release_start"]))
        hm = _json.load(open(_os.path.join(case_dir, "historical_mapping.json")))
    except Exception:
        return out

    hours = (acq - rel).total_seconds() / 3600.0
    inside = next((x.get("inside_at") or [] for x in hm.get("assessments", [])
                   if x["vessel_key"] == top["vessel_key"]), [])

    out.update({
        "estimable": True,
        "hours": round(hours, 2),
        "hours_low": round(min(inside), 2) if inside else None,
        "hours_high": round(max(inside), 2) if inside else None,
        "confidence": "low",
        "method": ("release time from the best-fitting forward-replay hypothesis; "
                   "interval from the hours at which this vessel was inside the "
                   "backward origin envelope"),
        "caveat": ("Not derived from slick appearance. Area-based age needs volume, "
                   "oil properties and forcing that a single scene does not supply, "
                   "so no Fay spreading estimate is made. The interval is as "
                   "uncertain as the envelope it comes from, and the hypothesis "
                   "grid it is drawn from has finite time resolution. Confidence "
                   "cannot be higher than low here and the field cannot express it."),
    })
    return out


def _named_factors(case_dir: str, ranked: list[dict]) -> dict:
    """Report proximity, trajectory and physical fit separately per candidate.

    The problem statement names proximity, trajectory and behavioural anomalies
    as aspects on which suspects should be scored. This system ranks on physical
    fit alone - whether a replayed release from that vessel reproduces the
    observed slick - and the other two are reported beside it rather than folded
    into it. Three reasons to separate them rather than sum them:

      Proximity is the baseline this method is measured against. Mixing it into
      the score would make the comparison circular.

      Trajectory here means envelope dwell: how much of the backward origin
      window the vessel spent inside it. Forward replay already uses the
      vessel's path implicitly, so adding dwell as a weighted term would count
      the same evidence twice.

      Behavioural anomalies are deliberately absent. A transponder gap raises no
      score here - three repositories in this problem statement's public field
      treat going dark as evidence of guilt, and it is not.

    Reported so a reader can see what each factor says and observe where they
    disagree. Only physical fit orders the ranking.
    """
    import json as _json, os as _os
    prox, dwell = {}, {}
    try:
        nb = _json.load(open(_os.path.join(case_dir, "naive_baseline_result.json")))
        prox = {r["vessel_key"]: r["distance_deg"] for r in nb.get("ranking", [])}
    except Exception:
        pass
    try:
        hm = _json.load(open(_os.path.join(case_dir, "historical_mapping.json")))
        for x in hm.get("assessments", []):
            dwell[x["vessel_key"]] = len(x.get("inside_at") or [])
    except Exception:
        pass

    rows = []
    for r in ranked:
        vk = r["vessel_key"]
        rows.append({
            "vessel_key": vk,
            # Rounded: this is copied from the naive baseline, where it is a
            # haversine result that differs at the last representable digit
            # between x86-64 and arm64 (see A19). Six decimals is ~0.1 m, far
            # below any distance this quantity is used to reason about, and it
            # keeps the artifact byte-identical across platforms.
            "proximity_deg_at_acquisition": (None if prox.get(vk) is None
                                             else round(prox[vk], 6)),
            "trajectory_envelope_dwell": dwell.get(vk),
            "physical_fit_mean_iou": round(r["mean_iou"], 4),
            "physical_fit_mean_loss": round(r["mean_loss"], 4),
        })
    return {
        "factors": rows,
        "ranked_on": "physical_fit_mean_loss",
        "note": ("Proximity and trajectory are reported, not scored. Only physical "
                 "fit orders the ranking; folding proximity in would make the "
                 "baseline comparison circular, and folding dwell in would count "
                 "the vessel's path twice."),
        "behavioural_anomalies": ("not scored. A transponder gap does not raise a "
                                  "candidate's score - missing evidence is recorded "
                                  "as unassessed, never as culpability."),
    }


DISCRIMINATION_LOSS_TOLERANCE = 0.05


def _discrimination(ranked: list[dict]) -> dict:
    """Is the ranking actually separating the top two candidates?

    Distinct from the absolute fit gate, which asks whether the best candidate
    explains the observation at all. This asks whether the second-best explains
    it about as well - a ranking can clear the gate and still be a coin toss.
    Reported always, so the margin is visible rather than inferred, and never
    used to raise confidence in a result: it can only qualify one.
    """
    if len(ranked) < 2:
        return {"discriminated": None, "loss_gap": None, "iou_gap": None,
                "tolerance": DISCRIMINATION_LOSS_TOLERANCE,
                "note": "fewer than two candidates - nothing to discriminate between"}
    loss_gap = ranked[1]["mean_loss"] - ranked[0]["mean_loss"]
    iou_gap = ranked[0]["mean_iou"] - ranked[1]["mean_iou"]
    ok = loss_gap >= DISCRIMINATION_LOSS_TOLERANCE
    note = ("top two candidates separated on the ranking criterion" if ok else
            "top two candidates are not separated - the ordering between them "
            "carries no weight and should not be read as a preference")
    if iou_gap < 0:
        note += ("; ranking by loss disagrees with ranking by IoU here, which is "
                 "itself a sign the case is unresolved")
    return {"discriminated": ok, "loss_gap": round(loss_gap, 4),
            "iou_gap": round(iou_gap, 4),
            "tolerance": DISCRIMINATION_LOSS_TOLERANCE, "note": note}


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
        "discrimination": _discrimination([r.__dict__ for r in ranking]),
        "named_factors": _named_factors(case_dir, [r.__dict__ for r in ranking]),
        "release_age": _release_age(case_dir, manifest, top.__dict__ if top else None,
                                    unknown_source),
        "loss_weights": LOSS_WEIGHTS,
        "n_ensemble_variants": len(ENSEMBLE_VARIANTS),
    }
    with open(os.path.join(case_dir, "attribution_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    # The footprint each ranked candidate's best hypothesis draws under the
    # nominal forcing member, rasterised exactly as scored, for the map.
    from slicktrace_core.display_geometry import write_replay_footprints
    write_replay_footprints(case_dir, manifest, out["ranking"], tracks_by_key, u, v,
                            acquired, bbox, observed_mask)
    # The same run, hour by hour, for the leading candidate of a named case.
    from slicktrace_core.replay_timeline import write_replay_timeline
    write_replay_timeline(case_dir, manifest, out, tracks_by_key, u, v)
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
