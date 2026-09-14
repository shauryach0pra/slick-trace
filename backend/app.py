"""
Slick Trace backend — wires slicktrace_core into a real API.

Endpoints are intentionally thin: each reads artifacts already produced by the
pipeline stages, or recomputes a cheap derived view (the backward envelope for
the time slider), rather than re-implementing logic. This mirrors the
masterplan's "versioned analysis services" architecture (p.13) — detection,
hindcast, candidate replay, confidence checks and forecast stay separate,
callable stages.

GROUND-TRUTH DISCIPLINE
    `truth.json` is never loaded here, and `_strip_truth` removes any field
    whose name marks it as hidden before anything is serialised. Earlier the
    manifest endpoint served `true_vessel_key_HIDDEN` and a per-track
    `is_true_source` flag straight to the browser; the generator no longer
    writes those, and this is the second line of defence in case a future
    adapter reintroduces one.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from slicktrace_core.ais_quality import validate_track
from slicktrace_core.identity import parse_mmsi
from slicktrace_core.hindcast import _interp_track_position, _parse, build_backward_envelope
from slicktrace_core.nlp_query import CaseKB, ask as ask_nlp
from slicktrace_core.report import build_report, render_markdown

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(REPO_ROOT, "data", "cases")

app = FastAPI(title="Slick Trace API", version="0.2.0")

_kb_cache: dict[str, CaseKB] = {}
_envelope_cache: dict[str, list] = {}
_query_log: dict[str, list[dict]] = {}


# ------------------------------------------------------------ truth guard --

def _strip_truth(obj):
    """Remove any dev-only ground-truth field before it reaches a client.

    Belt and braces: the generator no longer writes these, but an adapter for
    real data could plausibly carry a label column through, and a leak here is
    silent — the UI would look fine while the answer sat in the network tab.
    """
    if isinstance(obj, dict):
        return {k: _strip_truth(v) for k, v in obj.items()
                if not (k.endswith("_HIDDEN") or k in ("is_true_source", "true_vessel_key",
                                                       "absent_true_vessel_key", "roles"))}
    if isinstance(obj, list):
        return [_strip_truth(v) for v in obj]
    return obj


# ---------------------------------------------------------------- helpers --

def _case_dir(incident_id: str) -> str:
    if "/" in incident_id or "\\" in incident_id or incident_id.startswith("."):
        raise HTTPException(400, "invalid incident id")
    d = os.path.join(DATA_ROOT, incident_id)
    if not os.path.isdir(d):
        raise HTTPException(404, f"incident '{incident_id}' not found")
    return d


def _get_kb(incident_id: str) -> CaseKB:
    if incident_id not in _kb_cache:
        _kb_cache[incident_id] = CaseKB(_case_dir(incident_id))
    return _kb_cache[incident_id]


def _load_json(incident_id: str, fname: str) -> dict | None:
    path = os.path.join(_case_dir(incident_id), fname)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _require(incident_id: str, fname: str, stage: str) -> dict:
    out = _load_json(incident_id, fname)
    if out is None:
        raise HTTPException(404, f"{stage} has not been computed for this incident. "
                                 f"Run scripts/run_pipeline.py to produce it.")
    return _strip_truth(out)


# ------------------------------------------------------------- incidents --

@app.get("/api/incidents")
def list_incidents():
    if not os.path.isdir(DATA_ROOT):
        return []
    out = []
    for iid in sorted(d for d in os.listdir(DATA_ROOT)
                      if os.path.isdir(os.path.join(DATA_ROOT, d))):
        m = _load_json(iid, "manifest.json")
        if not m:
            continue
        at = _load_json(iid, "attribution_result.json") or {}
        out.append({
            "incident_id": iid,
            "acquired_utc": m["acquired_utc"],
            "provenance_status": m.get("provenance", {}).get("status"),
            "case_state": m.get("case_state"),
            "n_vessels": len(m.get("tracks", [])),
            # family is a property of the case design, not the answer — it says
            # what kind of test this is, not which vessel did it
            "family": m.get("generator", {}).get("family"),
            "outcome": ("unknown_source" if at.get("unknown_source")
                        else ("named_candidate" if at else None)),
        })
    return out


@app.get("/api/incidents/{incident_id}/manifest")
def get_manifest(incident_id: str):
    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")
    return _strip_truth(m)


@app.get("/api/incidents/{incident_id}/scene")
def get_scene(incident_id: str):
    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")
    path = m["image_path"]
    if not os.path.isabs(path):
        path = os.path.join(REPO_ROOT, path)
    if not os.path.exists(path):
        raise HTTPException(404, "scene image missing from this case directory")
    return FileResponse(path, media_type="image/png")


@app.get("/api/incidents/{incident_id}/historical-mapping")
def get_historical_mapping(incident_id: str):
    return _require(incident_id, "historical_mapping.json", "historical mapping")


@app.get("/api/incidents/{incident_id}/attribution")
def get_attribution(incident_id: str):
    return _require(incident_id, "attribution_result.json", "attribution")


@app.get("/api/incidents/{incident_id}/naive-baseline")
def get_naive_baseline(incident_id: str):
    return _require(incident_id, "naive_baseline_result.json", "naive baseline")


@app.get("/api/incidents/{incident_id}/detection")
def detection(incident_id: str):
    """Detected slick outline and geometric characterisation (PS part (a))."""
    return _require(incident_id, "detection_result.json", "detection result")


@app.get("/api/incidents/{incident_id}/fragility")
def get_fragility(incident_id: str):
    return _require(incident_id, "fragility_result.json", "rank-fragility analysis")


@app.get("/api/incidents/{incident_id}/forecast")
def get_forecast(incident_id: str):
    return _require(incident_id, "forecast_result.json", "forward exposure forecast")


@app.get("/api/incidents/{incident_id}/coverage")
def get_coverage(incident_id: str):
    return _require(incident_id, "coverage_result.json", "coverage-aware contact matching")


@app.get("/api/incidents/{incident_id}/next-observation")
def get_next_observation(incident_id: str):
    return _require(incident_id, "next_observation_result.json", "next-observation advisor")


@app.get("/api/incidents/{incident_id}/tracks")
def get_tracks(incident_id: str):
    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")
    return _strip_truth({
        "bbox": m["bbox"],
        "coastline": m.get("coastline", []),
        "sensitive_areas": m.get("sensitive_areas", []),
        # MMSI structure is resolved here rather than in the interface: what a
        # nine-digit identifier means is a property of the identifier, not of
        # how it is displayed. Provenance only, never an input to ranking.
        "tracks": [{"vessel_key": t["vessel_key"], "mmsi": t.get("mmsi"),
                    "identity": parse_mmsi(t.get("mmsi") or t["vessel_key"]),
                    "quality": validate_track(t),
                    "fixes": t["fixes"]} for t in m["tracks"]],
    })


# ------------------------------------------------------- live time slider --

@app.get("/api/incidents/{incident_id}/envelope")
def get_envelope(incident_id: str,
                 hours_before: float = Query(0.0, ge=0.0, le=24.0),
                 max_particles: int = Query(300, ge=20, le=600)):
    """State of the backward origin envelope at one point in time, plus every
    vessel's interpolated position then.

    This is what makes the UTC control a live instrument rather than a
    pre-rendered filmstrip: the reviewer drags the slider and watches
    candidates enter and leave the envelope. Three vessels excluded and two
    retained is an argument; watching the exclusion happen as time rewinds is
    the evidence.
    """
    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")

    if incident_id not in _envelope_cache:
        _envelope_cache[incident_id] = build_backward_envelope(m)
    snapshots = _envelope_cache[incident_id]

    snap = min(snapshots, key=lambda s: abs(s.hours_before_acquisition - hours_before))
    hm = _load_json(incident_id, "historical_mapping.json") or {}
    status_by_vessel = {a["vessel_key"]: a["status"] for a in hm.get("assessments", [])}

    # Probability contours over the particle cloud. A cloud of dots says
    # "somewhere around here"; contours enclosing 50/75/90% of the density say
    # how much of the probability sits where, which is the judgement the
    # envelope exists to support.
    from slicktrace_core.envelope_density import density_contours
    contours = density_contours(snap.particles_lon, snap.particles_lat)

    import numpy as np
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
    inclusion_radius = 0.045

    vessels = []
    for t in m["tracks"]:
        pos = _interp_track_position(t["fixes"], snap.time_utc)
        if pos is None:
            vessels.append({"vessel_key": t["vessel_key"], "lon": None, "lat": None,
                            "in_envelope": None, "overall_status": status_by_vessel.get(
                                t["vessel_key"], "unassessed"),
                            "at_this_time": "no_data"})
            continue
        dist, _ = tree.query([pos[0], pos[1]])
        vessels.append({
            "vessel_key": t["vessel_key"],
            "lon": round(float(pos[0]), 5), "lat": round(float(pos[1]), 5),
            "distance_to_envelope_deg": round(float(dist), 5),
            "in_envelope": bool(dist <= inclusion_radius),
            "overall_status": status_by_vessel.get(t["vessel_key"], "unassessed"),
            "at_this_time": "inside" if dist <= inclusion_radius else "outside",
        })

    step = max(1, len(snap.particles_lon) // max_particles)
    return {
        "incident_id": incident_id,
        "hours_before_acquisition": snap.hours_before_acquisition,
        "time_utc": snap.time_utc.isoformat(),
        "acquired_utc": m["acquired_utc"],
        "layer_status": "modelled" if snap.hours_before_acquisition > 0 else "observed",
        "hindcast": snap.hours_before_acquisition > 0,
        "inclusion_radius_deg": inclusion_radius,
        "particles": [[round(float(lo), 5), round(float(la), 5)]
                      for lo, la in zip(snap.particles_lon[::step], snap.particles_lat[::step])],
        # Contours are computed on the full particle set, not the decimated one
        # sent to the client: subsampling for bandwidth should not change where
        # the probability mass is said to be.
        "density_contours": contours,
        "density_note": ("Contours enclose 50/75/90% of the estimated density over the "
                          "backward particles. They describe where this transport model "
                          "places the mass and inherit its assumptions; a tight contour "
                          "means the model is confident, not that the answer is certain."),
        "vessels": vessels,
        "note": "Envelope width grows with hours-back because release time, duration and "
                "diffusivity are unknown. It is not converging on a point source.",
    }


# ------------------------------------------------------------------- ask --

class AskRequest(BaseModel):
    question: str


@app.post("/api/incidents/{incident_id}/ask")
def post_ask(incident_id: str, req: AskRequest):
    _case_dir(incident_id)
    kb = _get_kb(incident_id)
    result = ask_nlp(kb, req.question)
    payload = {
        "question": result.question,
        "intent": result.intent,
        "supported": result.supported,
        "filters": result.filters,
        "answer": result.answer,
        "citations": result.citations,
    }
    _query_log.setdefault(incident_id, []).append(payload)
    return payload


# ---------------------------------------------------------------- export --

@app.get("/api/incidents/{incident_id}/report")
def get_report(incident_id: str):
    case_dir = _case_dir(incident_id)
    return _strip_truth(build_report(case_dir, _query_log.get(incident_id, [])))


@app.get("/api/incidents/{incident_id}/report.md", response_class=PlainTextResponse)
def get_report_markdown(incident_id: str):
    case_dir = _case_dir(incident_id)
    report = _strip_truth(build_report(case_dir, _query_log.get(incident_id, [])))
    return PlainTextResponse(
        render_markdown(report), media_type="text/markdown",
        headers={"Content-Disposition":
                 f'attachment; filename="{incident_id}_investigation_report.md"'})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def version():
    return {
        "api_version": app.version,
        "compute_profile": "cpu",
        "outbound_calls_at_runtime": "none — no model API, no tile server, no font CDN",
    }


# Serve the built frontend (if present) at the root, so the whole app is one
# process — required for the single-container Docker packaging.
_frontend_dist = os.path.join(REPO_ROOT, "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
