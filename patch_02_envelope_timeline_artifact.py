#!/usr/bin/env python3
"""
Patch 02 - the time-slider replay is served from an artifact, not computed per request.

Requires patch 01. Run from the repository root:
    python3 patch_02_envelope_timeline_artifact.py

What it changes
  slicktrace_core/envelope_timeline.py   NEW. Builds envelope_timeline.json: 25
                                hourly frames (particles, 50/75/90% contours,
                                every vessel's position and membership)
  slicktrace_core/hindcast.py   historical-mapping stage computes per-time
                                membership once and writes both artifacts
  backend/app.py                /envelope serves the nearest frame; new
                                /envelope-timeline serves all 25; no simulation,
                                KDE or KD-tree at request time
  slicktrace_core/nlp_query.py  time-window answers read hourly_state from
                                historical_mapping.json instead of rebuilding
                                the envelope; the third 0.045 radius copy goes
  scripts/run_validation.py     latency table labels describe what is timed
  tests/test_api_and_suite.py   two tests: timeline == historical mapping;
                                endpoints do not simulate at request time
  scripts/verify_document_claims.py   test count 215 -> 217
  .github/workflows/tests.yml   determinism diff covers envelope_timeline.json
  frontend/src/TimeSliderMap.jsx  comment only
  CHANGELOG.md                  entry

Safety: identical to patch 01. Every anchor must match exactly once before any
file is written; a re-run changes nothing.
"""

from __future__ import annotations

import os
import sys

EDITS: list[tuple[str, str, str]] = []   # (path, old, new); old None = new file


def edit(path: str, old: str | None, new: str) -> None:
    EDITS.append((path, old, new))


# ------------------------------------------------------------- new module --

edit("slicktrace_core/envelope_timeline.py", None, '''"""
Backward-envelope timeline: every queried hour, computed once, in the pipeline.

The interface's UTC replay used to be served by an endpoint that rebuilt the
backward simulation, ran the density contours and re-tested every vessel on
each request, with its own copy of the inclusion radius. That made the slider,
the piece of evidence a reviewer actually watches, the one output the
determinism check never saw, and a place where membership could drift from the
historical mapping it illustrates.

This artifact is written by the historical-mapping stage from the same
snapshots and the same per-time membership pass (`vessel_hourly_states`) that
the historical mapping summarises. The API serves frames from it; an interface
can load it once and scrub without a request per step.

Coordinates are rounded to 5 decimal places (about 1 m). The contours come from
a kernel density estimate whose last floating-point digit can depend on the
linear algebra library a platform ships; rounding keeps the artifact
byte-identical across machines without moving anything a reader could see.
Written compactly rather than indented: 25 frames of 300 particles would
otherwise be mostly whitespace.
"""

from __future__ import annotations

import json
import os

from slicktrace_core.envelope_density import density_contours

DECIMALS = 5

DENSITY_NOTE = ("Contours enclose 50/75/90% of the estimated density over the "
                "backward particles. They describe where this transport model "
                "places the mass and inherit its assumptions; a tight contour "
                "means the model is confident, not that the answer is certain.")

ENVELOPE_NOTE = ("Envelope width grows with hours-back because release time, duration "
                 "and diffusivity are unknown. It is not converging on a point source. "
                 "At the longest lookbacks the outer contour runs past the frame: the "
                 "envelope genuinely extends beyond the imagery, and is drawn clipped "
                 "rather than truncated to fit.")


def _r(x: float) -> float:
    return round(float(x), DECIMALS)


def build_envelope_timeline(manifest: dict, snapshots: list, hourly: dict,
                            assessments: list, inclusion_radius_deg: float) -> dict:
    """One frame per snapshot. `hourly` is the output of
    hindcast.vessel_hourly_states for these snapshots; nothing is re-decided."""
    status = {a.vessel_key: a.status for a in assessments}
    frames = []
    for i, snap in enumerate(snapshots):
        vessels = []
        for tr in manifest["tracks"]:
            key = tr["vessel_key"]
            row = hourly[key][i]
            if row["state"] == "no_data":
                vessels.append({"vessel_key": key, "lon": None, "lat": None,
                                "in_envelope": None,
                                "overall_status": status.get(key, "unassessed"),
                                "at_this_time": "no_data"})
                continue
            vessels.append({"vessel_key": key, "lon": _r(row["lon"]), "lat": _r(row["lat"]),
                            "distance_to_envelope_deg": _r(row["distance_deg"]),
                            "in_envelope": row["state"] == "inside",
                            "overall_status": status.get(key, "unassessed"),
                            "at_this_time": row["state"]})
        hours_before = snap.hours_before_acquisition
        # Contours on the full particle set; any decimation happens at serving.
        contours = density_contours(snap.particles_lon, snap.particles_lat)
        frames.append({
            "hours_before_acquisition": hours_before,
            "time_utc": snap.time_utc.isoformat(),
            "layer_status": "modelled" if hours_before > 0 else "observed",
            "hindcast": hours_before > 0,
            "particles": [[_r(lo), _r(la)]
                          for lo, la in zip(snap.particles_lon, snap.particles_lat)],
            "density_contours": [{"fraction": c["fraction"],
                                  "polygons": [[[_r(x), _r(y)] for x, y in ring]
                                               for ring in c["polygons"]]}
                                 for c in contours],
            "vessels": vessels,
        })
    return {
        "incident_id": manifest["incident_id"],
        "acquired_utc": manifest["acquired_utc"],
        "hours_queried": [s.hours_before_acquisition for s in snapshots],
        "inclusion_radius_deg": inclusion_radius_deg,
        "n_particles": len(snapshots[0].particles_lon) if snapshots else 0,
        "coordinate_decimals": DECIMALS,
        "density_note": DENSITY_NOTE,
        "note": ENVELOPE_NOTE,
        "frames": frames,
    }


def write_envelope_timeline(case_dir: str, manifest: dict, snapshots: list, hourly: dict,
                            assessments: list, inclusion_radius_deg: float) -> dict:
    out = build_envelope_timeline(manifest, snapshots, hourly, assessments, inclusion_radius_deg)
    with open(os.path.join(case_dir, "envelope_timeline.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\\n")
    return out
''')

# --------------------------------------------------------------- hindcast --

edit("slicktrace_core/hindcast.py",
'''                    inclusion_radius_deg: float = INCLUSION_RADIUS_DEG) -> list[VesselAssessment]:
''',
'''                    inclusion_radius_deg: float = INCLUSION_RADIUS_DEG, hourly=None) -> list[VesselAssessment]:
''')

edit("slicktrace_core/hindcast.py",
'''    hourly = vessel_hourly_states(manifest, snapshots, inclusion_radius_deg)
    hours = [s.hours_before_acquisition for s in snapshots]
''',
'''    hourly = hourly or vessel_hourly_states(manifest, snapshots, inclusion_radius_deg)
    hours = [s.hours_before_acquisition for s in snapshots]
''')

edit("slicktrace_core/hindcast.py",
'''    snapshots = build_backward_envelope(manifest, hours_back=hours_back)
    assessments = assess_vessels(manifest, snapshots)
''',
'''    snapshots = build_backward_envelope(manifest, hours_back=hours_back)
    hourly = vessel_hourly_states(manifest, snapshots)
    assessments = assess_vessels(manifest, snapshots, hourly=hourly)
''')

edit("slicktrace_core/hindcast.py",
'''    out_path = os.path.join(case_dir, "historical_mapping.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out
''',
'''    out_path = os.path.join(case_dir, "historical_mapping.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    # Same snapshots, same membership pass: the replay the interface scrubs
    # through is this stage's output, not a second computation that could drift.
    from slicktrace_core.envelope_timeline import write_envelope_timeline
    write_envelope_timeline(case_dir, manifest, snapshots, hourly, assessments,
                            INCLUSION_RADIUS_DEG)
    return out
''')

# -------------------------------------------------------------------- API --

edit("backend/app.py",
'''Endpoints are intentionally thin: each reads artifacts already produced by the
pipeline stages, or recomputes a cheap derived view (the backward envelope for
the time slider), rather than re-implementing logic. This mirrors the
masterplan's "versioned analysis services" architecture (p.13) — detection,
hindcast, candidate replay, confidence checks and forecast stay separate,
callable stages.
''',
'''Endpoints are intentionally thin: each reads artifacts already produced by the
pipeline stages rather than re-implementing logic. The time slider is served
from envelope_timeline.json, which the historical-mapping stage writes; nothing
is simulated per request. Three request-time views remain and are named here:
/tracks resolves MMSI identity and AIS field quality, /probe reads the forcing
file for one point, and /report assembles the committed artifacts with this
session's query log. This mirrors the masterplan's "versioned analysis
services" architecture (p.13) — detection, hindcast, candidate replay,
confidence checks and forecast stay separate, callable stages.
''')

edit("backend/app.py",
'''from slicktrace_core.hindcast import _interp_track_position, _parse, build_backward_envelope
''',
'')

edit("backend/app.py",
'''_envelope_cache: dict[str, list] = {}
''',
'')

edit("backend/app.py",
'''    """State of the backward origin envelope at one point in time, plus every
    vessel's interpolated position then.

    This is what makes the UTC control a live instrument rather than a
    pre-rendered filmstrip: the reviewer drags the slider and watches
    candidates enter and leave the envelope. Three vessels excluded and two
    retained is an argument; watching the exclusion happen as time rewinds is
    the evidence.
    """
    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")

    if incident_id not in _envelope_cache:
        _envelope_cache[incident_id] = build_backward_envelope(m)
    snapshots = _envelope_cache[incident_id]

    snap = min(snapshots, key=lambda s: abs(s.hours_before_acquisition - hours_before))
    hm = _load_json(incident_id, "historical_mapping.json") or {}
    status_by_vessel = {a["vessel_key"]: a["status"] for a in hm.get("assessments", [])}

    # Probability contours over the particle cloud. A cloud of dots says
    # "somewhere around here"; contours enclosing 50/75/90% of the density say
    # how much of the probability sits where, which is the judgement the
    # envelope exists to support.
    from slicktrace_core.envelope_density import density_contours
    contours = density_contours(snap.particles_lon, snap.particles_lat)

    import numpy as np
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
    inclusion_radius = 0.045

    vessels = []
    for t in m["tracks"]:
        pos = _interp_track_position(t["fixes"], snap.time_utc)
        if pos is None:
            vessels.append({"vessel_key": t["vessel_key"], "lon": None, "lat": None,
                            "in_envelope": None, "overall_status": status_by_vessel.get(
                                t["vessel_key"], "unassessed"),
                            "at_this_time": "no_data"})
            continue
        dist, _ = tree.query([pos[0], pos[1]])
        vessels.append({
            "vessel_key": t["vessel_key"],
            "lon": round(float(pos[0]), 5), "lat": round(float(pos[1]), 5),
            "distance_to_envelope_deg": round(float(dist), 5),
            "in_envelope": bool(dist <= inclusion_radius),
            "overall_status": status_by_vessel.get(t["vessel_key"], "unassessed"),
            "at_this_time": "inside" if dist <= inclusion_radius else "outside",
        })

    step = max(1, len(snap.particles_lon) // max_particles)
    return {
        "incident_id": incident_id,
        "hours_before_acquisition": snap.hours_before_acquisition,
        "time_utc": snap.time_utc.isoformat(),
        "acquired_utc": m["acquired_utc"],
        "layer_status": "modelled" if snap.hours_before_acquisition > 0 else "observed",
        "hindcast": snap.hours_before_acquisition > 0,
        "inclusion_radius_deg": inclusion_radius,
        "particles": [[round(float(lo), 5), round(float(la), 5)]
                      for lo, la in zip(snap.particles_lon[::step], snap.particles_lat[::step])],
        # Contours are computed on the full particle set, not the decimated one
        # sent to the client: subsampling for bandwidth should not change where
        # the probability mass is said to be.
        "density_contours": contours,
        "density_note": ("Contours enclose 50/75/90% of the estimated density over the "
                          "backward particles. They describe where this transport model "
                          "places the mass and inherit its assumptions; a tight contour "
                          "means the model is confident, not that the answer is certain."),
        "vessels": vessels,
        "note": ("Envelope width grows with hours-back because release time, duration "
                 "and diffusivity are unknown. It is not converging on a point source. "
                 "At the longest lookbacks the outer contour runs past the frame: the "
                 "envelope genuinely extends beyond the imagery, and is drawn clipped "
                 "rather than truncated to fit."),
    }
''',
'''    """The backward origin envelope at one queried hour, plus every vessel's
    position and membership then.

    Served from envelope_timeline.json, which the historical-mapping stage
    writes from the same snapshots and membership pass it summarises. Nothing
    is simulated here: the frame nearest the requested time is returned, so the
    slider shows exactly the 25 hourly states the pipeline computed and the
    determinism check covers.
    """
    tl = _require(incident_id, "envelope_timeline.json", "envelope timeline")
    frame = min(tl["frames"], key=lambda f: abs(f["hours_before_acquisition"] - hours_before))
    step = max(1, len(frame["particles"]) // max_particles)
    return {
        "incident_id": incident_id,
        "hours_before_acquisition": frame["hours_before_acquisition"],
        "time_utc": frame["time_utc"],
        "acquired_utc": tl["acquired_utc"],
        "layer_status": frame["layer_status"],
        "hindcast": frame["hindcast"],
        "inclusion_radius_deg": tl["inclusion_radius_deg"],
        "particles": frame["particles"][::step],
        # Contours were computed on the full particle set, not the decimated one
        # sent to the client: subsampling for bandwidth does not move the mass.
        "density_contours": frame["density_contours"],
        "density_note": tl["density_note"],
        "vessels": frame["vessels"],
        "note": tl["note"],
    }


@app.get("/api/incidents/{incident_id}/envelope-timeline")
def get_envelope_timeline(incident_id: str):
    """All 25 hourly frames at once, so an interface can scrub without a
    request per step."""
    return _require(incident_id, "envelope_timeline.json", "envelope timeline")
''')

# -------------------------------------------------------------------- NLP --

edit("slicktrace_core/nlp_query.py",
'''from slicktrace_core.hindcast import _interp_track_position, _parse, build_backward_envelope
import numpy as np
from scipy.spatial import cKDTree
''',
'''from slicktrace_core.hindcast import _parse
''')

edit("slicktrace_core/nlp_query.py",
'''        self.tracks_by_key = {t["vessel_key"]: t for t in self.manifest["tracks"]}
        self._envelope_snapshots = None  # computed lazily, only if a time-window query needs it
''',
'''        self.tracks_by_key = {t["vessel_key"]: t for t in self.manifest["tracks"]}
''')

edit("slicktrace_core/nlp_query.py",
'''    @property
    def envelope_snapshots(self):
        if self._envelope_snapshots is None:
            self._envelope_snapshots = build_backward_envelope(self.manifest)
        return self._envelope_snapshots

''',
'')

edit("slicktrace_core/nlp_query.py",
'''    inclusion_radius = 0.045
    hits = []
    for snap in kb.envelope_snapshots:
        if not (t_start <= snap.time_utc <= t_end):
            continue
        tree = cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
        for tr in kb.manifest["tracks"]:
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                continue
            dist, _ = tree.query([pos[0], pos[1]])
            if dist <= inclusion_radius:
                hits.append((tr["vessel_key"], snap.time_utc, float(dist)))

    filters = {"time_start_utc": t_start.isoformat(), "time_end_utc": t_end.isoformat(),
               "inclusion_radius_deg": inclusion_radius}
''',
'''    # Per-time membership is read, not recomputed: historical_mapping.json holds
    # every vessel's state at every queried hour, decided once in the pipeline
    # by the same pass the historical filtering summarises.
    hm = kb.historical_mapping
    if not hm or "hours_queried" not in hm:
        return QueryResult(question, "time_window_vessels", supported=False,
                            answer="This case's historical mapping predates per-time envelope "
                                   "membership. Rerun scripts/run_pipeline.py to produce it.")
    states = {a["vessel_key"]: a["hourly_state"] for a in hm["assessments"]}
    hits = []
    for i, hours_before in enumerate(hm["hours_queried"]):
        t = acquired - timedelta(hours=hours_before)
        if not (t_start <= t <= t_end):
            continue
        for tr in kb.manifest["tracks"]:
            vessel_states = states.get(tr["vessel_key"])
            if vessel_states and vessel_states[i] == "inside":
                hits.append((tr["vessel_key"], t))

    filters = {"time_start_utc": t_start.isoformat(), "time_end_utc": t_end.isoformat(),
               "inclusion_radius_deg": hm["inclusion_radius_deg"]}
''')

edit("slicktrace_core/nlp_query.py",
'''        detail = "; ".join(f"{v} at {t.strftime('%H:%M')} UTC" for v, t, _ in hits)
        answer = f"Vessels inside the origin envelope in this window: {', '.join(seen)}. ({detail})"
    citations = [f"historical_mapping (recomputed) incident={kb.manifest['incident_id']}"] + \\
                [f"vessel={v} snapshot_time={t.isoformat()}" for v, t, _ in hits]
''',
'''        detail = "; ".join(f"{v} at {t.strftime('%H:%M')} UTC" for v, t in hits)
        answer = f"Vessels inside the origin envelope in this window: {', '.join(seen)}. ({detail})"
    citations = [f"historical_mapping.json field=hourly_state incident={kb.manifest['incident_id']}"] + \\
                [f"vessel={v} snapshot_time={t.isoformat()}" for v, t in hits]
''')

# ------------------------------------------------------ validation labels --

edit("scripts/run_validation.py",
'''    ask(kb, heavy_q)  # prime the envelope cache
''',
'''    ask(kb, heavy_q)  # prime
''')

edit("scripts/run_validation.py",
'''            w(f"| Time-window query, cold — fresh KB + envelope build | "
''',
'''            w(f"| Time-window query, cold — fresh KB, reads per-time state | "
''')

edit("scripts/run_validation.py",
'''            w(f"| Time-window query, warm — envelope cached (median of {nlp_timing['n_warm']}) | "
''',
'''            w(f"| Time-window query, warm (median of {nlp_timing['n_warm']}) | "
''')

edit("scripts/run_validation.py",
'''          + ". Cold and warm query times are reported separately because the "
            "backward envelope is cached after its first computation, and quoting "
            "only the warm number would overstate what a reviewer sees on first load.")
''',
'''          + ". Cold and warm query times are reported separately because a fresh "
            "knowledge base loads the case's artifacts on first use, and quoting "
            "only the warm number would overstate what a reviewer sees on first load. "
            "Time-window queries read per-time envelope membership from "
            "historical_mapping.json; nothing is simulated at query time.")
''')

# ------------------------------------------------------------------ tests --

edit("tests/test_api_and_suite.py",
'''def test_envelope_rejects_out_of_range_time():
    assert client.get(f"/api/incidents/{CASE}/envelope?hours_before=999").status_code == 422
''',
'''def test_envelope_rejects_out_of_range_time():
    assert client.get(f"/api/incidents/{CASE}/envelope?hours_before=999").status_code == 422


def test_envelope_timeline_agrees_with_historical_mapping():
    """The replay and the historical filtering come from one membership pass:
    every frame's per-vessel state must equal that vessel's hourly_state."""
    for cid in sorted(os.listdir(os.path.join("data", "cases"))):
        case_dir = os.path.join("data", "cases", cid)
        with open(os.path.join(case_dir, "envelope_timeline.json")) as f:
            tl = json.load(f)
        with open(os.path.join(case_dir, "historical_mapping.json")) as f:
            hm = json.load(f)
        assert [fr["hours_before_acquisition"] for fr in tl["frames"]] == hm["hours_queried"]
        assert tl["inclusion_radius_deg"] == hm["inclusion_radius_deg"]
        by_key = {a["vessel_key"]: a for a in hm["assessments"]}
        for i, frame in enumerate(tl["frames"]):
            for v in frame["vessels"]:
                a = by_key[v["vessel_key"]]
                assert v["at_this_time"] == a["hourly_state"][i], (cid, v["vessel_key"], i)
                assert v["overall_status"] == a["status"]


def test_envelope_endpoints_do_not_simulate_at_request_time(monkeypatch):
    """Serving the replay, or answering a time-window question, must not rerun
    the backward simulation, the membership pass or the density estimate."""
    import backend.app as api_module
    import slicktrace_core.envelope_density as density_module
    import slicktrace_core.hindcast as hindcast_module
    import slicktrace_core.nlp_query as nlp_module

    def refuse(*_args, **_kwargs):
        raise AssertionError("simulation at request time")

    for mod in (hindcast_module, api_module, nlp_module):
        for name in ("build_backward_envelope", "vessel_hourly_states", "assess_vessels"):
            monkeypatch.setattr(mod, name, refuse, raising=False)
    for mod in (density_module, api_module, nlp_module):
        monkeypatch.setattr(mod, "density_contours", refuse, raising=False)

    timeline = client.get(f"/api/incidents/{CASE}/envelope-timeline").json()
    assert len(timeline["frames"]) == 25
    for h in (0, 7, 24):
        resp = client.get(f"/api/incidents/{CASE}/envelope?hours_before={h}")
        assert resp.status_code == 200
        assert resp.json()["time_utc"] == timeline["frames"][h]["time_utc"]
    answer = client.post(f"/api/incidents/{CASE}/ask", json={
        "question": "Which vessels crossed the likely origin zone from 02:00 to 05:00 UTC?"}).json()
    assert answer["supported"] and "hourly_state" in answer["citations"][0]
''')

edit("scripts/verify_document_claims.py",
'''check("215 tests pass", "215 passed" in t, True)
''',
'''check("217 tests pass", "217 passed" in t, True)
''')

# --------------------------------------------------------------------- CI --

edit(".github/workflows/tests.yml",
'''      # Every analysis artifact - attribution, fragility, hindcast, coverage,
      # forecast, next-observation, detection - regenerates byte-identically on
      # a different OS and architecture, and that is what the reproducibility
      # claim rests on.
''',
'''      # Every analysis artifact - attribution, fragility, hindcast, coverage,
      # forecast, next-observation, detection - regenerates byte-identically on
      # a different OS and architecture, and that is what the reproducibility
      # claim rests on.
      #
      # envelope_timeline.json is what the time slider shows. Its contours come
      # from a kernel density estimate whose last digit can depend on the
      # platform's linear algebra; coordinates are rounded to 5 decimals so the
      # file should still match, and this diff is what establishes that.
''')

edit(".github/workflows/tests.yml",
'''            'data/cases/*/historical_mapping.json' \\
''',
'''            'data/cases/*/historical_mapping.json' \\
            'data/cases/*/envelope_timeline.json' \\
''')

# --------------------------------------------------------------- frontend --

edit("frontend/src/TimeSliderMap.jsx",
''' * demonstration: three vessels excluded and two retained is an argument;
 * watching the exclusion happen as time rewinds is the evidence. The slider
 * queries the backward envelope for the requested time rather than stepping
 * through pre-rendered frames, so a reviewer can stop anywhere.
''',
''' * demonstration: vessels filtered out and vessels retained is an argument;
 * watching membership change as time rewinds is the evidence. The slider
 * selects one of the 25 hourly states the pipeline computed and serves
 * (envelope_timeline.json); nothing is interpolated between them.
''')

# -------------------------------------------------------------- changelog --

edit("CHANGELOG.md",
'''Nothing in the interface reads it yet. Three tests added; 215 pass.
''',
'''Nothing in the interface reads it yet. Three tests added; 215 pass.

**Time-slider replay served from an artifact, not computed per request.**
`/api/incidents/{id}/envelope` rebuilt the backward simulation, re-ran the
density contours and re-tested every vessel on each request, with its own copy
of the 0.045° inclusion radius; the query console did the same for time-window
questions with a third copy. None of it was covered by the determinism check.
The historical-mapping stage now also writes `envelope_timeline.json` (25 hourly
frames: particles, 50/75/90% contours, every vessel's position and membership)
from the same snapshots and per-time pass it summarises. `/envelope` serves the
nearest frame, `/envelope-timeline` serves all 25, and time-window questions
read `hourly_state` from `historical_mapping.json`. The served API no longer
reads the ground-truth mask at request time; the pipeline still seeds the
hindcast from it. Measured: every frame's per-vessel state equals the historical
mapping's in all nine cases; the old and new `/envelope` agree on every field
for all 25 hours of all nine cases, contours to the 5-decimal rounding the
artifact applies; the NLP suite returns the same 40 answers. CI now diffs the
new artifact. Two tests added; 217 pass.
''')


# ------------------------------------------------------------------ apply --

def main() -> int:
    if not os.path.isfile("slicktrace_core/hindcast.py"):
        print("Run this from the slick-trace repository root.", file=sys.stderr)
        return 2
    with open("slicktrace_core/hindcast.py", encoding="utf-8") as f:
        if "def vessel_hourly_states(" not in f.read():
            print("ABORT: patch 01 is not applied (hindcast.vessel_hourly_states missing).",
                  file=sys.stderr)
            return 1
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
    print(f"patch 02: {applied} edits applied, {skipped} already in place, "
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
