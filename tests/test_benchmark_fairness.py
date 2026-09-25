"""
The benchmark is fair and its geography is real.

Two properties the generator used to lack, locked in here so they cannot
quietly return:

  * no rule that ignores physics can find the source. The old generator gave
    the true source a track length, start time and speed no other vessel had;
    bookkeeping alone named it in 7 of 7 cases.
  * everything sits where it could physically be. The old coastline was
    invented about 19 km east of the real one, so on real imagery a synthetic
    mangrove reserve lay over the city and part of a slick lay on land.
"""
import json
import math
import os
from datetime import datetime, timedelta

import numpy as np
import pytest
from PIL import Image

from slicktrace_core.geography import coastline_for_bbox, land_mask, on_land
from slicktrace_core.synth_generator import CASE_PLAN, IDENTIFIABLE_KM, _interp

ROOT = os.path.join("data", "cases")
CASES = [cid for cid, _f, _s in CASE_PLAN]


def _load(cid, name):
    path = os.path.join(ROOT, cid, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated - run scripts/run_pipeline.py --regenerate")
    with open(path) as f:
        return json.load(f)


def _km(a, b):
    dx = (a[0] - b[0]) * 111.0 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, (a[1] - b[1]) * 111.0)


# ------------------------------------------------------------- the land test

@pytest.mark.parametrize("name, lon, lat, land", [
    ("Arabian Sea off Mumbai", 72.50, 19.00, False),
    ("Dadar, Mumbai city", 72.842, 19.018, True),
    ("Mumbai harbour", 72.90, 18.95, False),
    ("Navi Mumbai", 73.03, 19.05, True),
])
def test_land_test_on_known_places(name, lon, lat, land):
    assert on_land(lon, lat) is land, name


def test_no_coastline_means_no_land_not_dry_sea():
    assert on_land(72.84, 19.02, coastline=[]) is False


# ---------------------------------------------------------- real geography

@pytest.mark.parametrize("cid", CASES)
def test_case_coastline_is_the_real_one(cid):
    m = _load(cid, "manifest.json")
    assert m["coastline"] == coastline_for_bbox(m["bbox"])


@pytest.mark.parametrize("cid", CASES)
def test_no_vessel_fix_is_on_land(cid):
    m = _load(cid, "manifest.json")
    on = [(t["vessel_key"], f["t_utc"]) for t in m["tracks"] for f in t["fixes"]
          if on_land(f["lon"], f["lat"], m["coastline"])]
    assert not on, f"fixes on land: {on[:3]}"


@pytest.mark.parametrize("cid", CASES)
def test_truth_slick_is_entirely_at_sea(cid):
    m = _load(cid, "manifest.json")
    mask = np.array(Image.open(m["mask_groundtruth_path"])) > 127
    land = land_mask(m["bbox"], mask.shape, m["coastline"])
    assert mask.any() and not (mask & land).any()


@pytest.mark.parametrize("cid", CASES)
def test_sensitive_areas_sit_where_they_would(cid):
    m = _load(cid, "manifest.json")
    areas = {a["kind"]: a["polygon"] for a in m["sensitive_areas"]}
    assert not any(on_land(x, y, m["coastline"]) for x, y in areas["fishery"]), \
        "a fishing ground is at sea"
    shore = [on_land(x, y, m["coastline"]) for x, y in areas["mangrove"]]
    assert any(shore) and not all(shore), "a mangrove fringe straddles the shoreline"


# --------------------------------------------------------- fair bookkeeping

@pytest.mark.parametrize("cid", CASES)
def test_reported_speed_is_the_vessels_actual_motion(cid):
    """A reported 9.5 kn on a vessel moving at 0.2 kn singled out the source."""
    m = _load(cid, "manifest.json")
    for t in m["tracks"]:
        f = t["fixes"]
        for a, b in zip(f, f[1:]):
            hours = (datetime.fromisoformat(b["t_utc"]) - datetime.fromisoformat(a["t_utc"])).total_seconds() / 3600
            if abs(hours - 0.5) > 1e-6:
                continue                      # a gap in the published fixes
            actual_kn = _km((a["lon"], a["lat"]), (b["lon"], b["lat"])) / hours / 1.852
            assert abs(a["sog_knots"] - actual_kn) <= 0.15, (t["vessel_key"], a["t_utc"])


@pytest.mark.parametrize("cid", CASES)
def test_innocents_are_physically_identifiable(cid):
    """No innocent vessel is at the release while it happens. Such a vessel is
    indistinguishable from the polluter by drift physics, so a case containing
    one would test nothing."""
    truth, m = _load(cid, "truth.json"), _load(cid, "manifest.json")
    src = truth["true_vessel_key"]
    if src is None:
        pytest.skip("source absent from the manifest; checked when generated")
    tracks = {t["vessel_key"]: t["fixes"] for t in m["tracks"]}
    rs = datetime.fromisoformat(truth["release_start_utc"])
    steps = int(round(truth["release_duration_hours"] * 2))
    for key, fixes in tracks.items():
        if key == src:
            continue
        for i in range(steps + 1):
            t = rs + i * timedelta(minutes=30)
            a, b = _interp(fixes, t), _interp(tracks[src], t)
            if a is not None and b is not None:
                assert _km(a, b) >= IDENTIFIABLE_KM - 0.05, (key, t.isoformat())


def test_no_bookkeeping_rule_nearly_finds_the_source():
    """The leak audit may flag a rule by chance at 3 of 7. A rule at 6 or 7 of 7
    is a leak by any reading; the old generator had four."""
    path = os.path.join("docs", "validation_report.json")
    if not os.path.exists(path):
        pytest.skip("no validation report - run scripts/run_validation.py")
    leak = json.load(open(path)).get("leak_audit")
    assert leak and leak["rules"], "validation report carries no leak audit"
    worst = max(leak["rules"], key=lambda r: r["hits"])
    assert worst["hits"] < 6, f"{worst['rule']} names the source in {worst['hits']}/{worst['n']}"


# ---------------------------------------------------------------- stranding

@pytest.mark.parametrize("cid", CASES)
def test_stranded_oil_only_accumulates(cid):
    """Oil that reaches the coast stays there, so shoreline contact never falls."""
    fc = _load(cid, "forecast_result.json")
    shore = [h["modelled_shoreline_fraction"] for h in fc["horizons"]]
    assert all(b >= a for a, b in zip(shore, shore[1:])), shore
