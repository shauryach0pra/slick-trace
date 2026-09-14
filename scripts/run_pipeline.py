"""
Run every analysis stage over every case.

This is the reproducibility entry point: from a clean checkout,
`python3 scripts/run_pipeline.py --regenerate` rebuilds the cases from their
seeds and recomputes every artifact the API, the UI and the report read.
Nothing shown to a reviewer needs a file that this script cannot produce.

Stages, in dependency order:
    generate -> detect + characterise -> historical mapping -> naive baseline
             -> attribution
             -> fragility -> coverage -> forecast -> next observation
             -> investigation report
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slicktrace_core.dossier import build_dossier
from slicktrace_core.attribution import run_attribution, run_naive_baseline
from slicktrace_core.coverage import run_hidden_ais_experiment
from slicktrace_core.detection_geometry import run_detection
from slicktrace_core.forecast import run_forecast
from slicktrace_core.fragility import run_fragility
from slicktrace_core.hindcast import run_historical_mapping
from slicktrace_core.next_observation import run_next_observation
from slicktrace_core.report import export_report
from slicktrace_core.synth_generator import CASE_PLAN, generate_all


def run_case(case_dir: str, skip: set[str]) -> dict:
    timings = {}
    stages = [
        ("detection", lambda: run_detection(case_dir)),
        ("historical_mapping", lambda: run_historical_mapping(case_dir)),
        ("naive_baseline", lambda: run_naive_baseline(case_dir)),
        ("attribution", lambda: run_attribution(case_dir)),
        ("fragility", lambda: run_fragility(case_dir)),
        ("coverage", lambda: run_hidden_ais_experiment(case_dir)),
        ("forecast", lambda: run_forecast(case_dir)),
        ("next_observation", lambda: run_next_observation(case_dir)),
        ("report", lambda: export_report(case_dir)),
        # Last: renders the report the previous stage wrote. Computes nothing,
        # so it cannot disagree with the artifact it draws from.
        ("dossier", lambda: build_dossier(case_dir)),
    ]
    for name, fn in stages:
        if name in skip:
            continue
        t0 = time.time()
        fn()
        timings[name] = round(time.time() - t0, 2)
    return timings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true",
                    help="rebuild all cases from their seeds before running stages")
    ap.add_argument("--case", default=None, help="run a single incident id")
    ap.add_argument("--skip", default="", help="comma-separated stage names to skip")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    if args.regenerate:
        print("Regenerating cases from seeds...")
        for manifest, truth in generate_all():
            print(f"  {manifest['incident_id']}  family={truth['family']:17s} "
                  f"seed={truth['seed']}")
        print()

    ids = [args.case] if args.case else [cid for cid, _f, _s in CASE_PLAN]
    total = time.time()
    per_case = {}
    for cid in ids:
        case_dir = os.path.join("data", "cases", cid)
        if not os.path.isdir(case_dir):
            print(f"  {cid}: no such case directory — run with --regenerate first")
            continue
        t0 = time.time()
        timings = run_case(case_dir, skip)
        elapsed = time.time() - t0
        per_case[cid] = {"total_s": round(elapsed, 2), "stages_s": timings}
        slowest = max(timings, key=timings.get) if timings else "-"
        print(f"  {cid}: {elapsed:6.1f}s  "
              f"(slowest stage: {slowest} {timings.get(slowest, 0)}s)")
    wall = time.time() - total
    print(f"\nTotal {wall:.1f}s across {len(ids)} case(s).")

    # Masterplan p.15 asks for measured runtime with the actual hardware named.
    # These numbers were already being computed and then discarded at exit,
    # which forfeited a feasibility claim that the run had already earned.
    if per_case:
        os.makedirs("docs", exist_ok=True)
        with open(os.path.join("docs", "runtime.json"), "w") as f:
            json.dump({
                "wall_clock_s": round(wall, 2),
                "n_cases": len(per_case),
                "regenerated_from_seeds": bool(args.regenerate),
                "skipped_stages": sorted(skip),
                "hardware": {
                    "machine": platform.machine(),
                    "system": f"{platform.system()} {platform.release()}",
                    "python": platform.python_version(),
                    "cpu_count": os.cpu_count(),
                    "compute_profile": "CPU (no GPU, no torch in the served path)",
                },
                "per_case": per_case,
            }, f, indent=2)
        print("Runtime written to docs/runtime.json.")

    print("Artifacts written into each case directory. Run "
          "`python3 scripts/run_validation.py` to score them.")


if __name__ == "__main__":
    main()
