"""Per-case summary of track_display.json. Reads artifacts only; computes nothing
beyond totals. Run from the repository root after scripts/run_pipeline.py."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slicktrace_core.synth_generator import CASE_PLAN  # noqa: E402

print(f"{'case':<10} {'family':<19} {'vessels':>7} {'points':>7} {'display':>8} "
      f"{'gaps L/I/T/none':>16} {'type inferred':>14} {'present':>8} {'not reported':>13}")
tot = [0, 0, 0, 0, 0, 0, 0, 0, 0]
for cid, family, _seed in CASE_PLAN:
    d = json.load(open(os.path.join("data", "cases", cid, "track_display.json")))
    vs = d["vessels"]
    kinds = [g["kind"] for v in vs for g in v["gaps"]]
    row = [len(vs), sum(v["n_fixes"] for v in vs), sum(v["n_display_points"] for v in vs),
           kinds.count("leading"), kinds.count("internal"), kinds.count("trailing"),
           kinds.count("no_fixes"), sum(v["vessel_type"] is not None for v in vs),
           sum(v["vessel_type"] is None for v in vs)]
    tot = [a + b for a, b in zip(tot, row)]
    print(f"{cid:<10} {family:<19} {row[0]:>7} {row[1]:>7} {row[2]:>8} "
          f"{row[3]:>7}/{row[4]}/{row[5]}/{row[6]:<3} {0:>14} {row[7]:>8} {row[8]:>13}")
print(f"{'total':<10} {'':<19} {tot[0]:>7} {tot[1]:>7} {tot[2]:>8} "
      f"{tot[3]:>7}/{tot[4]}/{tot[5]}/{tot[6]:<3} {0:>14} {tot[7]:>8} {tot[8]:>13}")
print("type inferred is 0 by design: an MMSI does not encode ship type, so none is derived.")
