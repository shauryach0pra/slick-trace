"""
MMSI structure: validity, category and flag state.

An MMSI is not an opaque identifier. Its first three digits are the Maritime
Identification Digits, assigned by the ITU to a flag administration, and the
leading digit distinguishes a ship station from a coast station, an aircraft, a
navigational aid or a search-and-rescue transmitter. Reading that structure
costs nothing and tells an investigator which administration would have to be
approached, and whether the identifier is a ship at all.

WHAT THIS DOES NOT ESTABLISH
    Flag state is where the vessel is registered. It is not where it operates,
    who owns it, who was aboard, or any indication of conduct. It is a lookup on
    a number the vessel broadcasts about itself, and a vessel that misreports
    its MMSI misreports this too. It is provenance, not evidence, and it is
    never an input to ranking: class and registry are contextual at most, and
    physical compatibility drives candidate retention.

    Assumption A8 already records that identity is time-bounded: an MMSI can be
    reassigned, so a flag resolved today may not describe the vessel that
    carried it at acquisition time. The validity interval on the track governs;
    this adds structure, not certainty.

COVERAGE
    The table below is partial by design - the maritime nations relevant to the
    Indian Ocean and the major open registries. An unlisted MID returns the MID
    itself with flag_state=None rather than a guess, so an unknown
    administration reads as unknown rather than as absent.
"""
from __future__ import annotations

MID_TABLE: dict[str, str] = {
    "419": "India", "417": "Sri Lanka", "405": "Bangladesh", "463": "Pakistan",
    "422": "Iran", "403": "Saudi Arabia", "470": "United Arab Emirates",
    "471": "United Arab Emirates", "425": "Iraq", "447": "Oman",
    "408": "Bahrain", "466": "Qatar",
    "525": "Indonesia", "533": "Malaysia", "567": "Thailand", "574": "Vietnam",
    "563": "Singapore", "564": "Singapore", "565": "Singapore", "566": "Singapore",
    "412": "China", "413": "China", "414": "China",
    "431": "Japan", "432": "Japan", "440": "South Korea", "441": "South Korea",
    "351": "Panama", "352": "Panama", "353": "Panama", "354": "Panama",
    "355": "Panama", "356": "Panama", "357": "Panama", "370": "Panama",
    "371": "Panama", "372": "Panama", "373": "Panama", "374": "Panama",
    "636": "Liberia", "637": "Liberia", "538": "Marshall Islands",
    "215": "Malta", "229": "Malta", "248": "Malta", "249": "Malta", "256": "Malta",
    "477": "Hong Kong", "319": "Cayman Islands",
    "311": "Bahamas", "312": "Bahamas", "313": "Bahamas", "314": "Bahamas",
    "316": "Canada",
    "232": "United Kingdom", "233": "United Kingdom",
    "234": "United Kingdom", "235": "United Kingdom",
    "338": "United States", "366": "United States", "367": "United States",
    "368": "United States", "369": "United States",
    "244": "Netherlands", "245": "Netherlands", "246": "Netherlands",
    "211": "Germany", "218": "Germany",
    "226": "France", "227": "France", "228": "France", "247": "Italy",
    "224": "Spain", "225": "Spain",
    "209": "Cyprus", "210": "Cyprus", "212": "Cyprus",
    "271": "Turkey", "273": "Russia", "240": "Greece", "241": "Greece",
}

CATEGORY_BY_LEAD: dict[str, str] = {
    "0": "group ship station or coast station",
    "1": "SAR aircraft",
    "8": "handheld VHF / diver radio",
    "9": "navigational aid, AIS-SART, EPIRB or MOB device",
}


def parse_mmsi(mmsi: str | None) -> dict:
    """Structure of an MMSI. Never raises; an unusable input is reported as such."""
    out: dict = {"mmsi": mmsi, "valid": False, "mid": None,
                 "flag_state": None, "category": None, "note": ""}
    if not mmsi:
        out["note"] = "no MMSI on this track"
        return out
    s = str(mmsi).strip()
    if not s.isdigit() or len(s) != 9:
        out["note"] = "not nine digits - not a well-formed MMSI"
        return out

    lead = s[0]
    if lead in CATEGORY_BY_LEAD:
        out["valid"] = True
        out["category"] = CATEGORY_BY_LEAD[lead]
        out["note"] = ("structurally valid, but this is not a ship station: "
                       "it should not appear as an attribution candidate")
        return out

    if lead in "234567":
        out["valid"] = True
        out["category"] = "ship station"
        out["mid"] = s[:3]
        out["flag_state"] = MID_TABLE.get(s[:3])
        out["note"] = ("flag state is the administration of registry - not "
                       "operating area, ownership or conduct, and never an "
                       "input to ranking")
        if out["flag_state"] is None:
            out["note"] += "; MID not in this table, reported as unresolved"
        return out

    out["note"] = f"leading digit {lead} is not an assigned MMSI category"
    return out


def annotate_tracks(tracks: list[dict]) -> list[dict]:
    """Attach MMSI structure to each track, in place, returning the same list."""
    for t in tracks:
        t["identity"] = parse_mmsi(t.get("mmsi") or t.get("vessel_key"))
    return tracks
