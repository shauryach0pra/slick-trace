"""
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
        f.write("\n")
    return out
