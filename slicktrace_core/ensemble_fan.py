"""
The ensemble fan: each ranked candidate's best-fitting release, replayed under
all six forcing variants - the same runs attribution scored.

Forward replay does not trust a single current. It scores every release under
six forcing variants (nominal, the current 20% faster and slower, pushed across
itself either way, and faster spreading) and averages the fit. This artifact
records, for every ranked candidate, what each of those six runs did: the drift
path of its released oil from the release to the image, its fit (IoU) and loss,
and whether that candidate won that variant. It is the same computation as
attribution - the same variants, the same seed for each (its index), the same
scoring - so its per-candidate mean IoU and win count reproduce
attribution_result.json exactly, which a test checks.

It also records the forcing itself: the model advects with ONE uniform current,
u and v, the same everywhere. There is no wind in these inputs, and the spatial
variation the generator applies is deliberately not given to the model.
"""
from __future__ import annotations

import json
import math
import os
from datetime import timedelta

import numpy as np

from slicktrace_core.hindcast import _parse
from slicktrace_core.replay_timeline import replay_particles

DECIMALS = 5


def _r(x: float) -> float:
    return round(float(x), DECIMALS)


def build_ensemble_fan(manifest: dict, attribution: dict, tracks_by_key: dict, u: float, v: float,
                       observed_mask: np.ndarray) -> dict:
    from slicktrace_core.attribution import (ENSEMBLE_VARIANTS, ReleaseHypothesisSpec,
                                             raster_particles_to_mask, score_fit)
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    ranking = attribution.get("ranking") or []

    # every member of every ranked candidate: path, fit, loss
    runs = {}
    for r in ranking:
        fixes = tracks_by_key[r["vessel_key"]]
        hyp = ReleaseHypothesisSpec(r["candidate_id"], r["vessel_key"], _parse(r["release_start"]),
                                    r["duration_hours"], r["is_continuous"])
        penalty = min(hyp.duration_hours / 4.0, 1.0)
        first = math.ceil((hyp.release_start - acquired).total_seconds() / 3600)   # first whole hour after release
        members = []
        for vi, variant in enumerate(ENSEMBLE_VARIANTS):
            path = []
            for h in range(first, 1):
                when = acquired + timedelta(hours=h)
                lon, lat, rel = replay_particles(hyp, fixes, u, v, variant, acquired, when, seed=vi)
                if rel.any():
                    path.append([_r(lon[rel].mean()), _r(lat[rel].mean())])
            lon, lat, _ = replay_particles(hyp, fixes, u, v, variant, acquired, acquired, seed=vi)
            fit = score_fit(raster_particles_to_mask(lon, lat, bbox), observed_mask, penalty)
            members.append({"variant": variant["name"], "iou": round(float(fit["iou"]), 4),
                            "loss": float(fit["loss"]), "path": path})
        runs[r["vessel_key"]] = members

    # which candidate wins each variant: lowest loss, as attribution tallies it
    for vi in range(len(ENSEMBLE_VARIANTS)):
        losses = {k: m[vi]["loss"] for k, m in runs.items()}
        winner = min(losses, key=losses.get) if losses else None
        for k, m in runs.items():
            m[vi]["won"] = k == winner

    candidates = []
    for r in ranking:
        members = runs[r["vessel_key"]]
        candidates.append({
            "vessel_key": r["vessel_key"], "candidate_id": r["candidate_id"],
            "mean_iou": round(float(np.mean([m["iou"] for m in members])), 4),
            "ensemble_win_count": sum(m["won"] for m in members),
            "members": [{**m, "loss": round(m["loss"], 4)} for m in members],
        })
    return {
        "incident_id": manifest["incident_id"],
        "named": not attribution.get("unknown_source"),
        "top_candidate_id": attribution.get("top_candidate_id"),
        "forcing": {
            "u_ms": u, "v_ms": v,
            "description": ("One uniform current, the same everywhere, that the attribution model advects "
                            "with; the six variants perturb it. No wind is in these inputs, and the spatial "
                            "variation the generator applies is not given to the model."),
            "variants": [{"name": x["name"], "du_ms": x["du"], "dv_ms": x["dv"],
                          "diffusivity_scale": x["diffusivity_scale"]} for x in ENSEMBLE_VARIANTS],
        },
        "coordinate_decimals": DECIMALS,
        "candidates": candidates,
        "note": ("Each candidate's best-fitting release under each of the six forcing variants, the runs "
                 "attribution scored: a member's path is the centre of its released oil each hour from the "
                 "release to the image. Mean IoU and win count reproduce attribution_result.json. Modelled "
                 "drift, not observed tracks."),
    }


def write_ensemble_fan(case_dir, manifest, attribution, tracks_by_key, u, v, observed_mask) -> dict:
    out = build_ensemble_fan(manifest, attribution, tracks_by_key, u, v, observed_mask)
    with open(os.path.join(case_dir, "ensemble_fan.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    return out
