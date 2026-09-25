#!/usr/bin/env python3
"""
Patch 04 - track display: AIS gap windows, rendering-only paths, vessel type not invented.

Requires patches 01-03. Run from the repository root:
    python3 patch_04_track_display.py

What it changes
  slicktrace_core/track_display.py   NEW. Pipeline stage writing track_display.json:
                                per vessel, gap windows inside the declared AIS
                                window, a centripetal Catmull-Rom display path that
                                never crosses a gap, and vessel_type null with reason
  scripts/track_summary.py      NEW. Per-case summary table from the artifact
  tests/test_track_display.py   NEW. seven tests
  scripts/run_pipeline.py       new stage after historical mapping
  slicktrace_core/case_contract.py  schema 3: optional track_display section
  backend/app.py                /track-display
  scripts/verify_document_claims.py   test count 223 -> 230
  .github/workflows/tests.yml   determinism diff covers track_display.json
  CHANGELOG.md                  entry

No existing artifact changes.

Safety: identical to patches 01-03. Every anchor must match exactly once before
any file is written; a re-run changes nothing.
"""

from __future__ import annotations

import os
import sys

EDITS: list[tuple[str, str, str]] = []   # (path, old, new); old None = new file


def edit(path: str, old: str | None, new: str) -> None:
    EDITS.append((path, old, new))

# ------------------------------------------------------------- new module --

edit("slicktrace_core/track_display.py", None, '''"""
Track display: what the map draws for each vessel, derived in the pipeline.

For every vessel in a case this records three things the interface needs and
must not compute itself.

  gaps          Windows inside the declared AIS window with no usable position
                report, each [start, end] with a kind: leading (window start to
                first fix), internal (consecutive fixes more than twice the
                track's median step apart), trailing (last fix to window end),
                or no_fixes. A fix whose position is a reserved sentinel
                (ais_quality) counts as missing. A gap is "no position
                reported": missing evidence, not proof of an outage (A6) and
                never culpability (A7).

  display_path  A centripetal Catmull-Rom curve (alpha 0.5) through the usable
                fixes, three points inserted per step, for rendering only. It
                passes through every fix, never bridges a gap, and is used by
                no analysis: the hindcast and forward replay interpolate
                linearly between the original fixes, which remain the source of
                truth. max_display_deviation_m says how far the curve strays
                from those straight segments.

  vessel_type   Not reported. An MMSI does not encode ship type; that is AIS
                static data (message 5), which this source does not carry. The
                field says so rather than inferring one.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta

from slicktrace_core.ais_quality import validate_fix

DECIMALS = 5
INSERTED_PER_STEP = 3
INTERNAL_GAP_FACTOR = 2.0
METRES_PER_DEG = 6_371_008.8 * math.pi / 180.0
VESSEL_TYPE_SOURCE = ("not reported: an MMSI does not encode ship type, and this source "
                      "carries no AIS static data (message 5)")

GAP_RULE = ("Windows inside the declared AIS window with no usable position report. "
            "leading: window start to first fix; internal: consecutive fixes more than "
            f"{INTERNAL_GAP_FACTOR:g} x the track's median step apart; trailing: last fix to "
            "window end; no_fixes: no usable fix in the window. A sentinel position counts "
            "as missing. No position reported is missing evidence, not proof of an outage.")

DISPLAY_RULE = (f"Centripetal Catmull-Rom (alpha 0.5) through the usable fixes, "
                f"{INSERTED_PER_STEP} points inserted per step, never across a gap. For "
                "rendering only; every analysis uses the original fixes with straight-line "
                "interpolation.")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _gap(kind: str, start: datetime, end: datetime) -> dict:
    return {"kind": kind, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "hours": round((end - start).total_seconds() / 3600.0, 4)}


def find_gaps(fixes: list[dict], window_start: datetime, window_end: datetime):
    """(gaps, usable fixes inside the window, internal threshold in minutes)."""
    usable = sorted((f for f in fixes if validate_fix(f)["usable_position"]
                     and window_start <= _t(f["t_utc"]) <= window_end),
                    key=lambda f: _t(f["t_utc"]))
    if not usable:
        return [_gap("no_fixes", window_start, window_end)], [], None
    times = [_t(f["t_utc"]) for f in usable]
    steps = sorted((b - a).total_seconds() / 60.0 for a, b in zip(times, times[1:]))
    threshold = INTERNAL_GAP_FACTOR * steps[len(steps) // 2] if steps else None
    gaps = []
    if times[0] > window_start:
        gaps.append(_gap("leading", window_start, times[0]))
    for a, b in zip(times, times[1:]):
        if threshold is not None and (b - a).total_seconds() / 60.0 > threshold:
            gaps.append(_gap("internal", a, b))
    if times[-1] < window_end:
        gaps.append(_gap("trailing", times[-1], window_end))
    return gaps, usable, threshold


def _catmull_rom(p0, p1, p2, p3, n: int) -> list[tuple[float, float]]:
    """n points strictly between p1 and p2 on the centripetal Catmull-Rom curve.
    Knot spacing is sqrt(chord), computed with sqrt only so every platform
    rounds it identically."""
    def knot(a, b):
        return math.sqrt(max(math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2), 1e-12))

    t0 = 0.0
    t1 = t0 + knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)

    def lerp(a, b, ta, tb, t):
        wa, wb = (tb - t) / (tb - ta), (t - ta) / (tb - ta)
        return (wa * a[0] + wb * b[0], wa * a[1] + wb * b[1])

    out = []
    for k in range(1, n + 1):
        t = t1 + (t2 - t1) * k / (n + 1)
        a1, a2, a3 = lerp(p0, p1, t0, t1, t), lerp(p1, p2, t1, t2, t), lerp(p2, p3, t2, t3, t)
        b1, b2 = lerp(a1, a2, t0, t2, t), lerp(a2, a3, t1, t3, t)
        out.append(lerp(b1, b2, t1, t2, t))
    return out


def _segment_distance_m(p, a, b) -> float:
    """Distance from p to segment ab, all in local metres."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    s = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    ex, ey = p[0] - (a[0] + s * dx), p[1] - (a[1] + s * dy)
    return math.sqrt(ex * ex + ey * ey)


def display_path(usable: list[dict], gaps: list[dict], lat0: float):
    """(path points [lon, lat, t_utc, is_fix], max deviation from straight segments in m)."""
    kx = math.cos(math.radians(lat0))
    breaks = {_t(g["start_utc"]) for g in gaps if g["kind"] == "internal"}
    segments, cur = [], []
    for f in usable:
        cur.append(f)
        if _t(f["t_utc"]) in breaks:
            segments.append(cur)
            cur = []
    if cur:
        segments.append(cur)

    path, worst = [], 0.0
    for seg in segments:
        P = [(f["lon"] * kx, f["lat"]) for f in seg]
        T = [_t(f["t_utc"]) for f in seg]
        for i in range(len(seg)):
            path.append([round(seg[i]["lon"], DECIMALS), round(seg[i]["lat"], DECIMALS),
                         seg[i]["t_utc"], True])
            if i == len(seg) - 1:
                break
            p0 = P[i - 1] if i > 0 else (2 * P[0][0] - P[1][0], 2 * P[0][1] - P[1][1])
            p3 = P[i + 2] if i + 2 < len(P) else (2 * P[-1][0] - P[-2][0], 2 * P[-1][1] - P[-2][1])
            for k, (x, y) in enumerate(_catmull_rom(p0, P[i], P[i + 1], p3, INSERTED_PER_STEP), 1):
                t = T[i] + (T[i + 1] - T[i]) * (k / (INSERTED_PER_STEP + 1))
                path.append([round(x / kx, DECIMALS), round(y, DECIMALS), t.isoformat(), False])
                a = (P[i][0] * METRES_PER_DEG, P[i][1] * METRES_PER_DEG)
                b = (P[i + 1][0] * METRES_PER_DEG, P[i + 1][1] * METRES_PER_DEG)
                worst = max(worst, _segment_distance_m((x * METRES_PER_DEG, y * METRES_PER_DEG), a, b))
    return path, round(worst)


def run_track_display(case_dir: str) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    ws, we = _t(manifest["ais_window_start_utc"]), _t(manifest["ais_window_end_utc"])
    b = manifest["bbox"]
    lat0 = (b["min_lat"] + b["max_lat"]) / 2.0
    vessels = []
    for tr in manifest["tracks"]:
        gaps, usable, threshold = find_gaps(tr["fixes"], ws, we)
        path, deviation = display_path(usable, gaps, lat0)
        vessels.append({
            "vessel_key": tr["vessel_key"],
            "vessel_type": None,
            "vessel_type_source": VESSEL_TYPE_SOURCE,
            "n_fixes": len(tr["fixes"]),
            "n_usable_fixes": len(usable),
            "internal_gap_threshold_minutes": threshold,
            "gaps": gaps,
            "hours_without_position": round(sum(g["hours"] for g in gaps), 4),
            "n_display_points": len(path),
            "max_display_deviation_m": deviation,
            "display_path": path,
        })
    out = {
        "incident_id": manifest["incident_id"],
        "ais_window_start_utc": manifest["ais_window_start_utc"],
        "ais_window_end_utc": manifest["ais_window_end_utc"],
        "gap_rule": GAP_RULE,
        "display_rule": DISPLAY_RULE,
        "vessels": vessels,
    }
    with open(os.path.join(case_dir, "track_display.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\\n")
    return out
''')

# ------------------------------------------------------------ summary script --

edit("scripts/track_summary.py", None, '''"""Per-case summary of track_display.json. Reads artifacts only; computes nothing
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
''')

# ------------------------------------------------------------- tests (new) --

edit("tests/test_track_display.py", None, '''"""Track display: gap windows, rendering-only paths, and no invented vessel type."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.app import app
from slicktrace_core.synth_generator import CASE_PLAN
from slicktrace_core.track_display import display_path, find_gaps

CASES = [cid for cid, _f, _s in CASE_PLAN]


def _load(cid, name):
    with open(os.path.join("data", "cases", cid, name)) as f:
        return json.load(f)


def _t(s):
    return datetime.fromisoformat(s)


def test_leading_and_trailing_gaps_are_exactly_the_no_data_hours():
    """The hindcast's no_data hours and the gap windows describe the same
    absence, so the map and the provenance badge cannot disagree."""
    for cid in CASES:
        td, hm, m = (_load(cid, n) for n in ("track_display.json", "historical_mapping.json",
                                              "manifest.json"))
        acquired = _t(m["acquired_utc"])
        states = {a["vessel_key"]: a["hourly_state"] for a in hm["assessments"]}
        for v in td["vessels"]:
            for h, state in zip(hm["hours_queried"], states[v["vessel_key"]]):
                t = acquired - timedelta(hours=h)
                in_gap = any((g["kind"] == "leading" and _t(g["start_utc"]) <= t < _t(g["end_utc"]))
                             or (g["kind"] == "trailing" and _t(g["start_utc"]) < t <= _t(g["end_utc"]))
                             or g["kind"] == "no_fixes"
                             for g in v["gaps"])
                assert in_gap == (state == "no_data"), (cid, v["vessel_key"], h)


def test_gaps_are_ordered_and_inside_the_declared_window():
    for cid in CASES:
        td = _load(cid, "track_display.json")
        ws, we = _t(td["ais_window_start_utc"]), _t(td["ais_window_end_utc"])
        for v in td["vessels"]:
            spans = [(_t(g["start_utc"]), _t(g["end_utc"])) for g in v["gaps"]]
            assert all(ws <= a < b <= we for a, b in spans), (cid, v["vessel_key"])
            assert all(b1 <= a2 for (_a1, b1), (a2, _b2) in zip(spans, spans[1:]))
            assert abs(v["hours_without_position"] - sum(g["hours"] for g in v["gaps"])) < 1e-9


def test_display_path_passes_through_every_usable_fix_in_order():
    for cid in CASES:
        td, m = _load(cid, "track_display.json"), _load(cid, "manifest.json")
        fixes = {t["vessel_key"]: t["fixes"] for t in m["tracks"]}
        for v in td["vessels"]:
            on_fix = [p for p in v["display_path"] if p[3]]
            assert [p[2] for p in on_fix] == [f["t_utc"] for f in fixes[v["vessel_key"]]]
            assert all((p[0], p[1]) == (round(f["lon"], 5), round(f["lat"], 5))
                       for p, f in zip(on_fix, fixes[v["vessel_key"]]))
            times = [_t(p[2]) for p in v["display_path"]]
            assert times == sorted(times)
            assert v["n_display_points"] == len(v["display_path"])


def _track(minutes, lat=19.0):
    t0 = datetime.fromisoformat("2026-09-10T00:00:00+00:00")
    return [{"t_utc": (t0 + timedelta(minutes=m)).isoformat(), "lon": 72.5 + 0.01 * i,
             "lat": lat + 0.002 * i * i, "sog_knots": 8.0, "cog_deg": 90.0,
             "interpolated": False} for i, m in enumerate(minutes)]


def test_display_path_never_bridges_an_internal_gap():
    fixes = _track([0, 30, 60, 90, 240, 270, 300])        # 150-minute hole
    ws = datetime.fromisoformat("2026-09-09T23:00:00+00:00")
    we = datetime.fromisoformat("2026-09-10T06:00:00+00:00")
    gaps, usable, threshold = find_gaps(fixes, ws, we)
    internal = [g for g in gaps if g["kind"] == "internal"]
    assert threshold == 60.0 and len(internal) == 1
    a, b = _t(internal[0]["start_utc"]), _t(internal[0]["end_utc"])
    path, _dev = display_path(usable, gaps, 19.0)
    assert not [p for p in path if a < _t(p[2]) < b], "curve drawn across a gap"


def test_sentinel_position_counts_as_missing():
    fixes = _track([0, 30, 60, 90, 120])
    fixes[2] = {**fixes[2], "lat": 91.0}                  # ITU "position unavailable"
    ws = datetime.fromisoformat("2026-09-10T00:00:00+00:00")
    we = datetime.fromisoformat("2026-09-10T02:00:00+00:00")
    gaps, usable, _thr = find_gaps(fixes, ws, we)
    assert len(usable) == 4
    assert all(f["lat"] != 91.0 for f in usable)


def test_vessel_type_is_not_invented():
    for cid in CASES:
        for v in _load(cid, "track_display.json")["vessels"]:
            assert v["vessel_type"] is None
            assert v["vessel_type_source"].startswith("not reported")


def test_track_display_endpoint_equals_case_section():
    client = TestClient(app)
    case = client.get("/api/incidents/case_0001/case").json()
    assert case["track_display"] == client.get("/api/incidents/case_0001/track-display").json()
''')

# ----------------------------------------------------------------- pipeline --

edit("scripts/run_pipeline.py",
'''    generate -> detect + characterise -> historical mapping -> naive baseline
''',
'''    generate -> detect + characterise -> historical mapping -> track display
             -> naive baseline
''')

edit("scripts/run_pipeline.py",
'''from slicktrace_core.synth_generator import CASE_PLAN, generate_all
''',
'''from slicktrace_core.synth_generator import CASE_PLAN, generate_all
from slicktrace_core.track_display import run_track_display
''')

edit("scripts/run_pipeline.py",
'''        ("historical_mapping", lambda: run_historical_mapping(case_dir)),
''',
'''        ("historical_mapping", lambda: run_historical_mapping(case_dir)),
        ("track_display", lambda: run_track_display(case_dir)),
''')

# ----------------------------------------------------------- case contract --

edit("slicktrace_core/case_contract.py",
'''SCHEMA_VERSION = "2"   # 2: adds replay_footprints and forecast_contours
''',
'''SCHEMA_VERSION = "3"   # 2: replay_footprints, forecast_contours; 3: track_display
''')

edit("slicktrace_core/case_contract.py",
'''# ------------------------------------------------------------------- case --

class Case(_Strict):
    schema_version: Literal["2"] = SCHEMA_VERSION
''',
'''# ---------------------------------------------------------- track display --

class TrackGap(_Strict):
    kind: Literal["leading", "internal", "trailing", "no_fixes"]
    start_utc: IsoUtc
    end_utc: IsoUtc
    hours: float


class DisplayVessel(_Strict):
    vessel_key: str
    vessel_type: None = None          # never inferred; see vessel_type_source
    vessel_type_source: str
    n_fixes: int
    n_usable_fixes: int
    internal_gap_threshold_minutes: Optional[float] = None
    gaps: list[TrackGap]
    hours_without_position: float
    n_display_points: int
    max_display_deviation_m: int
    display_path: list[tuple[float, float, IsoUtc, bool]]


class TrackDisplay(_Strict):
    incident_id: str
    ais_window_start_utc: IsoUtc
    ais_window_end_utc: IsoUtc
    gap_rule: str
    display_rule: str
    vessels: list[DisplayVessel]


# ------------------------------------------------------------------- case --

class Case(_Strict):
    schema_version: Literal["3"] = SCHEMA_VERSION
''')

edit("slicktrace_core/case_contract.py",
'''    forecast_contours: Optional[ForecastContours] = None

    @model_validator(mode="after")
''',
'''    forecast_contours: Optional[ForecastContours] = None
    track_display: Optional[TrackDisplay] = None

    @model_validator(mode="after")
''')

edit("slicktrace_core/case_contract.py",
'''                     "next_observation", "replay_footprints", "forecast_contours"):
''',
'''                     "next_observation", "replay_footprints", "forecast_contours",
                     "track_display"):
''')

edit("slicktrace_core/case_contract.py",
'''                raise ValueError("forecast contours do not cover the forecast horizons")
        return self
''',
'''                raise ValueError("forecast contours do not cover the forecast horizons")

        if self.track_display is not None:
            if [v.vessel_key for v in self.track_display.vessels] != keys:
                raise ValueError("track display does not describe exactly the case's vessels")
        return self
''')

edit("slicktrace_core/case_contract.py",
'''        "forecast_contours": _load(case_dir, "forecast_contours.json"),
    })
''',
'''        "forecast_contours": _load(case_dir, "forecast_contours.json"),
        "track_display": _load(case_dir, "track_display.json"),
    })
''')

# -------------------------------------------------------------------- API --

edit("backend/app.py",
'''    return _require(incident_id, "forecast_contours.json", "forecast contours")
''',
'''    return _require(incident_id, "forecast_contours.json", "forecast contours")


@app.get("/api/incidents/{incident_id}/track-display")
def get_track_display(incident_id: str):
    """Per-vessel gap windows and a rendering-only smoothed path."""
    return _require(incident_id, "track_display.json", "track display")
''')

# --------------------------------------------------------- verifier and CI --

edit("scripts/verify_document_claims.py",
'''check("223 tests pass", "223 passed" in t, True)
''',
'''check("230 tests pass", "230 passed" in t, True)
''')

edit(".github/workflows/tests.yml",
'''            'data/cases/*/forecast_contours.json' \\
''',
'''            'data/cases/*/forecast_contours.json' \\
            'data/cases/*/track_display.json' \\
''')

# -------------------------------------------------------------- changelog --

edit("CHANGELOG.md",
'''unchanged. Six tests added; 223 pass.
''',
'''unchanged. Six tests added; 223 pass.

**Track display: gap windows, rendering-only paths, no invented vessel type.**
A new pipeline stage writes `track_display.json`. Per vessel it records every
window inside the declared AIS window with no usable position report (leading,
internal, trailing), counting sentinel positions as missing and wording them as
no position reported rather than as an outage; a test holds the leading and
trailing windows to exactly the hours the hindcast marks `no_data`. It adds a
centripetal Catmull-Rom path through the fixes for drawing, never across a gap,
with its largest departure from the straight segments stated; every analysis
still uses the original fixes. Vessel type is `null` with the reason: an MMSI
does not encode ship type and the source carries no AIS static data. Served at
`/track-display` and carried in the Case contract, schema 3.
`scripts/track_summary.py` prints the per-case table. Seven tests added; 230 pass.
''')


# ------------------------------------------------------------------ apply --

def main() -> int:
    if not os.path.isfile("slicktrace_core/hindcast.py"):
        print("Run this from the slick-trace repository root.", file=sys.stderr)
        return 2
    with open("slicktrace_core/hindcast.py", encoding="utf-8") as f:
        if "def vessel_hourly_states(" not in f.read() or not os.path.exists("slicktrace_core/display_geometry.py"):
            print("ABORT: patches 01-03 must be applied first.",
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
    print(f"patch 04: {applied} edits applied, {skipped} already in place, "
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
