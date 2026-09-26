"""
The map's time slider shows computed states only.

Replay frames are the leading candidate's scored run evaluated hour by hour;
forecast frames are the forecast's own particle paths. Each must agree exactly
with the artifact it extends, or the slider would be showing something the
analysis never computed.
"""
import json
import os

import numpy as np
import pytest

from slicktrace_core.synth_generator import CASE_PLAN

ROOT = os.path.join("data", "cases")
CASES = [cid for cid, _f, _s in CASE_PLAN]


def _load(cid, name):
    path = os.path.join(ROOT, cid, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated - run scripts/run_pipeline.py --regenerate")
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("cid", CASES)
def test_replay_is_animated_only_for_a_named_vessel(cid):
    at, rt = _load(cid, "attribution_result.json"), _load(cid, "replay_timeline.json")
    assert rt["named"] == (not at["unknown_source"])
    if rt["named"]:
        assert rt["vessel_key"] == at["top_candidate_id"] and rt["frames"]
    else:
        assert rt["frames"] == [] and rt["vessel_key"] is None


@pytest.mark.parametrize("cid", CASES)
def test_last_replay_frame_is_the_scored_footprint(cid):
    """Rasterised, the frame at the image time is the nominal footprint
    attribution scored - checked against a fresh run of simulate_hypothesis."""
    from slicktrace_core.attribution import (ENSEMBLE_VARIANTS, ReleaseHypothesisSpec,
                                             raster_particles_to_mask, simulate_hypothesis)
    from slicktrace_core.hindcast import _parse
    from slicktrace_core.replay_timeline import replay_particles
    rt = _load(cid, "replay_timeline.json")
    if not rt["named"]:
        pytest.skip("abstention: nothing animated")
    m, at = _load(cid, "manifest.json"), _load(cid, "attribution_result.json")
    top = at["ranking"][0]
    fixes = next(t["fixes"] for t in m["tracks"] if t["vessel_key"] == top["vessel_key"])
    f = np.load(m["forcing_path"])
    hyp = ReleaseHypothesisSpec(top["candidate_id"], top["vessel_key"], _parse(top["release_start"]),
                                top["duration_hours"], top["is_continuous"])
    acq = _parse(m["acquired_utc"])
    scored = simulate_hypothesis(hyp, fixes, float(f["u"]), float(f["v"]), ENSEMBLE_VARIANTS[0], acq, m["bbox"], seed=0)
    lon, lat, released = replay_particles(hyp, fixes, float(f["u"]), float(f["v"]), ENSEMBLE_VARIANTS[0], acq, acq)
    assert released.all()
    assert np.array_equal(raster_particles_to_mask(lon, lat, m["bbox"]), scored)
    assert rt["frames"][-1]["hours_before_acquisition"] == 0


@pytest.mark.parametrize("cid", CASES)
def test_replay_frames_run_forward_and_release_only_accumulates(cid):
    rt = _load(cid, "replay_timeline.json")
    hours = [f["hours_before_acquisition"] for f in rt["frames"]]
    assert hours == sorted(hours, reverse=True)
    rel = [f["released_fraction"] for f in rt["frames"]]
    assert all(b >= a for a, b in zip(rel, rel[1:]))
    # every frame carries every particle, in the same order, so each can be
    # followed from hour to hour; the released flag agrees with the fraction
    sizes = {len(f["particles"]) for f in rt["frames"]}
    assert len(sizes) <= 1
    for f in rt["frames"]:
        flags = [p[2] for p in f["particles"]]
        assert abs(sum(flags) / len(flags) - f["released_fraction"]) < 1e-3
        for prev, cur in zip(rt["frames"], rt["frames"][1:]):
            assert all(b[2] or not a[2] for a, b in zip(prev["particles"], cur["particles"])), \
                "a released particle never goes back aboard"


@pytest.mark.parametrize("cid", CASES)
def test_forecast_frames_agree_with_the_forecast(cid):
    fc, ct, ft = (_load(cid, n) for n in ("forecast_result.json", "forecast_contours.json",
                                           "forecast_timeline.json"))
    by_h = {f["hours_after_acquisition"]: f for f in ft["frames"]}
    assert sorted(by_h) == list(range(1, 25))
    for h in ct["horizons"]:
        assert by_h[h["horizon_hours"]]["density_contours"] == h["density_contours"]
    for h in fc["horizons"]:
        assert abs(by_h[h["horizon_hours"]]["stranded_fraction"] - (h["modelled_shoreline_fraction"] or 0)) < 1e-9
    stranded = [by_h[h]["stranded_fraction"] for h in sorted(by_h)]
    assert all(b >= a for a, b in zip(stranded, stranded[1:])), "stranded oil only accumulates"
