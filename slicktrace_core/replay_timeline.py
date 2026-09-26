"""
Hourly frames of the leading candidate's replayed release, for the map.

Forward replay scores each release hypothesis by drifting particles from the
vessel's track to the image time and comparing the footprint with the observed
slick. Each particle leaves the ship at a random moment in the release window
and then moves as

    position(T) = release point + current * (T - t_release) + z * spread(T - t_release)

with its random direction z drawn once. So a particle's path over time is one
smooth curve, and the frame at the image time IS the footprint attribution
scored. These frames are that run - nominal forcing, seed 0, the same draws in
the same order as attribution.simulate_hypothesis - evaluated at each whole
hour between the release and the image. Nothing is interpolated or re-run with
different randomness, and a test checks that the last frame rasterises to the
scored footprint pixel for pixel.

Only a NAMED leading candidate is animated. On an abstention the analysis named
no one, and animating the best-scoring hypothesis anyway would draw an
attribution the analysis refused to make.
"""
from __future__ import annotations

import json
import math
import os
from datetime import timedelta

import numpy as np

from slicktrace_core.hindcast import DEG_PER_MS_HR, _interp_track_position, _parse

DECIMALS = 5
HOURS_BACK = 24


def _r(x: float) -> float:
    return round(float(x), DECIMALS)


def replay_particles(hyp, fixes, u, v, variant, acquired, when, n_particles=250, seed=0):
    """Particle positions of one scored hypothesis at time `when`.

    Returns (lon, lat, released) for all n_particles; particles whose release
    moment is after `when` are still aboard (released False). At when == the
    image time this reproduces attribution.simulate_hypothesis exactly.
    """
    rng = np.random.default_rng(seed)
    u_eff, v_eff = u + variant["du"], v + variant["dv"]
    base = 0.020 * variant["diffusivity_scale"]
    offsets = (rng.uniform(0, hyp.duration_hours, n_particles)
               if hyp.is_continuous else np.zeros(n_particles))
    lon0 = np.zeros(n_particles)
    lat0 = np.zeros(n_particles)
    for i, off in enumerate(offsets):
        pos = _interp_track_position(fixes, hyp.release_start + timedelta(hours=float(off)))
        if pos is None:
            pos = _interp_track_position(fixes, hyp.release_start)
            if pos is None:
                pos = (fixes[0]["lon"], fixes[0]["lat"])
        lon0[i], lat0[i] = pos
    z_lon = rng.normal(0, 1, n_particles)
    z_lat = rng.normal(0, 1, n_particles)

    t_rel = np.array([(hyp.release_start + timedelta(hours=float(o)) - acquired).total_seconds() / 3600
                      for o in offsets])
    t_now = (when - acquired).total_seconds() / 3600
    drift = np.clip(t_now - t_rel, 0, None)
    spread = base * np.sqrt(np.maximum(drift, 0.05))
    lon = lon0 + u_eff * drift * DEG_PER_MS_HR + z_lon * spread
    lat = lat0 + v_eff * drift * DEG_PER_MS_HR + z_lat * spread
    return lon, lat, t_rel <= t_now + 1e-9


def build_replay_timeline(manifest: dict, attribution: dict, tracks_by_key: dict,
                          u: float, v: float) -> dict:
    from slicktrace_core.attribution import ENSEMBLE_VARIANTS, ReleaseHypothesisSpec

    acquired = _parse(manifest["acquired_utc"])
    base = {
        "incident_id": manifest["incident_id"],
        "acquired_utc": manifest["acquired_utc"],
        "variant": "nominal",
        "coordinate_decimals": DECIMALS,
    }
    top = attribution["ranking"][0] if attribution.get("ranking") else None
    if attribution.get("unknown_source") or top is None:
        return {**base, "named": False, "vessel_key": None, "frames": [],
                "note": ("No candidate was named, so no release is animated: showing the "
                         "best-scoring hypothesis would draw an attribution the analysis "
                         "declined to make.")}

    fixes = tracks_by_key[top["vessel_key"]]
    hyp = ReleaseHypothesisSpec(top["candidate_id"], top["vessel_key"], _parse(top["release_start"]),
                                top["duration_hours"], top["is_continuous"])
    first_h = min(HOURS_BACK, math.floor((acquired - hyp.release_start).total_seconds() / 3600))
    frames = []
    for h in range(first_h, -1, -1):
        when = acquired - timedelta(hours=h)
        lon, lat, released = replay_particles(hyp, fixes, u, v, ENSEMBLE_VARIANTS[0], acquired, when)
        ship = _interp_track_position(fixes, when)
        frames.append({
            "hours_before_acquisition": h,
            "time_utc": when.isoformat(),
            "released_fraction": round(float(released.mean()), 4),
            "ship_position": None if ship is None else [_r(ship[0]), _r(ship[1])],
            # Every particle, in the same order in every frame, so the map can
            # follow each one from hour to hour. Third field: released yet.
            # A particle still aboard sits at the point it will leave the ship.
            "particles": [[_r(x), _r(y), bool(r)] for x, y, r in zip(lon, lat, released)],
        })
    return {**base, "named": True, "vessel_key": top["vessel_key"],
            "candidate_id": top["candidate_id"], "release_start": top["release_start"],
            "duration_hours": top["duration_hours"], "is_continuous": top["is_continuous"],
            "frames": frames,
            "note": ("The leading candidate's best-fitting release, replayed hour by hour under the "
                     "nominal forcing member. Modelled, not observed: it shows how that hypothesis "
                     "forms the slick, and the frame at the image time is the footprint forward "
                     "replay scored. A lead for an analyst, not proof of responsibility.")}


def write_replay_timeline(case_dir: str, manifest: dict, attribution: dict, tracks_by_key: dict,
                          u: float, v: float) -> dict:
    out = build_replay_timeline(manifest, attribution, tracks_by_key, u, v)
    with open(os.path.join(case_dir, "replay_timeline.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    return out
