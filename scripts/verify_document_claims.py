"""Check every factual claim in the project document against the repository."""
import json, glob, os, subprocess, sys

ok, bad = [], []
def check(label, got, want, tol=None):
    if tol is not None:
        good = got is not None and abs(got - want) <= tol
    else:
        good = got == want
    (ok if good else bad).append(f"{label}: got {got!r}, doc says {want!r}")

V = json.load(open("docs/validation_report.json"))
sp, sa = V["attribution"]["source_present"], V["attribution"]["source_absent"]

check("source-present n",        sp["n"], 7)
check("method top-1",            sp["method_top1"], 7)
check("naive top-1",             sp["naive_top1"], 0)
check("McNemar p",               sp["mcnemar"]["p_value"], 0.0156, 1e-6)
check("source-absent n",         sa["n"], 2)
check("correct abstentions",     sa["correct_abstentions"], 1)
check("false named",             sa["false_named_attributions"], 1)
check("NLP total",               V["nlp"]["n"], 47)
check("NLP passed",              V["nlp"]["n_pass"], 47)
check("NLP refusals",            V["nlp"]["n_refusal"], 12)
check("leak audit rules flagged", sum(r["flagged"] for r in V["leak_audit"]["rules"]), 3)
check("no rule near 7/7",        max(r["hits"] for r in V["leak_audit"]["rules"]) < 6, True)

d = V["detection"]
check("classical val IoU",       round(d["baseline_val"]["iou_on_oil"],3), 0.857, 0.002)
check("classical val recall",    round(d["baseline_val"]["recall_on_oil"],3), 0.860, 0.002)
check("classical test IoU",      round(d["baseline_test"]["iou_on_oil"],3), 0.814, 0.002)
check("classical test recall",   round(d["baseline_test"]["recall_on_oil"],3), 0.819, 0.002)
check("classical val FP look",   d["baseline_val"]["false_positive_rate_lookalike"], 0.0)
check("classical test FP look",  d["baseline_test"]["false_positive_rate_lookalike"], 0.0)

u = d.get("unet")
if u and "val" in u:
    check("U-Net val IoU",       round(u["val"]["iou_on_oil"],3), 0.970, 0.002)
    check("U-Net val recall",    round(u["val"]["recall_on_oil"],3), 0.994, 0.002)
    check("U-Net test IoU",      round(u["test"]["iou_on_oil"],3), 0.968, 0.002)
    check("U-Net test recall",   round(u["test"]["recall_on_oil"],3), 0.998, 0.002)
else:
    bad.append("U-Net eval missing from validation_report.json")

cases = sorted(glob.glob("data/cases/case_*"))
check("case count", len(cases), 9)

ious = []
for c in cases:
    g = json.load(open(f"{c}/detection_result.json"))
    ious.append(g["agreement_with_truth_mask"]["iou"])
check("min scene IoU >= 0.95", min(ious) >= 0.95, True)
check("max scene IoU <= 0.99", max(ious) <= 0.99, True)

check("assumptions",
      int(subprocess.run("grep -c '^### A' docs/assumptions_register.md",
          shell=True, capture_output=True, text=True).stdout.strip()), 24)

t = subprocess.run("python3 -m pytest tests/ -q 2>&1 | tail -2",
                   shell=True, capture_output=True, text=True).stdout
check("338 tests pass", "338 passed" in t, True)

for f in ("data/geo/coastline_mumbai.json", "data/detection/unet.pt",
          "slicktrace_core/adapters/marinecadastre.py",
          "slicktrace_core/adapters/geotiff.py", "slicktrace_core/radiometry.py",
          "slicktrace_core/tiling.py", "slicktrace_core/speckle.py",
          "slicktrace_core/dossier.py", "docs/calibration_report.md",
          ".github/workflows/tests.yml"):
    check(f"exists {f}", os.path.exists(f), True)

fams = set()
for c in cases:
    fams.add(json.load(open(f"{c}/truth.json"))["family"])
check("five families", len(fams), 5)

print(f"\n{'='*60}\nPASSED {len(ok)}   FAILED {len(bad)}\n{'='*60}")
for b in bad:
    print("  MISMATCH:", b)
if not bad:
    print("  every claim in the document matches the repository")
