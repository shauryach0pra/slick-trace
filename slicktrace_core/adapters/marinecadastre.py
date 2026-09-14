"""
Read MarineCadastre AIS CSV into this project's schema.

MarineCadastre is the AIS source the problem statement names, and it publishes
US coastal AIS as daily CSV with a stable column set. This reads that format
into the project's track structure, which is the whole of the "adapter, not a
rewrite" claim the README makes: every pipeline stage downstream reads the
schema, not the source format, so a working reader is the entire integration.

WHAT IT DOES WITH BAD ROWS
    Drops them, and counts what it dropped. AIS is noisy at the source: rows
    arrive with reserved "unavailable" sentinels, with positions outside the
    valid range, with timestamps that do not parse. Silently coercing those into
    numbers is how a vessel ends up at latitude 91 doing 102 knots, so each
    class of rejection is counted and returned with the tracks. A caller that
    wants to know how much of a file was usable can find out.

    Field validation itself lives in `slicktrace_core.ais_quality` and is shared
    with the synthetic path, so both go through the same sentinel checks.

WHAT IT DOES NOT DO
    It does not interpolate, resample, or fill gaps. A track is the fixes that
    were broadcast, with the intervals between them left as intervals -
    assumption A6 bounds interpolation to a documented motion bound, and doing
    it here would hide the gap from the stage responsible for reasoning about
    it.

    It does not assign `vessel_key` any meaning beyond the MMSI in the file.
    Assumption A8 records that identity is time-bounded and an MMSI can be
    reassigned; resolving that needs a registry this reader does not have.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Iterable

from slicktrace_core.ais_quality import validate_fix

# MarineCadastre headers, with the aliases their older exports use.
COLUMN_ALIASES = {
    "mmsi": ("MMSI", "mmsi"),
    "t_utc": ("BaseDateTime", "basedatetime", "TIME", "timestamp"),
    "lat": ("LAT", "lat", "Latitude"),
    "lon": ("LON", "lon", "Longitude"),
    "sog": ("SOG", "sog"),
    "cog": ("COG", "cog"),
    "heading": ("Heading", "heading", "TrueHeading"),
    "name": ("VesselName", "vesselname", "NAME"),
    "imo": ("IMO", "imo"),
}


def _pick(header: list[str], names: tuple[str, ...]) -> str | None:
    lower = {h.strip().lower(): h for h in header}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def _parse_time(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _num(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def read_marinecadastre(source: str | Iterable[str]) -> dict:
    """Parse MarineCadastre CSV text (or a path) into tracks plus a reject report."""
    # Treat a string as a path only if it actually is one. Sniffing for a
    # newline fails on empty input and on a single-line file read into memory.
    import os as _os
    if isinstance(source, str) and source and "\n" not in source and _os.path.exists(source):
        with open(source, newline="", encoding="utf-8") as fh:
            return _read(fh)
    if isinstance(source, str):
        return _read(io.StringIO(source))
    return _read(source)


def _read(fh) -> dict:
    reader = csv.reader(fh)
    try:
        header = next(reader)
    except StopIteration:
        return {"tracks": [], "rejected": {}, "n_rows": 0,
                "note": "empty file: no header row"}

    cols = {k: _pick(header, v) for k, v in COLUMN_ALIASES.items()}
    missing = [k for k in ("mmsi", "t_utc", "lat", "lon") if cols[k] is None]
    if missing:
        return {"tracks": [], "rejected": {}, "n_rows": 0,
                "note": f"required columns absent: {', '.join(missing)}"}

    idx = {k: header.index(v) for k, v in cols.items() if v is not None}
    by_mmsi: dict[str, dict] = {}
    rejected = {"unparsable_time": 0, "unparsable_position": 0,
                "position_out_of_range": 0, "sentinel_position": 0, "short_mmsi": 0}
    n_rows = 0

    for row in reader:
        n_rows += 1
        if len(row) <= max(idx.values()):
            rejected["unparsable_position"] += 1
            continue

        mmsi = row[idx["mmsi"]].strip()
        if len(mmsi) != 9 or not mmsi.isdigit():
            rejected["short_mmsi"] += 1
            continue

        t = _parse_time(row[idx["t_utc"]])
        if t is None:
            rejected["unparsable_time"] += 1
            continue

        lat, lon = _num(row[idx["lat"]]), _num(row[idx["lon"]])
        if lat is None or lon is None:
            rejected["unparsable_position"] += 1
            continue

        fix = {"t_utc": t.isoformat(), "lat": lat, "lon": lon,
               "sog_knots": _num(row[idx["sog"]]) if "sog" in idx else None,
               "cog_deg": _num(row[idx["cog"]]) if "cog" in idx else None,
               "interpolated": False}
        if "heading" in idx:
            fix["heading_deg"] = _num(row[idx["heading"]])

        v = validate_fix(fix)
        if "lat" in v["fields_unavailable"] or "lon" in v["fields_unavailable"]:
            rejected["sentinel_position"] += 1
            continue
        if not v["usable_position"]:
            rejected["position_out_of_range"] += 1
            continue
        # A sentinel in speed or course is not a reason to drop the position;
        # the field is recorded as unavailable and the fix is kept.
        for field in v["fields_unavailable"]:
            fix[field] = None

        rec = by_mmsi.setdefault(mmsi, {
            "vessel_key": mmsi, "mmsi": mmsi,
            "name": row[idx["name"]].strip() if "name" in idx and len(row) > idx["name"] else None,
            "imo": row[idx["imo"]].strip() if "imo" in idx and len(row) > idx["imo"] else None,
            "fixes": [],
            "provenance": {"status": "OBSERVED", "source": "MarineCadastre AIS CSV"},
        })
        rec["fixes"].append(fix)

    tracks = list(by_mmsi.values())
    for t in tracks:
        t["fixes"].sort(key=lambda f: f["t_utc"])

    return {
        "tracks": tracks,
        "n_rows": n_rows,
        "n_tracks": len(tracks),
        "n_fixes": sum(len(t["fixes"]) for t in tracks),
        "rejected": {k: v for k, v in rejected.items() if v},
        "note": ("Rows are dropped rather than repaired, and each class of rejection is "
                 "counted. Speed and course sentinels do not drop a fix - the field is "
                 "recorded as unavailable and the position is kept. No interpolation is "
                 "performed here; gaps stay gaps."),
    }
