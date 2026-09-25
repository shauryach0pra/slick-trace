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

The numeric tolerance below is the real acceptance bound and is deliberately
duplicated from scripts/smoke_test.py: the smoke test checks a running server,
this checks the artifacts on disk, and both should fail if the physics moves.
It may not be loosened to make a run go green.
"""

from __future__ import annotations

import json
import os

import pytest

CASES_ROOT = os.path.join("data", "cases")
FROZEN_CASE = "case_0001"

MIN_TOP_CANDIDATE_IOU = 0.55


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


# Two claims about case_0001 were retired when the benchmark was fixed
# (CHANGELOG, "Benchmark: real geography and no leaked answers"): that the
# naive baseline falls for the decoy, and that the runner-up fits at IoU
# 0.30 or below. Both were properties of the old generator, which placed
# every innocent far from the slick and made the source loiter. Under the
# fair generator a loitering source can sit beside its own slick, so the
# naive baseline picks it, and passers-by fit as well as 0.49. The claims
# were removed from the documents, not only from the tests.


def test_no_vessel_key_encodes_its_role(roles):
    """Guards the fix directly: identifiers must not leak the answer again."""
    for key, role in roles.items():
        lowered = key.lower()
        for tell in ("true", "decoy", "source", "target", "guilty", "innocent"):
            assert tell not in lowered, f"vessel key {key!r} encodes its role ({role})"
