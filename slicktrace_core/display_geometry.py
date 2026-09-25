"""
Display geometry: the outlines the interface draws, computed in the pipeline.

Two artifacts, each written by the stage whose computation it shows:

  replay_footprints.json   (attribution stage) For every ranked candidate, the
      footprint its best release hypothesis produces under the nominal forcing
      member, rasterised exactly as it was scored, traced to lon/lat outlines.
      That is one member of six: mean_iou in attribution_result.json averages
      all six, so the nominal_iou stored here differs from it and says so.

  forecast_contours.json   (forecast stage) For each forecast horizon, the
      50/75/90% density contours over the same particles that produced the
      horizon's area and exposure figures.

Why here and not in the interface: a map that recomputes a footprint is a
second implementation of the physics, and the first is the one that was
validated. The interface draws these outlines and computes nothing.

Coordinates: a raster outline is traced at the 0.5 level between cells, and
cell (col, row) spans the part of the bbox the rasteriser assigns a particle
to, so traced edges fall on cell boundaries. Rounded to 5 decimal places
(about 1 m), and written compactly like envelope_timeline.json.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import numpy as np

from slicktrace_core.envelope_density import density_contours, rings_of

DECIMALS = 5


def _r(x: float) -> float:
    return round(float(x), DECIMALS)


def _write(case_dir: str, name: str, obj: dict) -> None:
    with open(os.path.join(case_dir, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"))
        f.write("\n")


def mask_outlines(mask: np.ndarray, bbox: dict) -> list[list[list[float]]]:
    """Every outline of a binary raster, as lon/lat rings on cell edges."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h, w = mask.shape
    padded = np.pad(mask.astype(float), 1)   # closes rings that touch the frame
    fig, ax = plt.subplots()
    try:
        rings = rings_of(ax.contour(padded, levels=[0.5]))
    finally:
        plt.close(fig)
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    lat_span = bbox["max_lat"] - bbox["min_lat"]
    # padded index x is cell x - 1; the edge between cells c-1 and c sits at
    # index c - 0.5, i.e. at lon min + c / w * span
    return [[[_r(bbox["min_lon"] + (x - 0.5) / w * lon_span),
              _r(bbox["max_lat"] - (y - 0.5) / h * lat_span)] for x, y in ring]
            for ring in rings]


def write_replay_footprints(case_dir: str, manifest: dict, ranking: list, tracks_by_key: dict,
                            u: float, v: float, acquired, bbox: dict,
                            observed_mask: np.ndarray) -> dict:
    from slicktrace_core.attribution import (ENSEMBLE_VARIANTS, ReleaseHypothesisSpec,
                                             score_fit, simulate_hypothesis)
    from slicktrace_core.hindcast import _interp_track_position, _parse

    def position(fixes, t):
        p = _interp_track_position(fixes, t)
        return None if p is None else [_r(p[0]), _r(p[1])]

    rows = []
    for rank, r in enumerate(ranking, start=1):
        fixes = tracks_by_key[r["vessel_key"]]
        start = _parse(r["release_start"])
        hyp = ReleaseHypothesisSpec(r["candidate_id"], r["vessel_key"], start,
                                    r["duration_hours"], r["is_continuous"])
        # variant 0 with seed 0 is exactly the nominal member run_attribution scored
        pred = simulate_hypothesis(hyp, fixes, u, v, ENSEMBLE_VARIANTS[0], acquired, bbox, seed=0)
        fit = score_fit(pred, observed_mask, min(hyp.duration_hours / 4.0, 1.0))
        rows.append({
            "vessel_key": r["vessel_key"],
            "candidate_id": r["candidate_id"],
            "rank": rank,
            "release_start": r["release_start"],
            "duration_hours": r["duration_hours"],
            "is_continuous": r["is_continuous"],
            "release_start_position": position(fixes, start),
            "release_end_position": position(fixes, start + timedelta(hours=r["duration_hours"])),
            "nominal_iou": round(fit["iou"], 4),
            "polygons": mask_outlines(pred, bbox),
        })
    out = {
        "incident_id": manifest["incident_id"],
        "variant": "nominal",
        "scored_against": ("the generator mask (mask_groundtruth.png) that forward replay "
                           "is scored against, not the detector polygon"),
        "coordinate_convention": ("outlines lie on the edges of the scene's pixel cells, the "
                                  "cells the rasteriser assigns particles to"),
        "footprints": rows,
        "note": ("One forcing member of six. mean_iou in attribution_result.json averages "
                 "all six members, so nominal_iou differs from it; both come from the same "
                 "rasterisation. A release position is null where the track has no fix "
                 "bracketing that time."),
    }
    _write(case_dir, "replay_footprints.json", out)
    return out


def write_forecast_contours(case_dir: str, forecast: dict, particles_by_horizon: list) -> dict:
    horizons = []
    for h, (lon, lat) in zip(forecast["horizons"], particles_by_horizon):
        horizons.append({
            "horizon_hours": h["horizon_hours"],
            "valid_utc": h["valid_utc"],
            "density_contours": [{"fraction": c["fraction"],
                                  "polygons": [[[_r(x), _r(y)] for x, y in ring]
                                               for ring in c["polygons"]]}
                                 for c in density_contours(lon, lat)],
        })
    out = {
        "incident_id": forecast["incident_id"],
        "issued_from_utc": forecast["issued_from_utc"],
        "n_particles_per_horizon": forecast["horizons"][0]["particles"] if forecast["horizons"] else 0,
        "coordinate_decimals": DECIMALS,
        "horizons": horizons,
        "note": ("Contours enclose 50/75/90% of the estimated density over the particles "
                 "behind each horizon's figures. envelope_area_km2 in forecast_result.json "
                 "counts grid cells holding any particle, so it exceeds the area inside the "
                 "90% contour by construction. Modelled exposure, not predicted damage."),
    }
    _write(case_dir, "forecast_contours.json", out)
    return out
