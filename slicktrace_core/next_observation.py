"""
Next-observation advisor (masterplan p.12, P1 — pitched as experiment design).

For the two leading hypotheses, find the future times at which their predicted
surface footprints disagree most, and rank those observation windows by
discriminability. The useful framing is not detection but experiment design:
which future evidence would most reduce the ambiguity that currently exists.

Discriminability score
    For a candidate window, simulate both leading hypotheses forward to that
    time and score 1 - IoU(A, B). A score near 0 means the two explanations
    predict the same thing then, so observing then settles nothing. A score
    near 1 means they predict disjoint footprints, so a single observation
    separates them.

    This is a simple disagreement score, which is sufficient for a prototype.
    It is NOT expected information gain — that would require an explicit
    observation likelihood and prior over hypotheses, neither of which is
    modelled here. The field name says `disagreement_score` for that reason.

The interface recommends evidence. It does not task satellites, and it does
not know real acquisition schedules. Where no schedule is available, windows
are labelled hypothetical rather than presented as bookable passes.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import numpy as np

from slicktrace_core.attribution import ENSEMBLE_VARIANTS, simulate_hypothesis
from slicktrace_core.hindcast import _parse

DEFAULT_HORIZONS_H = (3, 6, 9, 12, 18, 24)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    ab, bb = a.astype(bool), b.astype(bool)
    union = np.logical_or(ab, bb).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(ab, bb).sum() / union)


def _disagreement_bbox(a: np.ndarray, b: np.ndarray, bbox: dict, img_size: int):
    diff = np.logical_xor(a.astype(bool), b.astype(bool))
    ys, xs = np.where(diff)
    if len(xs) == 0:
        return None
    lon_min = bbox["min_lon"] + (xs.min() / img_size) * (bbox["max_lon"] - bbox["min_lon"])
    lon_max = bbox["min_lon"] + (xs.max() / img_size) * (bbox["max_lon"] - bbox["min_lon"])
    lat_max = bbox["max_lat"] - (ys.min() / img_size) * (bbox["max_lat"] - bbox["min_lat"])
    lat_min = bbox["max_lat"] - (ys.max() / img_size) * (bbox["max_lat"] - bbox["min_lat"])
    return {"min_lon": round(float(lon_min), 5), "min_lat": round(float(lat_min), 5),
            "max_lon": round(float(lon_max), 5), "max_lat": round(float(lat_max), 5)}


def run_next_observation(case_dir: str, horizons_h=DEFAULT_HORIZONS_H,
                         acquisition_schedule: list[str] | None = None) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(case_dir, "attribution_result.json")) as f:
        attribution = json.load(f)

    ranking = attribution["ranking"]
    if len(ranking) < 2:
        return {
            "incident_id": manifest["incident_id"],
            "applicable": False,
            "reason": "fewer than two candidate hypotheses — there is no ambiguity "
                      "between leading explanations for a further observation to resolve",
        }

    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    img_size = manifest.get("img_size_px", 256)
    tracks = {t["vessel_key"]: t["fixes"] for t in manifest["tracks"]}

    a, b = ranking[0], ranking[1]
    nominal = ENSEMBLE_VARIANTS[0]

    from slicktrace_core.attribution import ReleaseHypothesisSpec

    def spec(r):
        return ReleaseHypothesisSpec(r["candidate_id"], r["vessel_key"],
                                     _parse(r["release_start"]), r["duration_hours"],
                                     r["is_continuous"])

    windows = []
    for h in horizons_h:
        target = acquired + timedelta(hours=h)
        mask_a = simulate_hypothesis(spec(a), tracks[a["vessel_key"]], u, v, nominal,
                                     target, bbox, seed=11)
        mask_b = simulate_hypothesis(spec(b), tracks[b["vessel_key"]], u, v, nominal,
                                     target, bbox, seed=11)
        overlap = _iou(mask_a, mask_b)
        windows.append({
            "horizon_hours": h,
            "valid_utc": target.isoformat(),
            "disagreement_score": round(1.0 - overlap, 4),
            "predicted_overlap_iou": round(overlap, 4),
            "disagreement_bbox": _disagreement_bbox(mask_a, mask_b, bbox, img_size),
            "schedule_status": "hypothetical — no acquisition schedule supplied"
            if not acquisition_schedule else "matched to supplied schedule",
        })

    windows_sorted = sorted(windows, key=lambda w: -w["disagreement_score"])
    best = windows_sorted[0]

    out = {
        "incident_id": manifest["incident_id"],
        "applicable": True,
        "hypothesis_a": {"vessel_key": a["vessel_key"], "candidate_id": a["candidate_id"]},
        "hypothesis_b": {"vessel_key": b["vessel_key"], "candidate_id": b["candidate_id"]},
        "current_ambiguity": {
            "mean_iou_gap": round(a["mean_iou"] - b["mean_iou"], 4),
            "mean_loss_gap": round(b["mean_loss"] - a["mean_loss"], 4),
        },
        "windows": windows,
        "recommended_window": best,
        "method_note": "Simple footprint-disagreement score between the two leading "
                       "hypotheses under the nominal forcing variant. Not expected "
                       "information gain: no observation likelihood and no prior over "
                       "hypotheses are modelled.",
        "scope_note": "The system recommends which evidence would be informative. It does "
                      "not task satellites and does not assert that an acquisition is "
                      "available in the recommended window.",
    }
    with open(os.path.join(case_dir, "next_observation_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


def validate_with_held_out_observation(case_dir: str) -> dict:
    """Dev/validation only (reads truth.json).

    Does observing at the recommended window actually separate the two leading
    candidates better than observing at the worst-ranked window? Simulate the
    TRUE release forward to each window, score both hypotheses against it, and
    compare the resulting separation. This is the test that keeps the advisor
    from being an untested plausible-sounding feature.
    """
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(case_dir, "truth.json")) as f:
        truth = json.load(f)
    nxt_path = os.path.join(case_dir, "next_observation_result.json")
    if not os.path.exists(nxt_path):
        run_next_observation(case_dir)
    with open(nxt_path) as f:
        nxt = json.load(f)
    if not nxt.get("applicable"):
        return {"incident_id": manifest["incident_id"], "applicable": False,
                "reason": nxt.get("reason")}

    true_key = truth.get("true_vessel_key")
    if true_key is None:
        return {"incident_id": manifest["incident_id"], "applicable": False,
                "reason": "absent-source case: there is no true vessel track to "
                          "generate a held-out observation from"}

    with open(os.path.join(case_dir, "attribution_result.json")) as f:
        attribution = json.load(f)
    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    tracks = {t["vessel_key"]: t["fixes"] for t in manifest["tracks"]}
    nominal = ENSEMBLE_VARIANTS[0]

    from slicktrace_core.attribution import ReleaseHypothesisSpec

    def spec(r):
        return ReleaseHypothesisSpec(r["candidate_id"], r["vessel_key"],
                                     _parse(r["release_start"]), r["duration_hours"],
                                     r["is_continuous"])

    a, b = attribution["ranking"][0], attribution["ranking"][1]
    truth_spec = ReleaseHypothesisSpec("truth", true_key,
                                       _parse(truth["release_start_utc"]),
                                       truth["release_duration_hours"],
                                       truth["is_continuous"])

    def separation_at(h):
        target = acquired + timedelta(hours=h)
        observed = simulate_hypothesis(truth_spec, tracks[true_key], u, v, nominal,
                                       target, bbox, seed=99)
        ma = simulate_hypothesis(spec(a), tracks[a["vessel_key"]], u, v, nominal, target, bbox, seed=11)
        mb = simulate_hypothesis(spec(b), tracks[b["vessel_key"]], u, v, nominal, target, bbox, seed=11)
        return _iou(ma, observed) - _iou(mb, observed)

    best_h = nxt["recommended_window"]["horizon_hours"]
    worst = min(nxt["windows"], key=lambda w: w["disagreement_score"])
    sep_best = separation_at(best_h)
    sep_worst = separation_at(worst["horizon_hours"])

    return {
        "incident_id": manifest["incident_id"],
        "applicable": True,
        "recommended_horizon_h": best_h,
        "least_informative_horizon_h": worst["horizon_hours"],
        "separation_at_recommended": round(sep_best, 4),
        "separation_at_least_informative": round(sep_worst, 4),
        "recommendation_helped": bool(sep_best > sep_worst),
        "note": "Separation is IoU(leading hypothesis, held-out observation) minus "
                "IoU(runner-up, held-out observation). Larger is better. A single "
                "synthetic held-out observation per case is a weak test and is "
                "reported per case rather than averaged into a headline number.",
    }


if __name__ == "__main__":
    import sys
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/cases/case_0001"
    res = run_next_observation(case_dir)
    print(f"Next-observation advisor — {res['incident_id']}")
    if not res.get("applicable"):
        print(f"  not applicable: {res['reason']}")
    else:
        print(f"  comparing {res['hypothesis_a']['vessel_key']} vs "
              f"{res['hypothesis_b']['vessel_key']}")
        for w in res["windows"]:
            print(f"    +{w['horizon_hours']:>2}h  disagreement {w['disagreement_score']:.3f}  "
                  f"(predicted overlap IoU {w['predicted_overlap_iou']:.3f})")
        r = res["recommended_window"]
        print(f"  -> most informative tested window: +{r['horizon_hours']}h "
              f"({r['schedule_status']})")
        v = validate_with_held_out_observation(case_dir)
        if v.get("applicable"):
            print(f"  held-out check: separation {v['separation_at_recommended']:.3f} at "
                  f"+{v['recommended_horizon_h']}h vs {v['separation_at_least_informative']:.3f} "
                  f"at +{v['least_informative_horizon_h']}h -> "
                  f"{'helped' if v['recommendation_helped'] else 'did not help'}")
