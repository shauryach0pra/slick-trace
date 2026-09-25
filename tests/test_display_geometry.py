"""Display geometry: outlines drawn by the map, computed and persisted by the pipeline."""

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
        assert [(f["vessel_key"], f["candidate_id"]) for f in fp["footprints"]] == \
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
        assert [h["horizon_hours"] for h in fc["horizons"]] == \
               [h["horizon_hours"] for h in fr["horizons"]], cid
        for h in fc["horizons"]:
            assert [c["fraction"] for c in h["density_contours"]] == [0.5, 0.75, 0.9]
            assert all(c["polygons"] for c in h["density_contours"]), (cid, h["horizon_hours"])


def test_display_geometry_endpoints_equal_case_sections():
    client = TestClient(app)
    case = client.get("/api/incidents/case_0001/case").json()
    assert case["replay_footprints"] == \
        client.get("/api/incidents/case_0001/replay-footprints").json()
    assert case["forecast_contours"] == \
        client.get("/api/incidents/case_0001/forecast-contours").json()
