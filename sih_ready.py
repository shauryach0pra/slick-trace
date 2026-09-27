#!/usr/bin/env python3
"""
Get the Slick Trace dashboard up to date: apply patches 85-114, only the ones not already applied,
in order, stopping at the first problem.

Each patch leaves a unique trace in the code; a patch whose trace is present is skipped. Patches are
never re-run blindly - some replace whole files, and re-running one after a later patch would undo it.

Run from the repository root:   python3 sih_ready.py            (applies what is missing)
                                python3 sih_ready.py --check    (only reports; changes nothing)
Patch files are looked for in the repository root, ~/Downloads and ~/Downloads/slicktrace-patches.
"""
import glob, os, subprocess, sys

# patch -> (file, a string only that patch introduces)
TRACE = {
    85: ("frontend/src/cards/caseFinding.css", ".cf6-list { display: grid"),
    86: ("frontend/src/cards/CaseFindingCard.jsx", "runnerUp && { kind: 'caution'"),
    87: ("slicktrace_core/dossier.py", "ON THE DESIGN"),
    88: ("frontend/src/ConclusionGraph.jsx", "onScroll={onScroll}"),
    89: ("frontend/src/cards/ProvenanceCard.jsx", "function RowCount("),
    90: ("frontend/src/ui/useCountUp.js", "ease.current(k)"),
    91: ("frontend/src/cards/ForecastCard.jsx", "Modelled, not a forecast"),
    92: ("frontend/src/cards/ProvenanceCard.jsx", "k: 'named', label: 'Named'"),
    93: ("frontend/src/cards/CaseFindingCard.jsx", "Leads the runner-up by a"),
    94: ("frontend/src/ConclusionGraph.css", "--cg-pad"),
    95: ("frontend/src/map/ReplayMap.css", "the popup's \"Leading candidate\" pill"),
    96: ("frontend/src/App.jsx", "Synthetic case</span>"),
    97: ("frontend/src/cards/FragilityCard.jsx", "function ExploreResult("),
    98: ("frontend/src/shell.css", "keep their tag in the top right on one line"),
    99: ("frontend/src/ConclusionGraph.css", "no edge fades: the strip runs edge to edge"),
    100: ("frontend/src/cards/FragilityCard.jsx", 'className="fr-ex-group"'),
    101: ("frontend/src/cards/fragility.css", "the smallest flip as part of the column"),
    102: ("frontend/src/shell.css", "the two half-width cards stand the same height"),
    103: ("frontend/src/ConclusionGraph.jsx", "const tallest = "),
    104: ("frontend/src/cards/ProvenanceCard.jsx", 'title="Traffic and Provenance"'),
    105: ("frontend/src/ConclusionGraph.jsx", "slick found"),
    106: ("frontend/src/map/ReplayMap.jsx", "const toggleFollow"),
    107: ("frontend/src/map/replayCard.css", "the legend: its four chips centred"),
    108: ("frontend/src/ConclusionGraph.jsx", "The lead first flips when"),
    109: ("frontend/src/map/ReplayMap.jsx", "still move on every frame"),
    110: ("frontend/src/map/TimeScrubber.jsx", "Apple's video player"),
    111: ("frontend/src/ConclusionGraph.jsx", "A single dark region, found by the classical detector"),
    112: ("frontend/src/cards/FragilityCard.jsx", "fr-ro-a"),
    113: ("frontend/src/map/ReplayMap.jsx", "rmap-moment"),
    114: ("frontend/src/map/ReplayMap.jsx", "useState({ fan: true })"),
}

def applied(n):
    f, s = TRACE[n]
    return os.path.exists(f) and s in open(f, encoding="utf-8").read()

def find(n):
    for d in (".", os.path.expanduser("~/Downloads"), os.path.expanduser("~/Downloads/slicktrace-patches")):
        hits = sorted(glob.glob(os.path.join(d, f"patch_{n}_*.py")))
        if hits: return hits[0]
    return None

if not (os.path.isdir("frontend/src") and os.path.isdir("slicktrace_core")):
    sys.exit("Run this from the slick-trace repository root.")

check = "--check" in sys.argv
missing = [n for n in TRACE if not applied(n)]
print(f"applied: {len(TRACE) - len(missing)} of {len(TRACE)}" + (f" | missing: {', '.join(map(str, missing))}" if missing else " - everything is in place"))
if check or not missing:
    sys.exit(0)

for n in missing:
    path = find(n)
    if not path:
        sys.exit(f"patch {n}: FILE NOT FOUND - download patch_{n}_*.py again, then re-run this. Nothing more was changed.")
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0 or not applied(n):
        print(f"patch {n}: FAILED\n{r.stdout}{r.stderr}")
        sys.exit(f"Stopped at patch {n}. Paste this output to get it sorted. Patches before it are applied.")
    print(f"patch {n}: {last}")
print("done - every patch 85-114 is applied. Now rebuild: (cd frontend && npm run build)")
