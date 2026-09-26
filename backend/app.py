"""
Slick Trace backend — wires slicktrace_core into a real API.

Endpoints are intentionally thin: each reads artifacts already produced by the
pipeline stages rather than re-implementing logic. The time slider is served
from envelope_timeline.json, which the historical-mapping stage writes; nothing
is simulated per request. Three request-time views remain and are named here:
/tracks resolves MMSI identity and AIS field quality, /probe reads the forcing
file for one point, and /report assembles the committed artifacts with this
session's query log. This mirrors the masterplan's "versioned analysis
services" architecture (p.13) — detection, hindcast, candidate replay,
confidence checks and forecast stay separate, callable stages.

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
from slicktrace_core.nlp_query import CaseKB, ask as ask_nlp
from slicktrace_core.report import build_report, render_markdown
from slicktrace_core.case_contract import build_case

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(REPO_ROOT, "data", "cases")

app = FastAPI(title="Slick Trace API", version="0.2.0")

_kb_cache: dict[str, CaseKB] = {}
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


# ------------------------------------------------------------------ case --

@app.get("/api/incidents/{incident_id}/case")
def get_case(incident_id: str):
    """The whole incident as one validated object (slicktrace_core.case_contract).

    Assembled from the committed artifacts; nothing here computes. A missing
    optional stage comes back null. An artifact that no longer matches the
    contract is a 500 naming the mismatch, never a silently partial payload.
    """
    case_dir = _case_dir(incident_id)
    try:
        case = build_case(case_dir)
    except FileNotFoundError as e:
        raise HTTPException(404, f"{e}. Run scripts/run_pipeline.py to produce it.")
    except ValueError as e:  # includes pydantic's ValidationError
        raise HTTPException(500, f"{incident_id} does not match the Case contract: {e}")
    return _strip_truth(case.model_dump(mode="json"))


@app.get("/api/incidents/{incident_id}/replay-footprints")
def get_replay_footprints(incident_id: str):
    """Each ranked candidate's nominal replayed footprint, traced for the map."""
    return _require(incident_id, "replay_footprints.json", "replay footprints")


@app.get("/api/incidents/{incident_id}/forecast-contours")
def get_forecast_contours(incident_id: str):
    """50/75/90% density contours for each forecast horizon, for the map."""
    return _require(incident_id, "forecast_contours.json", "forecast contours")


@app.get("/api/incidents/{incident_id}/track-display")
def get_track_display(incident_id: str):
    """Per-vessel gap windows and a rendering-only smoothed path."""
    return _require(incident_id, "track_display.json", "track display")


@app.get("/api/incidents/{incident_id}/replay-timeline")
def get_replay_timeline(incident_id: str):
    """The named leading candidate's scored release, hour by hour, for the map.
    Empty frames on an abstention: nothing is animated for a vessel not named."""
    return _require(incident_id, "replay_timeline.json", "replay timeline")


@app.get("/api/incidents/{incident_id}/ensemble-fan")
def get_ensemble_fan(incident_id: str):
    """Each ranked candidate's best release under the six forcing variants attribution
    scored, and the uniform current the model uses, for the map."""
    return _require(incident_id, "ensemble_fan.json", "ensemble fan")


@app.get("/api/incidents/{incident_id}/forecast-timeline")
def get_forecast_timeline(incident_id: str):
    """Modelled drift after the image, every hour to +24 h, for the map."""
    return _require(incident_id, "forecast_timeline.json", "forecast timeline")


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


@app.get("/api/overview")
def get_overview():
    """Every case with just what its headline finding needs, for the overview grid.

    The fields are copied from attribution_result.json and
    naive_baseline_result.json - the same ones the Case Finding card reads - so
    the overview's one-line finding is produced by the same rule as the card's,
    not written separately. Nothing here summarises beyond selecting fields.
    """
    out = []
    for row in list_incidents():
        iid = row["incident_id"]
        at = _load_json(iid, "attribution_result.json")
        nb = _load_json(iid, "naive_baseline_result.json")
        finding = None
        if at is not None:
            rk = at.get("ranking") or []
            top = rk[0] if rk else None
            near = (nb or {}).get("ranking") or []
            finding = {
                "unknown_source": at["unknown_source"],
                "abstention_iou_gate": at["abstention_iou_gate"],
                "n_candidates": len(at.get("candidates_considered") or []),
                "top_candidate_id": at.get("top_candidate_id"),
                "best": None if top is None else {
                    "vessel_key": top["vessel_key"], "mean_iou": top["mean_iou"],
                    "ensemble_win_count": top["ensemble_win_count"], "n_ensemble": top["n_ensemble"]},
                "runner_up_mean_iou": rk[1]["mean_iou"] if len(rk) > 1 else None,
                "discrimination": at.get("discrimination"),
                "nearest": None if not near else {
                    "vessel_key": near[0]["vessel_key"], "distance_deg": near[0]["distance_deg"]},
            }
        out.append({**row, "finding": finding})
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

@app.get("/api/geo/coastline")
def get_real_coastline():
    """Real coastline geometry for the scene area, as a reference overlay.

    Natural Earth 10m, public domain, clipped to the case bounding boxes and
    committed to the repository - not fetched from a tile server. The offline
    smoke test in docs/evidence is a property this project went out of its way
    to establish, and a basemap that needs the network would end it.

    The same coastline every case now uses: each manifest carries it clipped
    to the scene, the detector rejects land against it, and the forecast strands
    oil on it (slicktrace_core.geography). An invented coastline about 19 km
    east of this one stood in for it before.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "geo", "coastline_mumbai.json")
    if not os.path.exists(path):
        raise HTTPException(404, "coastline geometry not present")
    with open(path) as f:
        geo = json.load(f)
    return {
        "geometry": geo,
        "source": "Natural Earth 10m coastline",
        "licence": "public domain",
        "note": ("The coastline every case uses: manifests carry it clipped to the scene, "
                 "detection rejects land against it and the forecast strands oil on it. "
                 "Natural Earth 10 m is scene-scale; narrow creeks are resolved only coarsely."),
    }


@app.get("/api/incidents/{incident_id}/dossier.pdf")
def get_dossier(incident_id: str):
    """The investigation report as a PDF, rendered from the committed artifact."""
    from fastapi.responses import FileResponse
    path = os.path.join(_case_dir(incident_id), "investigation_dossier.pdf")
    if not os.path.exists(path):
        raise HTTPException(404, "dossier not generated for this incident")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{incident_id}_investigation.pdf")


@app.get("/api/incidents/{incident_id}/probe")
def probe_forcing(incident_id: str,
                  lon: float = Query(...), lat: float = Query(...),
                  hours_before: float = Query(0.0, ge=0.0, le=24.0)):
    """The transport forcing at one point, as the attribution model sees it.

    Deliberately not the true field. The generator applies a spatial swirl the
    simulator is never given - it is the unmodelled variation the whole
    fragility analysis exists to probe - and serving it here would leak truth
    into the interface and make the model look better informed than it is.

    What is returned is the uniform current the attribution actually advects
    with. A reviewer clicking two points and getting the same answer is seeing
    a real property of the model, not a broken endpoint.
    """
    import math
    import numpy as np

    m = _load_json(incident_id, "manifest.json")
    if m is None:
        raise HTTPException(404, "manifest not found")
    b = m["bbox"]
    if not (b["min_lon"] <= lon <= b["max_lon"] and b["min_lat"] <= lat <= b["max_lat"]):
        raise HTTPException(400, "point is outside the scene")

    f = np.load(m["forcing_path"])
    # The forcing stores the current in metres per second - the simulator
    # converts with DEG_PER_MS_HR. An earlier version read these as degrees
    # per hour and reported a current about 29 times too fast (9.03 kn for a
    # 0.31 kn current); the bearing was right because the units cancel in it.
    u_ms, v_ms = float(f["u"]), float(f["v"])
    east_kmh = u_ms * 3.6
    north_kmh = v_ms * 3.6
    speed = math.hypot(east_kmh, north_kmh)
    bearing = (math.degrees(math.atan2(east_kmh, north_kmh)) + 360) % 360

    return {
        "incident_id": incident_id,
        "lon": round(lon, 5), "lat": round(lat, 5),
        "hours_before_acquisition": hours_before,
        "current": {
            "east_km_per_h": round(east_kmh, 3),
            "north_km_per_h": round(north_kmh, 3),
            "speed_km_per_h": round(speed, 3),
            "speed_knots": round(speed / 1.852, 3),
            "bearing_deg_from_north": round(bearing, 1),
        },
        "wind": None,
        "model_note": (
            "This is the current the attribution model advects with: uniform in space "
            "and constant in time. Two different points return the same vector, which "
            "is a property of the model rather than a fault in this endpoint."
        ),
        "truth_note": (
            "The generator applies a spatial swirl the simulator is never given. That "
            "unmodelled variation is what the rank-fragility sweep exists to probe, and "
            "it is deliberately not served here: an interface that showed the true "
            "field would make the model look better informed than it is."
        ),
        "wind_note": (
            "No wind field exists anywhere in this pipeline - see assumption A17. "
            "Surface oil moves at roughly 3% of wind speed plus Stokes drift, so this "
            "is a first-order omission on real data, not a refinement."
        ),
    }


@app.get("/api/incidents/{incident_id}/envelope")
def get_envelope(incident_id: str,
                 hours_before: float = Query(0.0, ge=0.0, le=24.0),
                 max_particles: int = Query(300, ge=20, le=600)):
    """The backward origin envelope at one queried hour, plus every vessel's
    position and membership then.

    Served from envelope_timeline.json, which the historical-mapping stage
    writes from the same snapshots and membership pass it summarises. Nothing
    is simulated here: the frame nearest the requested time is returned, so the
    slider shows exactly the 25 hourly states the pipeline computed and the
    determinism check covers.
    """
    tl = _require(incident_id, "envelope_timeline.json", "envelope timeline")
    frame = min(tl["frames"], key=lambda f: abs(f["hours_before_acquisition"] - hours_before))
    step = max(1, len(frame["particles"]) // max_particles)
    return {
        "incident_id": incident_id,
        "hours_before_acquisition": frame["hours_before_acquisition"],
        "time_utc": frame["time_utc"],
        "acquired_utc": tl["acquired_utc"],
        "layer_status": frame["layer_status"],
        "hindcast": frame["hindcast"],
        "inclusion_radius_deg": tl["inclusion_radius_deg"],
        "particles": frame["particles"][::step],
        # Contours were computed on the full particle set, not the decimated one
        # sent to the client: subsampling for bandwidth does not move the mass.
        "density_contours": frame["density_contours"],
        "density_note": tl["density_note"],
        "vessels": frame["vessels"],
        "note": tl["note"],
    }


@app.get("/api/incidents/{incident_id}/envelope-timeline")
def get_envelope_timeline(incident_id: str):
    """All 25 hourly frames at once, so an interface can scrub without a
    request per step."""
    return _require(incident_id, "envelope_timeline.json", "envelope timeline")


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
