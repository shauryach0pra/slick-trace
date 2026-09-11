"""
Release-acceptance smoke test (masterplan p.6, p.15).

Run this against a running instance (local dev server OR the Docker
container) to verify it reproduces the frozen case_0001 result within
declared numeric tolerances. This is the check a teammate runs on each
target host, after disconnecting the network, before trusting a build.

Usage:
    python3 scripts/smoke_test.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
import json

# Declared tolerances for case_0001 — CPU/GPU bitwise equality is NOT
# required (masterplan p.6), just these bounds. These two numbers are the
# actual acceptance criteria and are NOT derived from the run: loosening
# either one would falsify the result rather than test it.
EXPECTED = {
    "min_top_candidate_iou": 0.55,
    "max_runner_up_iou": 0.30,
}

# Which vessel should win is identified by its ROLE in the frozen case, not by
# a literal identifier. Vessel keys are per-seed fictional MMSIs precisely so
# that no chart, screenshot or video frame announces the answer; hardcoding
# them here would reintroduce that coupling through the back door and would
# break again the next time a case is regenerated.
EXPECTED_ROLES = {
    "top_candidate": "true_source",
    "naive_baseline_top_candidate": "near_decoy",  # the naive baseline SHOULD be wrong
}

CASE_ID = "case_0001"


def load_expected_keys(repo_root: str, case_id: str = CASE_ID) -> dict | None:
    """Resolve the expected vessel keys from the dev-only truth sidecar.

    Read from the local checkout, never from the API — the served application
    has no access to this file and must not gain any. Returns None when the
    sidecar is unavailable (e.g. smoke-testing a remote host without the
    repo), in which case run() falls back to structural checks and says so
    rather than silently testing less.
    """
    path = os.path.join(repo_root, "data", "cases", case_id, "truth.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        truth = json.load(f)
    roles = truth.get("roles", {})
    resolved = {}
    for label, role in EXPECTED_ROLES.items():
        keys = [k for k, r in roles.items() if r == role]
        if len(keys) != 1:
            return None  # ambiguous or absent — do not guess
        resolved[label] = keys[0]
    return resolved


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def run(base_url: str, expected_keys: dict | None) -> bool:
    checks = []

    def check(name, condition, detail=""):
        checks.append((name, condition, detail))
        print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

    print(f"Smoke test against {base_url}\n")
    if expected_keys is None:
        print("  [note] truth sidecar unavailable — identity of the expected winner cannot be\n"
              "         checked from here. Falling back to structural checks: the two IoU\n"
              "         tolerances still apply, and the naive baseline must still disagree\n"
              "         with the method. Run from the repo checkout for the full check.\n")

    try:
        health = fetch_json(f"{base_url}/api/health")
        check("health endpoint responds", health.get("status") == "ok")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  [FAIL] could not reach {base_url}: {e}")
        return False

    try:
        attribution = fetch_json(f"{base_url}/api/incidents/{CASE_ID}/attribution")
        if expected_keys is not None:
            check("attribution top candidate is the true source",
                  attribution["top_candidate_id"] == expected_keys["top_candidate"],
                  f"got {attribution['top_candidate_id']}, "
                  f"expected {expected_keys['top_candidate']} (role: true_source)")
        else:
            check("attribution named a candidate (did not abstain on a source-present case)",
                  attribution["top_candidate_id"] is not None
                  and not attribution["unknown_source"],
                  f"got {attribution['top_candidate_id']}")
        top_iou = attribution["ranking"][0]["mean_iou"]
        check("top candidate IoU above tolerance",
              top_iou >= EXPECTED["min_top_candidate_iou"],
              f"iou={top_iou:.3f}, need >= {EXPECTED['min_top_candidate_iou']}")
        if len(attribution["ranking"]) > 1:
            runner_up_iou = attribution["ranking"][1]["mean_iou"]
            check("runner-up IoU below tolerance (not a near-tie)",
                  runner_up_iou <= EXPECTED["max_runner_up_iou"],
                  f"iou={runner_up_iou:.3f}, need <= {EXPECTED['max_runner_up_iou']}")
    except Exception as e:
        check("attribution result well-formed", False, str(e))

    try:
        naive = fetch_json(f"{base_url}/api/incidents/{CASE_ID}/naive-baseline")
        if expected_keys is not None:
            check("naive baseline reproduces the known decoy trap "
                  "(documents the improvement, not a bug)",
                  naive["top_candidate_id"] == expected_keys["naive_baseline_top_candidate"],
                  f"got {naive['top_candidate_id']}, "
                  f"expected {expected_keys['naive_baseline_top_candidate']} (role: near_decoy)")
        else:
            check("naive baseline disagrees with forward replay "
                  "(the improvement this case exists to show)",
                  naive["top_candidate_id"] != attribution.get("top_candidate_id"),
                  f"naive picked {naive['top_candidate_id']}")
    except Exception as e:
        check("naive baseline result well-formed", False, str(e))

    try:
        ask_result = post_json(f"{base_url}/api/incidents/{CASE_ID}/ask",
                                {"question": "What is the top candidate and why?"})
        check("ask endpoint returns a supported, cited answer",
              ask_result["supported"] and len(ask_result["citations"]) > 0)
    except Exception as e:
        check("ask endpoint reachable", False, str(e))

    all_passed = all(c[1] for c in checks)
    print(f"\n{'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'} "
          f"({sum(c[1] for c in checks)}/{len(checks)})")
    return all_passed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--repo-root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="checkout to read the dev-only truth sidecar from")
    args = ap.parse_args()
    sys.exit(0 if run(args.base_url, load_expected_keys(args.repo_root)) else 1)
