"""MarineCadastre AIS CSV adapter.

The problem statement names MarineCadastre as the AIS source. The README claims
real data is "an adapter, not a rewrite" because every stage downstream reads
the schema rather than a source format - this is the adapter that has to exist
for that claim to be true, and these tests are what make it checkable.
"""
from slicktrace_core.adapters.marinecadastre import read_marinecadastre

HEADER = "MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,IMO\n"
GOOD = "419336692,2026-09-10T04:30:00,19.0552,72.9466,12.2,347.5,348,ATLAS,IMO9123456\n"


def test_reads_a_well_formed_row():
    r = read_marinecadastre(HEADER + GOOD)
    assert r["n_tracks"] == 1 and r["n_fixes"] == 1
    t = r["tracks"][0]
    assert t["vessel_key"] == "419336692" and t["name"] == "ATLAS"
    assert t["provenance"]["status"] == "OBSERVED"


def test_groups_fixes_by_vessel_and_sorts_by_time():
    rows = (HEADER
            + "419336692,2026-09-10T04:40:00,19.06,72.94,12.0,346,347,ATLAS,\n"
            + GOOD)
    t = read_marinecadastre(rows)["tracks"][0]
    assert len(t["fixes"]) == 2
    assert t["fixes"][0]["t_utc"] < t["fixes"][1]["t_utc"]


def test_speed_sentinel_nulls_the_field_but_keeps_the_position():
    """A speed sensor with nothing to report does not invalidate a good fix."""
    row = "419824090,2026-09-10T04:30:00,19.18,72.29,102.3,360.0,511,BEACON,\n"
    r = read_marinecadastre(HEADER + row)
    fix = r["tracks"][0]["fixes"][0]
    assert fix["sog_knots"] is None and fix["cog_deg"] is None
    assert fix["lat"] == 19.18 and fix["lon"] == 72.29


def test_sentinel_position_is_dropped_and_counted():
    row = "999999999,2026-09-10T04:30:00,91.0,181.0,3.0,10.0,12,GHOST,\n"
    r = read_marinecadastre(HEADER + row)
    assert r["n_tracks"] == 0
    assert r["rejected"]["sentinel_position"] == 1


def test_out_of_range_position_is_dropped_and_counted():
    row = "419000222,2026-09-10T04:30:00,95.0,72.5,4.0,20.0,25,BAD,\n"
    r = read_marinecadastre(HEADER + row)
    assert r["rejected"]["position_out_of_range"] == 1


def test_unparsable_time_is_dropped_and_counted():
    row = "419000111,not-a-time,19.0,72.5,4.0,20.0,25,BAD,\n"
    assert read_marinecadastre(HEADER + row)["rejected"]["unparsable_time"] == 1


def test_malformed_mmsi_is_dropped_and_counted():
    row = "12345,2026-09-10T04:30:00,19.0,72.5,4.0,20.0,25,SHORT,\n"
    assert read_marinecadastre(HEADER + row)["rejected"]["short_mmsi"] == 1


def test_rejections_are_counted_not_silent():
    """Every dropped row is attributable to a reason. A caller can tell how much
    of a file was usable."""
    rows = (HEADER + GOOD
            + "999999999,2026-09-10T04:30:00,91.0,181.0,3.0,10.0,12,GHOST,\n"
            + "419000111,not-a-time,19.0,72.5,4.0,20.0,25,BAD,\n")
    r = read_marinecadastre(rows)
    assert r["n_rows"] == 3
    assert sum(r["rejected"].values()) == 2
    assert r["n_fixes"] == 1


def test_older_column_names_are_accepted():
    alt = ("mmsi,timestamp,Latitude,Longitude,sog,cog\n"
           "419336692,2026-09-10 04:30:00,19.05,72.94,12.2,347.5\n")
    assert read_marinecadastre(alt)["n_fixes"] == 1


def test_missing_required_columns_reports_rather_than_crashes():
    r = read_marinecadastre("MMSI,SOG\n419336692,12.2\n")
    assert r["tracks"] == [] and "required columns absent" in r["note"]


def test_empty_file_is_handled():
    assert read_marinecadastre("")["tracks"] == []


def test_no_interpolation_is_performed():
    """Gaps stay gaps: A6 bounds interpolation to a documented motion bound, and
    doing it in the reader would hide the gap from the stage that reasons about
    it."""
    rows = (HEADER + GOOD
            + "419336692,2026-09-10T09:30:00,19.40,72.60,12.0,346,347,ATLAS,\n")
    fixes = read_marinecadastre(rows)["tracks"][0]["fixes"]
    assert len(fixes) == 2, "reader must not synthesise intermediate fixes"
    assert all(f["interpolated"] is False for f in fixes)
