"""
The ensemble fan on the map is the runs attribution scored, not an illustration:
per candidate it must reproduce attribution's mean IoU and win count, and each
member's final oil must rasterise to the footprint attribution simulated.
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
def test_fan_reproduces_attribution_for_every_candidate(cid):
    at, fan = _load(cid, "attribution_result.json"), _load(cid, "ensemble_fan.json")
    assert [c["vessel_key"] for c in fan["candidates"]] == [r["vessel_key"] for r in at["ranking"]]
    for r, c in zip(at["ranking"], fan["candidates"]):
        assert len(c["members"]) == r["n_ensemble"]
        assert abs(c["mean_iou"] - r["mean_iou"]) < 1e-3
        assert c["ensemble_win_count"] == r["ensemble_win_count"]
    # each variant is won by exactly one candidate
    for vi in range(len(fan["forcing"]["variants"])):
        assert sum(c["members"][vi]["won"] for c in fan["candidates"]) == (1 if fan["candidates"] else 0)


@pytest.mark.parametrize("cid", CASES)
def test_fan_forcing_is_the_simulation_input(cid):
    from slicktrace_core.attribution import ENSEMBLE_VARIANTS
    fan, m = _load(cid, "ensemble_fan.json"), _load(cid, "manifest.json")
    f = np.load(m["forcing_path"])
    assert fan["forcing"]["u_ms"] == float(f["u"]) and fan["forcing"]["v_ms"] == float(f["v"])
    assert [v["name"] for v in fan["forcing"]["variants"]] == [v["name"] for v in ENSEMBLE_VARIANTS]


def test_leader_members_rasterise_to_the_scored_footprints():
    """case_0001's leader, all six members: the fan's runs are attribution's runs."""
    from slicktrace_core.attribution import (ENSEMBLE_VARIANTS, ReleaseHypothesisSpec,
                                             raster_particles_to_mask, simulate_hypothesis)
    from slicktrace_core.hindcast import _parse
    from slicktrace_core.replay_timeline import replay_particles
    cid = "case_0001"
    at, m = _load(cid, "attribution_result.json"), _load(cid, "manifest.json")
    top = at["ranking"][0]
    fixes = next(t["fixes"] for t in m["tracks"] if t["vessel_key"] == top["vessel_key"])
    f = np.load(m["forcing_path"])
    hyp = ReleaseHypothesisSpec(top["candidate_id"], top["vessel_key"], _parse(top["release_start"]),
                                top["duration_hours"], top["is_continuous"])
    acq = _parse(m["acquired_utc"])
    for vi, variant in enumerate(ENSEMBLE_VARIANTS):
        scored = simulate_hypothesis(hyp, fixes, float(f["u"]), float(f["v"]), variant, acq, m["bbox"], seed=vi)
        lon, lat, _ = replay_particles(hyp, fixes, float(f["u"]), float(f["v"]), variant, acq, acq, seed=vi)
        assert np.array_equal(raster_particles_to_mask(lon, lat, m["bbox"]), scored), variant["name"]
