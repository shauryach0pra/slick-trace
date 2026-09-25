"""The canonical Case contract must describe every committed case exactly."""

from __future__ import annotations

import inspect
import json
import os
from typing import get_args

import pytest
from pydantic import ValidationError

import slicktrace_core.case_contract as contract
from slicktrace_core.case_contract import Attribution, Case, Family, build_case
from slicktrace_core.synth_generator import CASE_PLAN

CASES_ROOT = os.path.join("data", "cases")


def _dir(cid):
    return os.path.join(CASES_ROOT, cid)


@pytest.mark.parametrize("cid", [cid for cid, _f, _s in CASE_PLAN])
def test_every_case_validates_and_round_trips(cid):
    case = build_case(_dir(cid))
    assert Case.model_validate_json(case.model_dump_json()) == case


def test_family_labels_come_from_case_plan():
    assert set(get_args(Family)) == {fam for _cid, fam, _s in CASE_PLAN}
    for cid, fam, seed in CASE_PLAN:
        gen = build_case(_dir(cid)).meta.generator
        assert (gen.family, gen.seed) == (fam, seed), cid


def test_case_carries_no_ground_truth():
    assert "truth.json" not in inspect.getsource(contract)
    for cid, _f, _s in CASE_PLAN:
        blob = build_case(_dir(cid)).model_dump_json()
        for marker in ("_HIDDEN", "is_true_source", "true_vessel_key",
                       "expected_outcome", "release_start_utc"):
            assert marker not in blob, f"{cid} carries {marker}"


def test_unknown_artifact_fields_are_rejected():
    with open(os.path.join(_dir("case_0001"), "attribution_result.json")) as f:
        attribution = json.load(f)
    Attribution.model_validate(attribution)
    with pytest.raises(ValidationError):
        Attribution.model_validate({**attribution, "surprise_field": 1})


def test_cross_wired_artifacts_are_rejected():
    case = build_case(_dir("case_0001")).model_dump()
    other = build_case(_dir("case_0002")).model_dump()
    case["forecast"] = other["forecast"]
    with pytest.raises(ValidationError, match="belongs to case_0002"):
        Case.model_validate(case)
