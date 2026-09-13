"""AIS sentinel handling.

These tests exist because none of this repository's own data triggers the
validator: the generator produces clean values. A guard that is never exercised
by the data it guards is a guard nobody has checked, so it is checked here with
the reserved values themselves.
"""
import pytest

from slicktrace_core.ais_quality import validate_fix, validate_track


def _fix(**kw):
    base = {"sog_knots": 12.0, "cog_deg": 90.0, "lat": 19.0, "lon": 72.0}
    base.update(kw)
    return base


@pytest.mark.parametrize("field,value", [
    ("sog_knots", 102.3),
    ("cog_deg", 360.0),
    ("heading_deg", 511),
])
def test_reserved_value_marks_field_unavailable_not_data(field, value):
    """A sentinel must never be read as a measurement."""
    v = validate_fix(_fix(**{field: value}))
    assert field in v["fields_unavailable"]
    assert not v["flags"], "a documented sentinel is not an error"


def test_unavailable_position_is_not_usable():
    v = validate_fix(_fix(lat=91.0, lon=181.0))
    assert set(v["fields_unavailable"]) == {"lat", "lon"}
    assert v["usable_position"] is False


def test_implausible_speed_is_flagged_but_not_treated_as_sentinel():
    v = validate_fix(_fix(sog_knots=85.0))
    assert "sog_implausible_for_a_vessel" in v["flags"]
    assert v["fields_unavailable"] == []


def test_negative_speed_is_flagged():
    assert "sog_negative" in validate_fix(_fix(sog_knots=-3.0))["flags"]


def test_out_of_range_course_is_flagged():
    assert "cog_outside_range" in validate_fix(_fix(cog_deg=400.0))["flags"]


def test_clean_fix_produces_nothing():
    v = validate_fix(_fix())
    assert v["flags"] == [] and v["fields_unavailable"] == []


def test_track_summary_counts_rather_than_passes_or_fails():
    """Two bad fixes in two hundred is usable; two hundred is not. A boolean
    cannot distinguish them, so the summary carries counts."""
    t = {"vessel_key": "419000001",
         "fixes": [_fix(), _fix(sog_knots=102.3), _fix(sog_knots=-1.0)]}
    s = validate_track(t)
    assert s["n_fixes"] == 3
    assert s["n_fixes_flagged"] == 1
    assert s["fields_unavailable"]["sog_knots"] == 1
    assert s["clean"] is False


def test_real_case_tracks_are_clean():
    """The generator produces clean values; if this ever fails the generator
    changed, not the validator."""
    import json
    m = json.load(open("data/cases/case_0001/manifest.json"))
    for t in m["tracks"]:
        assert validate_track(t)["clean"], f"{t['vessel_key']} no longer clean"
