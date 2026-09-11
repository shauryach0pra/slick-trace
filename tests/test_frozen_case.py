"""
The frozen case_0001 demo invariant, expressed by ROLE rather than by name.

Why this file exists
--------------------
The acceptance criterion for the demo used to be written as a pair of literal
vessel identifiers ("V-TRUE-0001" wins, "V-DECOY-NEAR" is the naive pick).
Those identifiers were removed on purpose: a ranking chart whose winning bar is
labelled V-TRUE proves nothing to a reviewer, so vessel keys became per-seed
fictional MMSIs and the roles moved to a dev-only sidecar.

That left `scripts/smoke_test.py` asserting names the generator no longer
produces, which failed 4/6 while the system underneath was entirely correct —
a broken test reporting a broken product. The lesson is that the invariant was
never really about the names; it is about which *role* wins. So it is pinned
here, by role, where a regeneration cannot invalidate it and where reverting to
hardcoded identifiers will fail loudly.

The two numeric tolerances below are the real acceptance bounds and are
deliberately duplicated from scripts/smoke_test.py: the smoke test checks a
running server, this checks the artifacts on disk, and both should fail if the
physics moves. Neither may be loosened to make a run go green.
"""

from __future__ import annotations

import json
import os

import pytest

CASES_ROOT = os.path.join("data", "cases")
FROZEN_CASE = "case_0001"

MIN_TOP_CANDIDATE_IOU = 0.55
MAX_RUNNER_UP_IOU = 0.30


def _load(name):
    path = os.path.join(CASES_ROOT, FROZEN_CASE, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated — run scripts/run_pipeline.py --regenerate")
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def roles():
    truth = _load("truth.json")
    return truth["roles"]


def _key_for_role(roles, role):
    keys = [k for k, r in roles.items() if r == role]
    assert len(keys) == 1, f"expected exactly one {role} vessel in {FROZEN_CASE}, got {keys}"
    return keys[0]


def test_forward_replay_ranks_the_true_source_first(roles):
    attribution = _load("attribution_result.json")
    assert attribution["top_candidate_id"] == _key_for_role(roles, "true_source")


def test_top_candidate_clears_the_fit_floor():
    attribution = _load("attribution_result.json")
    top_iou = attribution["ranking"][0]["mean_iou"]
    assert top_iou >= MIN_TOP_CANDIDATE_IOU, f"top IoU {top_iou:.3f} below {MIN_TOP_CANDIDATE_IOU}"


def test_runner_up_is_not_a_near_tie():
    attribution = _load("attribution_result.json")
    ranking = attribution["ranking"]
    assert len(ranking) > 1, "frozen case must retain more than one candidate to be a comparison"
    runner_up_iou = ranking[1]["mean_iou"]
    assert runner_up_iou <= MAX_RUNNER_UP_IOU, f"runner-up IoU {runner_up_iou:.3f} is a near-tie"


def test_naive_baseline_falls_for_the_decoy(roles):
    """The naive baseline being wrong is the point of this case, not a defect.

    If this ever starts passing in the sense of picking the true source, the
    case has stopped being a discriminating test and the comparison against
    historical proximity no longer demonstrates anything.
    """
    naive = _load("naive_baseline_result.json")
    assert naive["top_candidate_id"] == _key_for_role(roles, "near_decoy")


def test_the_two_methods_disagree():
    attribution = _load("attribution_result.json")
    naive = _load("naive_baseline_result.json")
    assert naive["top_candidate_id"] != attribution["top_candidate_id"]


def test_no_vessel_key_encodes_its_role(roles):
    """Guards the fix directly: identifiers must not leak the answer again."""
    for key, role in roles.items():
        lowered = key.lower()
        for tell in ("true", "decoy", "source", "target", "guilty", "innocent"):
            assert tell not in lowered, f"vessel key {key!r} encodes its role ({role})"
