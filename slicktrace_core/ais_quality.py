"""
AIS field validation against the values the standard reserves for "unavailable".

AIS does not omit a field it cannot supply. It transmits a documented sentinel,
and every sentinel is a number inside the plausible range of the quantity it
replaces. Speed over ground 102.3 knots is not a fast ship, it is a speed sensor
with nothing to report. Course over ground 360.0 is not due north, it is no
course. True heading 511 is no heading. Latitude 91 and longitude 181 are no
position.

A reader that treats these as data gets a vessel doing 102 knots on a heading of
511 at latitude 91, and every downstream stage inherits it: an interpolation
bound computed from an impossible speed, a track drawn off the map, a candidate
excluded for a manoeuvre it never made.

WHAT THIS DOES AND DOES NOT DO
    It flags. It does not repair. A fix carrying a sentinel has its field marked
    unavailable rather than guessed at, which is the same distinction the
    candidate states draw between `unassessed` and `excluded`: a missing
    measurement is missing, not zero and not the last known value.

    Nothing here is currently triggered by this repository's own data, because
    the generator produces clean values. That is the point of a guard: it costs
    nothing while the input is clean and it is already in place when it is not.
    The tests exercise it with the sentinels themselves.
"""
from __future__ import annotations

# ITU-R M.1371 reserved values. Each is inside the plausible range of its own
# quantity, which is exactly why a naive reader does not notice them.
SOG_UNAVAILABLE = 102.3          # knots
SOG_MAX_ENCODABLE = 102.2        # above this, only the sentinel exists
COG_UNAVAILABLE = 360.0          # degrees
HEADING_UNAVAILABLE = 511        # degrees
LAT_UNAVAILABLE = 91.0
LON_UNAVAILABLE = 181.0

# Not a sentinel, an implausibility. The fastest merchant vessels run ~25 kn;
# above 60 kn a value is a decode error or a spoof, not a ship.
SOG_IMPLAUSIBLE_ABOVE = 60.0


def validate_fix(fix: dict) -> dict:
    """Flags on one position report. Never raises, never modifies the fix."""
    flags: list[str] = []
    unavailable: list[str] = []

    sog = fix.get("sog_knots")
    if sog is not None:
        if abs(sog - SOG_UNAVAILABLE) < 0.05:
            unavailable.append("sog_knots")
        elif sog < 0:
            flags.append("sog_negative")
        elif sog > SOG_MAX_ENCODABLE:
            flags.append("sog_above_encodable_range")
        elif sog > SOG_IMPLAUSIBLE_ABOVE:
            flags.append("sog_implausible_for_a_vessel")

    cog = fix.get("cog_deg")
    if cog is not None:
        if abs(cog - COG_UNAVAILABLE) < 0.05:
            unavailable.append("cog_deg")
        elif cog < 0 or cog > 360:
            flags.append("cog_outside_range")

    hdg = fix.get("heading_deg")
    if hdg is not None:
        if int(hdg) == HEADING_UNAVAILABLE:
            unavailable.append("heading_deg")
        elif hdg < 0 or hdg >= 360:
            flags.append("heading_outside_range")

    lat, lon = fix.get("lat"), fix.get("lon")
    if lat is not None:
        if abs(lat - LAT_UNAVAILABLE) < 1e-6:
            unavailable.append("lat")
        elif lat < -90 or lat > 90:
            flags.append("lat_outside_range")
    if lon is not None:
        if abs(lon - LON_UNAVAILABLE) < 1e-6:
            unavailable.append("lon")
        elif lon < -180 or lon > 180:
            flags.append("lon_outside_range")

    return {"flags": flags, "fields_unavailable": unavailable,
            "usable_position": "lat" not in unavailable and "lon" not in unavailable
                               and not any(f.startswith(("lat_", "lon_")) for f in flags)}


def validate_track(track: dict) -> dict:
    """Per-track summary. Counts rather than a pass/fail: a track with two bad
    fixes out of two hundred is usable and a track with two hundred is not, and
    a boolean cannot tell them apart."""
    fixes = track.get("fixes") or []
    n_flagged = 0
    n_unusable = 0
    flag_counts: dict[str, int] = {}
    unavailable_counts: dict[str, int] = {}

    for f in fixes:
        v = validate_fix(f)
        if v["flags"]:
            n_flagged += 1
            for fl in v["flags"]:
                flag_counts[fl] = flag_counts.get(fl, 0) + 1
        for u in v["fields_unavailable"]:
            unavailable_counts[u] = unavailable_counts.get(u, 0) + 1
        if not v["usable_position"]:
            n_unusable += 1

    return {
        "n_fixes": len(fixes),
        "n_fixes_flagged": n_flagged,
        "n_fixes_without_usable_position": n_unusable,
        "flags": flag_counts,
        "fields_unavailable": unavailable_counts,
        "clean": n_flagged == 0 and not unavailable_counts,
        "note": ("Fields carrying a reserved 'unavailable' value are recorded as "
                 "unavailable, not substituted. Flags mark values outside the "
                 "encodable range or implausible for a vessel; neither is repaired "
                 "here, because guessing a speed is worse than not having one."),
    }


def validate_tracks(tracks: list[dict]) -> dict:
    """Fleet-level summary across every track in a case."""
    per = {t["vessel_key"]: validate_track(t) for t in tracks}
    return {
        "n_tracks": len(per),
        "n_tracks_clean": sum(1 for v in per.values() if v["clean"]),
        "total_fixes": sum(v["n_fixes"] for v in per.values()),
        "total_flagged": sum(v["n_fixes_flagged"] for v in per.values()),
        "per_track": per,
    }
