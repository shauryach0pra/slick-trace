"""Track display: gap windows, rendering-only paths, and no invented vessel type."""

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


def test_vessel_type_comes_from_static_data_not_inference():
    """Type is what the vessel's AIS static message reports, labelled with its
    source; with no static data it stays 'not reported' - never inferred."""
    for cid in CASES:
        static = {t["vessel_key"]: t.get("ship_type") for t in _load(cid, "manifest.json")["tracks"]}
        for v in _load(cid, "track_display.json")["vessels"]:
            assert v["vessel_type"] == static[v["vessel_key"]]
            if v["vessel_type"] is None:
                assert v["vessel_type_source"].startswith("not reported")
            else:
                assert v["vessel_type_source"] == "AIS static message 5 (synthetic)"


def test_track_display_endpoint_equals_case_section():
    client = TestClient(app)
    case = client.get("/api/incidents/case_0001/case").json()
    assert case["track_display"] == client.get("/api/incidents/case_0001/track-display").json()
