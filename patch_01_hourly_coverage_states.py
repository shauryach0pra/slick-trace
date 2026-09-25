#!/usr/bin/env python3
"""
Patch 01 - historical filtering: partial AIS coverage no longer counts as exclusion.

Run from the repository root:   python3 patch_01_hourly_coverage_states.py

What it changes
  slicktrace_core/hindcast.py   membership decided per queried time (inside /
                                outside / no_data), persisted as hourly_state;
                                `excluded` now requires track data at EVERY
                                queried time, as assumption A7 defines it
  slicktrace_core/report.py     state definitions and report note
  slicktrace_core/nlp_query.py  candidate-list answer names all three states
  scripts/run_validation.py     NLP suite {excluded} = filtered out before ranking
  tests/test_api_and_suite.py   same
  tests/nlp_suite.py            comment only
  tests/test_invariants.py      two new invariant tests
  scripts/verify_document_claims.py   test count 197 -> 199
  docs/assumptions_register.md  A6, A7 text and code locators
  frontend/src/ProvenancePanel.jsx, MetricInfo.jsx   state copy
  CHANGELOG.md                  entry for 25 September 2026

Safety
  Every anchor must match exactly once before ANY file is written. A missing or
  duplicated anchor aborts the whole patch with nothing changed. Re-running on
  an already-patched tree reports "already applied" per edit and changes nothing.
"""

from __future__ import annotations

import os
import sys

EDITS: list[tuple[str, str, str]] = []   # (path, old, new)


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


# --------------------------------------------------------------- hindcast --

edit("slicktrace_core/hindcast.py",
'''  - "excluded":    track data covers the window, but never entered it
  - "unassessed":  track has no data covering the queried window at all
''',
'''  - "excluded":    track data at EVERY queried time, and never inside
  - "unassessed":  never inside, and no track data at some or all times
''')

edit("slicktrace_core/hindcast.py",
'''    inside_at: list[float] = field(default_factory=list)  # hours_before values where inside
''',
'''    inside_at: list[float] = field(default_factory=list)  # hours_before values where inside
    hourly_state: list[str] = field(default_factory=list)  # per queried time: inside | outside | no_data
    hours_with_data: int = 0  # queried times at which the track has a position
    data_intervals_hours_before: list[list[float]] = field(default_factory=list)  # [from, to] runs with data
''')

edit("slicktrace_core/hindcast.py",
'''def assess_vessels(manifest: dict, snapshots: list[EnvelopeSnapshot],
                    inclusion_radius_deg: float = 0.045) -> list[VesselAssessment]:
    """Test every candidate vessel's position, at every backward snapshot
    time, against the particle cloud (nearest-particle distance — NOT a
    convex hull, so disjoint/diffuse envelope lobes aren't falsely bridged)."""
    trees = {
        snap.hours_before_acquisition: cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
        for snap in snapshots
    }

    results = []
    for tr in manifest["tracks"]:
        vkey = tr["vessel_key"]
        any_data = False
        inside_at = []
        for snap in snapshots:
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                continue
            any_data = True
            dist, _ = trees[snap.hours_before_acquisition].query([pos[0], pos[1]])
            if dist <= inclusion_radius_deg:
                inside_at.append(snap.hours_before_acquisition)

        if not any_data:
            results.append(VesselAssessment(vkey, "unassessed",
                                             reason="no track data covers the queried backward window"))
        elif inside_at:
            results.append(VesselAssessment(vkey, "candidate",
                                             first_entry_hours_before=max(inside_at),
                                             reason=f"inside envelope at {len(inside_at)} of "
                                                    f"{len(snapshots)} queried times",
                                             inside_at=sorted(inside_at)))
        else:
            results.append(VesselAssessment(vkey, "excluded",
                                             reason="track data present throughout window; "
                                                    "never inside the backward envelope"))
    return results
''',
'''INCLUSION_RADIUS_DEG = 0.045  # nearest-particle distance, degrees; see vessel_hourly_states

STATE_RULE = (
    "Membership is decided per queried time (inside, outside, no_data) and then "
    "summarised. candidate: inside the envelope at one or more queried times. "
    "excluded: track data at every queried time and never inside. unassessed: never "
    "inside where track data exists, and no track data at one or more queried times. "
    "Hours without data are missing evidence; they cannot exclude a vessel."
)


def vessel_hourly_states(manifest: dict, snapshots: list[EnvelopeSnapshot],
                         inclusion_radius_deg: float = INCLUSION_RADIUS_DEG) -> dict[str, list[dict]]:
    """Every vessel's position and envelope membership at every queried time.

    One of three states per time: `inside`, `outside`, or `no_data` where the
    track has no position (bounded interpolation, A6). Membership is the
    nearest-particle distance - NOT a convex hull, so disjoint or diffuse
    envelope lobes aren't falsely bridged.
    """
    trees = [cKDTree(np.column_stack([s.particles_lon, s.particles_lat])) for s in snapshots]
    out: dict[str, list[dict]] = {}
    for tr in manifest["tracks"]:
        rows = []
        for snap, tree in zip(snapshots, trees):
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                rows.append({"hours_before": snap.hours_before_acquisition, "lon": None,
                             "lat": None, "distance_deg": None, "state": "no_data"})
                continue
            dist, _ = tree.query([pos[0], pos[1]])
            rows.append({"hours_before": snap.hours_before_acquisition,
                         "lon": float(pos[0]), "lat": float(pos[1]), "distance_deg": float(dist),
                         "state": "inside" if dist <= inclusion_radius_deg else "outside"})
        out[tr["vessel_key"]] = rows
    return out


def _data_intervals(hours: list[float], states: list[str]) -> list[list[float]]:
    """Contiguous runs of queried times with track data, each as [from, to] in
    hours before acquisition (from >= to)."""
    runs: list[list[float]] = []
    lo = hi = None
    for h, s in zip(hours, states):
        if s == "no_data":
            if lo is not None:
                runs.append([hi, lo])
                lo = hi = None
            continue
        lo = h if lo is None else lo
        hi = h
    if lo is not None:
        runs.append([hi, lo])
    return runs


def _describe_intervals(runs: list[list[float]]) -> str:
    return "; ".join(f"{a:g} h before acquisition" if a == b
                     else f"{a:g} h to {b:g} h before acquisition" for a, b in runs)


def assess_vessels(manifest: dict, snapshots: list[EnvelopeSnapshot],
                    inclusion_radius_deg: float = INCLUSION_RADIUS_DEG) -> list[VesselAssessment]:
    """Summarise each vessel's per-time membership into one of three states.

      candidate   inside the envelope at one or more queried times
      excluded    track data at EVERY queried time, and never inside
      unassessed  never inside where data exists, and no track data at one or
                  more queried times - including a track with no data at all

    Partial coverage is never summarised as excluded: the hours without data
    are missing evidence, and a vessel cannot be cleared on the strength of
    them (A7). Before 25 Sep 2026 a single covered time was enough to exclude.
    """
    hourly = vessel_hourly_states(manifest, snapshots, inclusion_radius_deg)
    hours = [s.hours_before_acquisition for s in snapshots]
    n = len(snapshots)
    results = []
    for tr in manifest["tracks"]:
        vkey = tr["vessel_key"]
        states = [row["state"] for row in hourly[vkey]]
        inside_at = [h for h, s in zip(hours, states) if s == "inside"]
        with_data = sum(1 for s in states if s != "no_data")
        runs = _data_intervals(hours, states)
        coverage = {"hourly_state": states, "hours_with_data": with_data,
                    "data_intervals_hours_before": runs}
        if inside_at:
            results.append(VesselAssessment(
                vkey, "candidate", first_entry_hours_before=max(inside_at),
                reason=f"inside envelope at {len(inside_at)} of {n} queried times",
                inside_at=sorted(inside_at), **coverage))
        elif with_data == 0:
            results.append(VesselAssessment(
                vkey, "unassessed",
                reason="no track data covers the queried backward window", **coverage))
        elif with_data == n:
            results.append(VesselAssessment(
                vkey, "excluded",
                reason=f"track data at all {n} queried times; never inside the backward envelope",
                **coverage))
        else:
            results.append(VesselAssessment(
                vkey, "unassessed",
                reason=(f"no track data at {n - with_data} of {n} queried times; track data "
                        f"{_describe_intervals(runs)}, never inside the backward envelope. "
                        f"Hours without data cannot exclude a vessel"),
                **coverage))
    return results
''')

edit("slicktrace_core/hindcast.py",
'''        "hours_back": hours_back,
        "assessments": [a.__dict__ for a in assessments],
''',
'''        "hours_back": hours_back,
        "hours_queried": [s.hours_before_acquisition for s in snapshots],
        "inclusion_radius_deg": INCLUSION_RADIUS_DEG,
        "state_rule": STATE_RULE,
        "assessments": [a.__dict__ for a in assessments],
''')

# ----------------------------------------------------------------- report --

edit("slicktrace_core/report.py",
'''                "excluded": "track data present throughout the window, never inside the envelope",
                "unassessed": "no track data covering the queried window — missing evidence, "
                              "NOT exoneration",
''',
'''                "excluded": "track data at every queried time, never inside the envelope",
                "unassessed": "never inside where track data exists, but no track data at one or "
                              "more queried times — missing evidence, NOT exoneration",
''')

edit("slicktrace_core/report.py",
'''    w("> `unassessed` means no track data covered the queried window. That is missing "
      "evidence, not exoneration, and it is reported separately from `excluded` for "
      "exactly that reason.")
''',
'''    w("> `unassessed` means the track had no data at one or more queried times and was "
      "never inside the envelope where it did. Those hours are missing evidence, not "
      "exoneration, so the vessel is not `excluded`: that state requires data at every "
      "queried time.")
''')

# -------------------------------------------------------------------- NLP --

edit("slicktrace_core/nlp_query.py",
'''                                   f"(it may have been excluded during historical filtering).")
''',
'''                                   f"(it may have been filtered out as excluded or unassessed).")
''')

edit("slicktrace_core/nlp_query.py",
'''    cands = [a for a in kb.historical_mapping["assessments"] if a["status"] == "candidate"]
    excluded = [a for a in kb.historical_mapping["assessments"] if a["status"] == "excluded"]
    answer = (f"{len(cands)} candidate(s) survived historical filtering: "
              f"{', '.join(a['vessel_key'] for a in cands)}. "
              f"{len(excluded)} excluded: {', '.join(a['vessel_key'] for a in excluded)}.")
''',
'''    cands = [a for a in kb.historical_mapping["assessments"] if a["status"] == "candidate"]
    by_state = {s: [a["vessel_key"] for a in kb.historical_mapping["assessments"] if a["status"] == s]
                for s in ("candidate", "excluded", "unassessed")}

    def _keys(state: str) -> str:
        return ", ".join(by_state[state]) or "none"

    answer = (f"{len(cands)} candidate(s) survived historical filtering: {_keys('candidate')}. "
              f"{len(by_state['excluded'])} excluded (track data at every queried time, never "
              f"inside): {_keys('excluded')}. {len(by_state['unassessed'])} unassessed (never "
              f"inside where data exists, but data missing at some queried times; missing "
              f"evidence is not exoneration): {_keys('unassessed')}.")
''')

# ------------------------------------------ NLP suite: filtered-out vessels --

edit("scripts/run_validation.py",
'''    excluded = [a["vessel_key"] for a in (default_kb.historical_mapping or {}).get("assessments", [])
                if a["status"] == "excluded"]
''',
'''    # {excluded} in the suite means "filtered out before ranking": excluded or
    # unassessed. Keying it on status == "excluded" alone would silently change
    # the question whenever the state rule moves a vessel between the two.
    excluded = [a["vessel_key"] for a in (default_kb.historical_mapping or {}).get("assessments", [])
                if a["status"] != "candidate"]
''')

edit("tests/test_api_and_suite.py",
'''    excluded = [a["vessel_key"] for a in (kb.historical_mapping or {}).get("assessments", [])
                if a["status"] == "excluded"]
''',
'''    # filtered out before ranking: excluded or unassessed (see run_validation.py)
    excluded = [a["vessel_key"] for a in (kb.historical_mapping or {}).get("assessments", [])
                if a["status"] != "candidate"]
''')

edit("tests/nlp_suite.py",
'''    # two vessels that were EXCLUDED during historical filtering are not in the
    # ranking at all; the correct behaviour is to say so, not to invent a
    # comparison between them
''',
'''    # two vessels filtered out during historical filtering (excluded or
    # unassessed) are not in the ranking at all; the correct behaviour is to say
    # so, not to invent a comparison between them
''')

# ------------------------------------------------------------------ tests --

edit("tests/test_invariants.py",
'''        flipped = [g for g in frag["grid"] if g["flipped"]]
        assert frag["smallest_flip"]["magnitude"] == min(g["magnitude"] for g in flipped)
''',
'''        flipped = [g for g in frag["grid"] if g["flipped"]]
        assert frag["smallest_flip"]["magnitude"] == min(g["magnitude"] for g in flipped)


# ------------------------------------------------- per-time coverage (A7) --

def test_excluded_requires_track_data_at_every_queried_time():
    """`excluded` clears a vessel, so it must rest on data at every queried
    time. Until 25 Sep 2026 one covered time was enough, and every vessel then
    labelled excluded in the benchmark had data at 11 of 25."""
    for cid in ALL_CASE_IDS:
        hm = _load(cid, "historical_mapping.json")
        hours = hm["hours_queried"]
        for a in hm["assessments"]:
            states = a["hourly_state"]
            assert len(states) == len(hours)
            assert set(states) <= {"inside", "outside", "no_data"}
            assert a["inside_at"] == [h for h, s in zip(hours, states) if s == "inside"]
            assert a["hours_with_data"] == sum(s != "no_data" for s in states)
            if a["status"] == "candidate":
                assert "inside" in states
            elif a["status"] == "excluded":
                assert "no_data" not in states, f"{cid} {a['vessel_key']} excluded on partial data"
            else:
                assert "inside" not in states and "no_data" in states


def test_partial_coverage_is_unassessed_not_excluded():
    """Two vessels far from the slick: one tracked across the whole backward
    window, one only for its last five hours. The first is excluded. The second
    has no evidence for most of the window and must not be."""
    from slicktrace_core.hindcast import assess_vessels
    manifest = json.loads(json.dumps(_load("case_0001", "manifest.json")))
    acquired = _parse(manifest["acquired_utc"])

    def track(key, hours):
        return {"vessel_key": key,
                "fixes": [{"t_utc": (acquired - timedelta(hours=h)).isoformat(),
                           "lon": 73.05, "lat": 18.45, "sog_knots": 0.0, "cog_deg": 0.0,
                           "interpolated": False} for h in range(hours, -1, -1)]}

    manifest["tracks"] = [track("900000001", 24), track("900000002", 5)]
    got = {a.vessel_key: a for a in assess_vessels(manifest, build_backward_envelope(manifest))}
    assert got["900000001"].status == "excluded"
    partial = got["900000002"]
    assert partial.status == "unassessed"
    assert partial.hours_with_data == 6
    assert partial.data_intervals_hours_before == [[5.0, 0.0]]
    assert "no track data at 19 of 25" in partial.reason
''')

edit("scripts/verify_document_claims.py",
'''check("197 tests pass", "197 passed" in t, True)
''',
'''check("199 tests pass", "199 passed" in t, True)
''')

# ------------------------------------------------------------------- docs --

edit("docs/assumptions_register.md",
'''**Where:** `slicktrace_core/hindcast.py:109` (`_interp_track_position`)
''',
'''**Where:** `slicktrace_core/hindcast.py:112` (`_interp_track_position`)
''')

edit("docs/assumptions_register.md",
'''**How it is bounded.** Interpolation is confined strictly within a track's own
observed time range; outside it the function returns `None` and the vessel is
recorded as `unassessed` rather than guessed at. A single universal gap
threshold is not treated as proof of an outage.
''',
'''**How it is bounded.** Interpolation is confined strictly within a track's own
observed time range; outside it the function returns `None`, that queried time
is recorded as `no_data` in the vessel's `hourly_state`, and a vessel with any
`no_data` time cannot be summarised as `excluded` (A7). A single universal gap
threshold is not treated as proof of an outage.
''')

edit("docs/assumptions_register.md",
'''**Where:** `slicktrace_core/hindcast.py:24, 56, 149`
**Enforced by:** `tests/test_invariants.py:97, 110`
''',
'''**Where:** `slicktrace_core/hindcast.py:24, 56, 222, 227`
**Enforced by:** `tests/test_invariants.py:97, 110, 341, 362`
''')

edit("docs/assumptions_register.md",
'''**How it is bounded.** Three distinct states throughout the pipeline, the API,
the map (by shape as well as colour), the text-equivalent table and the
investigation report, which states the distinction in words.
''',
'''**How it is bounded.** Membership is decided per queried time first (`inside`,
`outside` or `no_data`, persisted as `hourly_state`) and only then summarised.
`excluded` requires track data at every queried time; partial coverage is
summarised as `unassessed`, with the span the data covers stated. Until
25 September 2026 a single covered time was enough to exclude, and the reason
string claimed coverage throughout the window: all 26 vessels then labelled
`excluded` had data at 11 of 25 queried times. The three states are carried
through the pipeline, the API, the text-equivalent table and the investigation
report, which states the distinction in words. The live map draws per-time
state; a vessel with no position at the selected time is not drawn.
''')

# --------------------------------------------------------------- frontend --

edit("frontend/src/ProvenancePanel.jsx",
'''  unassessed: ['Unassessed', 'no track data covering the queried window'],
''',
'''  unassessed: ['Unassessed', 'never inside where data exists; no track data for part or all of the window'],
''')

edit("frontend/src/MetricInfo.jsx",
'''      'Excluded: track data present throughout, never inside. Unassessed: no track data ' +
      'covering the window at all. Unassessed is missing evidence, not exoneration, which ' +
      'is why it is never merged into excluded.',
''',
'''      'Excluded: track data at every queried time, never inside. Unassessed: never inside ' +
      'where data exists, but no track data for part or all of the window. Those hours are ' +
      'missing evidence, not exoneration, which is why a partly covered vessel is never excluded.',
''')

# -------------------------------------------------------------- changelog --

edit("CHANGELOG.md",
'''---

## 13 September 2026
''',
'''---

## 25 September 2026

**Historical filtering: partial coverage no longer counts as exclusion.**
`slicktrace_core/hindcast.py` marked a vessel `excluded` if it had a position at
any one of the 25 queried times and was never inside the envelope, and the
reason string then claimed track data "present throughout window". Every one of
the 26 vessels excluded across the nine cases had data at 11 of 25 queried
times: generated tracks cover the last ten hours of a 24-hour window. Membership
is now decided per queried time (`inside`, `outside`, `no_data`, persisted as
`hourly_state` with `hours_with_data` and `data_intervals_hours_before`) and
only then summarised; `excluded` requires data at every queried time, as A7
always defined it. The 26 vessels are now `unassessed`, with the span their data
covers stated. Candidate sets, rankings, fragility and the headline are
unchanged (7/7 against 0/7, exact McNemar p = 0.0156), because neither state is
replayed. No vessel in the benchmark now qualifies as excluded: that needs
tracks spanning the window the manifest declares, a generator change not made
here. The NLP suite's "filtered out before ranking" question now draws on
excluded or unassessed vessels, so it resolves to the same two vessels as
before. Two invariant tests added; 199 pass.

---

## 13 September 2026
''')


# ------------------------------------------------------------------ apply --

def main() -> int:
    if not os.path.isfile("slicktrace_core/hindcast.py"):
        print("Run this from the slick-trace repository root.", file=sys.stderr)
        return 2
    original: dict[str, str | None] = {}
    staged: dict[str, str] = {}
    applied = skipped = 0
    for path, old, new in EDITS:
        if path not in staged:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    original[path] = staged[path] = f.read()
            else:
                original[path] = None
                staged[path] = ""
        text = staged[path]
        if old is None:                                   # whole new file
            if original[path] is None:
                staged[path] = new
                applied += 1
            elif original[path] == new:
                skipped += 1
            else:
                return _abort(f"{path} exists with different content")
            continue
        if old in new:
            # Append-style: the anchor survives application, so "applied" is
            # recognised by the new text, never by the anchor.
            if text.count(new) >= 1:
                skipped += 1
            elif text.count(old) == 1:
                staged[path] = text.replace(old, new, 1)
                applied += 1
            else:
                return _abort(f"{path}: anchor matched {text.count(old)} times", old)
        else:
            # Replacement or deletion: "applied" means the anchor is gone.
            n = text.count(old)
            if n == 1:
                staged[path] = text.replace(old, new, 1)
                applied += 1
            elif n == 0 and (not new or text.count(new) >= 1):
                skipped += 1
            else:
                return _abort(f"{path}: anchor matched {n} times", old)
    changed = [p for p in staged if staged[p] != original[p]]
    for path in changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(staged[path])
    print(f"patch 01: {applied} edits applied, {skipped} already in place, "
          f"{len(changed)} files changed.")
    return 0


def _abort(reason: str, anchor: str | None = None) -> int:
    print(f"ABORT: {reason} (expected exactly 1).", file=sys.stderr)
    if anchor:
        print(f"  anchor begins: {anchor.strip().splitlines()[0][:100]!r}", file=sys.stderr)
    print("No files were written.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
