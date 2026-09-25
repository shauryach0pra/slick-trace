#!/usr/bin/env python3
"""
Patch 03 - display geometry the map needs, computed in the pipeline.

Requires patches 01 and 02. Run from the repository root:
    python3 patch_03_display_geometry.py

What it changes
  slicktrace_core/display_geometry.py   NEW. Writes replay_footprints.json (each
                                ranked candidate's nominal replayed footprint,
                                traced to lon/lat) and forecast_contours.json
                                (50/75/90% contours per forecast horizon)
  slicktrace_core/envelope_density.py   contour levels split into one ring per
                                loop; disjoint lobes were joined into one polygon
  slicktrace_core/attribution.py  attribution stage also writes replay_footprints.json
  slicktrace_core/forecast.py     forecast stage also writes forecast_contours.json
  slicktrace_core/case_contract.py  schema 2: optional replay_footprints and
                                forecast_contours sections, checked against the
                                ranking and the forecast horizons
  backend/app.py                /replay-footprints and /forecast-contours
  tests/test_display_geometry.py  NEW. six tests
  scripts/verify_document_claims.py   test count 217 -> 223
  .github/workflows/tests.yml   determinism diff covers both new artifacts
  CHANGELOG.md                  entry

attribution_result.json and forecast_result.json are unchanged byte for byte.

Safety: identical to patches 01 and 02. Every anchor must match exactly once
before any file is written; a re-run changes nothing.
"""

from __future__ import annotations

import os
import sys

EDITS: list[tuple[str, str, str]] = []   # (path, old, new); old None = new file


def edit(path: str, old: str | None, new: str) -> None:
    EDITS.append((path, old, new))

# ------------------------------------------------------------- new module --

edit("slicktrace_core/display_geometry.py", None, '''"""
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
        f.write("\\n")


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
''')

# ------------------------------------------------------------- tests (new) --

edit("tests/test_display_geometry.py", None, '''"""Display geometry: outlines drawn by the map, computed and persisted by the pipeline."""

from __future__ import annotations

import json
import os

import numpy as np
from fastapi.testclient import TestClient

from backend.app import app
from slicktrace_core.display_geometry import mask_outlines
from slicktrace_core.envelope_density import density_contours
from slicktrace_core.synth_generator import CASE_PLAN

CASES = [cid for cid, _f, _s in CASE_PLAN]


def _load(cid, name):
    with open(os.path.join("data", "cases", cid, name)) as f:
        return json.load(f)


def test_mask_outline_lands_on_cell_edges():
    bbox = {"min_lon": 72.0, "max_lon": 73.0, "min_lat": 18.0, "max_lat": 19.0}
    mask = np.zeros((256, 256), dtype=np.uint8)
    mask[10:20, 20:30] = 1
    (ring,) = mask_outlines(mask, bbox)
    lons, lats = [p[0] for p in ring], [p[1] for p in ring]
    assert (min(lons), max(lons)) == (round(72.0 + 20 / 256, 5), round(72.0 + 30 / 256, 5))
    assert (max(lats), min(lats)) == (round(19.0 - 10 / 256, 5), round(19.0 - 20 / 256, 5))


def test_disjoint_lobes_are_separate_rings():
    """Regression: matplotlib returns every loop of a level in one path, and
    taking it whole drew two lobes as one polygon with a false edge between."""
    rng = np.random.default_rng(0)
    lon = np.concatenate([rng.normal(72.2, 0.01, 200), rng.normal(72.8, 0.01, 200)])
    lat = np.concatenate([rng.normal(18.5, 0.01, 200), rng.normal(19.2, 0.01, 200)])
    for level in density_contours(lon, lat):
        assert len(level["polygons"]) >= 2, level["fraction"]


def test_replay_footprints_follow_the_ranking():
    for cid in CASES:
        fp, at, m = (_load(cid, n) for n in ("replay_footprints.json",
                                              "attribution_result.json", "manifest.json"))
        assert [(f["vessel_key"], f["candidate_id"]) for f in fp["footprints"]] == \\
               [(r["vessel_key"], r["candidate_id"]) for r in at["ranking"]], cid
        b = m["bbox"]
        for f in fp["footprints"]:
            assert 0.0 <= f["nominal_iou"] <= 1.0
            for ring in f["polygons"]:
                assert len(ring) >= 4
                assert all(b["min_lon"] <= x <= b["max_lon"] and b["min_lat"] <= y <= b["max_lat"]
                           for x, y in ring), cid


def test_nominal_footprint_is_a_member_forward_replay_scored():
    """The six members' IoUs must average to the ranking's mean_iou, and the
    nominal one must be the IoU stored beside the drawn footprint."""
    from slicktrace_core.attribution import (ENSEMBLE_VARIANTS, ReleaseHypothesisSpec,
                                             score_fit, simulate_hypothesis)
    from slicktrace_core.hindcast import _parse
    from PIL import Image
    cid = "case_0001"
    m, at, fp = (_load(cid, n) for n in ("manifest.json", "attribution_result.json",
                                          "replay_footprints.json"))
    forcing = np.load(m["forcing_path"])
    observed = (np.array(Image.open(m["mask_groundtruth_path"])) > 127).astype(np.uint8)
    fixes = {t["vessel_key"]: t["fixes"] for t in m["tracks"]}
    for r, f in zip(at["ranking"], fp["footprints"]):
        hyp = ReleaseHypothesisSpec(r["candidate_id"], r["vessel_key"], _parse(r["release_start"]),
                                    r["duration_hours"], r["is_continuous"])
        ious = [score_fit(simulate_hypothesis(hyp, fixes[r["vessel_key"]], float(forcing["u"]),
                                              float(forcing["v"]), var, _parse(m["acquired_utc"]),
                                              m["bbox"], seed=vi),
                          observed, min(hyp.duration_hours / 4.0, 1.0))["iou"]
                for vi, var in enumerate(ENSEMBLE_VARIANTS)]
        assert abs(np.mean(ious) - r["mean_iou"]) < 1e-12
        assert round(ious[0], 4) == f["nominal_iou"]


def test_forecast_contours_cover_every_forecast_horizon():
    for cid in CASES:
        fc, fr = _load(cid, "forecast_contours.json"), _load(cid, "forecast_result.json")
        assert [h["horizon_hours"] for h in fc["horizons"]] == \\
               [h["horizon_hours"] for h in fr["horizons"]], cid
        for h in fc["horizons"]:
            assert [c["fraction"] for c in h["density_contours"]] == [0.5, 0.75, 0.9]
            assert all(c["polygons"] for c in h["density_contours"]), (cid, h["horizon_hours"])


def test_display_geometry_endpoints_equal_case_sections():
    client = TestClient(app)
    case = client.get("/api/incidents/case_0001/case").json()
    assert case["replay_footprints"] == \\
        client.get("/api/incidents/case_0001/replay-footprints").json()
    assert case["forecast_contours"] == \\
        client.get("/api/incidents/case_0001/forecast-contours").json()
''')

# ------------------------------------------------------- envelope density --

edit("slicktrace_core/envelope_density.py",
'''DEFAULT_LEVELS = (0.5, 0.75, 0.9)
MIN_PARTICLES = 12
''',
'''DEFAULT_LEVELS = (0.5, 0.75, 0.9)
MIN_PARTICLES = 12


def rings_of(contour_set) -> list[list[list[float]]]:
    """Every loop of a contour set as its own ring.

    Since matplotlib 3.8 each level comes back as one Path holding all of its
    loops, separated by MOVETO codes. Taking the vertices whole joins disjoint
    lobes into a single polygon with a false edge between them; splitting at
    each MOVETO keeps them apart and leaves single-loop rings unchanged.
    """
    rings = []
    for path in contour_set.get_paths():
        codes = path.codes
        starts = np.flatnonzero(codes == path.MOVETO) if codes is not None else np.array([0])
        for seg in np.split(path.vertices, starts[1:]):
            if len(seg) >= 4:
                rings.append(seg.tolist())
    return rings
''')

edit("slicktrace_core/envelope_density.py",
'''            cs = ax.contour(X, Y, Z, levels=[thr])
            rings = [p.vertices.tolist() for p in cs.get_paths()
                     if len(p.vertices) >= 4]
            out.append({"fraction": frac, "polygons": rings})
''',
'''            cs = ax.contour(X, Y, Z, levels=[thr])
            out.append({"fraction": frac, "polygons": rings_of(cs)})
''')

# ------------------------------------------------------------ attribution --

edit("slicktrace_core/attribution.py",
'''    with open(os.path.join(case_dir, "attribution_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out
''',
'''    with open(os.path.join(case_dir, "attribution_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    # The footprint each ranked candidate's best hypothesis draws under the
    # nominal forcing member, rasterised exactly as scored, for the map.
    from slicktrace_core.display_geometry import write_replay_footprints
    write_replay_footprints(case_dir, manifest, out["ranking"], tracks_by_key, u, v,
                            acquired, bbox, observed_mask)
    return out
''')

# --------------------------------------------------------------- forecast --

edit("slicktrace_core/forecast.py",
'''    horizons = []
    first_contact = {a["name"]: None for a in sensitive}
''',
'''    horizons = []
    particles_by_horizon = []  # the same particles, kept for forecast_contours.json
    first_contact = {a["name"]: None for a in sensitive}
''')

edit("slicktrace_core/forecast.py",
'''        lon_h = np.concatenate(all_lon)
        lat_h = np.concatenate(all_lat)
''',
'''        lon_h = np.concatenate(all_lon)
        lat_h = np.concatenate(all_lat)
        particles_by_horizon.append((lon_h, lat_h))
''')

edit("slicktrace_core/forecast.py",
'''    with open(os.path.join(case_dir, "forecast_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out
''',
'''    with open(os.path.join(case_dir, "forecast_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    from slicktrace_core.display_geometry import write_forecast_contours
    write_forecast_contours(case_dir, out, particles_by_horizon)
    return out
''')

# ----------------------------------------------------------- case contract --

edit("slicktrace_core/case_contract.py",
'''  * No forecast envelope polygon: forecast_result.json stores horizon areas
    and centroids only. Persisting contours is separate work.
''',
'''  * No forecast envelope polygon inside `forecast`: forecast_result.json
    stores horizon areas and centroids. The contours are their own artifact,
    carried in `forecast_contours`.
''')

edit("slicktrace_core/case_contract.py",
'''SCHEMA_VERSION = "1"
''',
'''SCHEMA_VERSION = "2"   # 2: adds replay_footprints and forecast_contours
''')

edit("slicktrace_core/case_contract.py",
'''# ------------------------------------------------------------------- case --

class Case(_Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
''',
'''# ------------------------------------------------------- display geometry --

class Footprint(_Strict):
    vessel_key: str
    candidate_id: str
    rank: int
    release_start: IsoUtc
    duration_hours: float
    is_continuous: bool
    release_start_position: Optional[LonLat] = None
    release_end_position: Optional[LonLat] = None
    nominal_iou: float
    polygons: list[list[LonLat]]


class ReplayFootprints(_Strict):
    incident_id: str
    variant: Literal["nominal"]
    scored_against: str
    coordinate_convention: str
    footprints: list[Footprint]
    note: str


class DensityContour(_Strict):
    fraction: float
    polygons: list[list[LonLat]]


class ForecastContourHorizon(_Strict):
    horizon_hours: int
    valid_utc: IsoUtc
    density_contours: list[DensityContour]


class ForecastContours(_Strict):
    incident_id: str
    issued_from_utc: IsoUtc
    n_particles_per_horizon: int
    coordinate_decimals: int
    horizons: list[ForecastContourHorizon]
    note: str


# ------------------------------------------------------------------- case --

class Case(_Strict):
    schema_version: Literal["2"] = SCHEMA_VERSION
''')

edit("slicktrace_core/case_contract.py",
'''    next_observation: Optional[NextObservation] = None

    @model_validator(mode="after")
''',
'''    next_observation: Optional[NextObservation] = None
    replay_footprints: Optional[ReplayFootprints] = None
    forecast_contours: Optional[ForecastContours] = None

    @model_validator(mode="after")
''')

edit("slicktrace_core/case_contract.py",
'''        for name in ("baseline", "attribution", "fragility", "coverage", "forecast",
                     "next_observation"):
''',
'''        for name in ("baseline", "attribution", "fragility", "coverage", "forecast",
                     "next_observation", "replay_footprints", "forecast_contours"):
''')

edit("slicktrace_core/case_contract.py",
'''            if not {r.vessel_key for r in self.attribution.ranking} <= set(candidates):
                raise ValueError("ranking contains a vessel that is not a candidate")
        return self
''',
'''            if not {r.vessel_key for r in self.attribution.ranking} <= set(candidates):
                raise ValueError("ranking contains a vessel that is not a candidate")

        if self.replay_footprints is not None and self.attribution is not None:
            drawn = [(f.vessel_key, f.candidate_id) for f in self.replay_footprints.footprints]
            ranked = [(r.vessel_key, r.candidate_id) for r in self.attribution.ranking]
            if drawn != ranked:
                raise ValueError("replay footprints do not follow the attribution ranking")

        if self.forecast_contours is not None and self.forecast is not None:
            if [h.horizon_hours for h in self.forecast_contours.horizons] != \\
                    [h.horizon_hours for h in self.forecast.horizons]:
                raise ValueError("forecast contours do not cover the forecast horizons")
        return self
''')

edit("slicktrace_core/case_contract.py",
'''        "next_observation": _load(case_dir, "next_observation_result.json"),
    })
''',
'''        "next_observation": _load(case_dir, "next_observation_result.json"),
        "replay_footprints": _load(case_dir, "replay_footprints.json"),
        "forecast_contours": _load(case_dir, "forecast_contours.json"),
    })
''')

# -------------------------------------------------------------------- API --

edit("backend/app.py",
'''    return _strip_truth(case.model_dump(mode="json"))


# ------------------------------------------------------------- incidents --
''',
'''    return _strip_truth(case.model_dump(mode="json"))


@app.get("/api/incidents/{incident_id}/replay-footprints")
def get_replay_footprints(incident_id: str):
    """Each ranked candidate's nominal replayed footprint, traced for the map."""
    return _require(incident_id, "replay_footprints.json", "replay footprints")


@app.get("/api/incidents/{incident_id}/forecast-contours")
def get_forecast_contours(incident_id: str):
    """50/75/90% density contours for each forecast horizon, for the map."""
    return _require(incident_id, "forecast_contours.json", "forecast contours")


# ------------------------------------------------------------- incidents --
''')

# --------------------------------------------------------- verifier and CI --

edit("scripts/verify_document_claims.py",
'''check("217 tests pass", "217 passed" in t, True)
''',
'''check("223 tests pass", "223 passed" in t, True)
''')

edit(".github/workflows/tests.yml",
'''            'data/cases/*/envelope_timeline.json' \\
''',
'''            'data/cases/*/envelope_timeline.json' \\
            'data/cases/*/replay_footprints.json' \\
            'data/cases/*/forecast_contours.json' \\
''')

# -------------------------------------------------------------- changelog --

edit("CHANGELOG.md",
'''already states the finding. `api.js` no longer defines `detection` twice.
''',
'''already states the finding. `api.js` no longer defines `detection` twice.

**Display geometry computed in the pipeline.** The attribution stage now also
writes `replay_footprints.json`: for every ranked candidate, the footprint its
best hypothesis produces under the nominal forcing member, rasterised exactly as
scored and traced to lon/lat. The forecast stage writes `forecast_contours.json`:
50/75/90% contours over the particles behind each horizon's figures. Both are
served (`/replay-footprints`, `/forecast-contours`) and carried in the Case
contract, now schema 2; `attribution_result.json` and `forecast_result.json` are
unchanged. Fixed on the way: since matplotlib 3.8 a contour level returns all of
its loops in one path, and `density_contours` took it whole, so 4 of 675 rings
across the nine envelope timelines joined two lobes into one polygon with a false
edge between them. Levels are now split at each loop; the single-loop rings are
unchanged. Six tests added; 223 pass.
''')


# ------------------------------------------------------------------ apply --

def main() -> int:
    if not os.path.isfile("slicktrace_core/hindcast.py"):
        print("Run this from the slick-trace repository root.", file=sys.stderr)
        return 2
    with open("slicktrace_core/hindcast.py", encoding="utf-8") as f:
        if "def vessel_hourly_states(" not in f.read() or not os.path.exists("slicktrace_core/envelope_timeline.py"):
            print("ABORT: patches 01 and 02 must be applied first.",
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
    print(f"patch 03: {applied} edits applied, {skipped} already in place, "
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
