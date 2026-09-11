"""API surface tests and the frozen NLP suite as a pass/fail gate."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from tests.nlp_suite import resolve_suite
from slicktrace_core.nlp_query import CaseKB, ask

client = TestClient(app)
CASE = "case_0001"
CASE_DIR = os.path.join("data", "cases", CASE)


# ------------------------------------------------------------ NLP suite ---

def _suite():
    kb = CaseKB(CASE_DIR)
    ranked = [r["vessel_key"] for r in (kb.attribution or {}).get("ranking", [])]
    excluded = [a["vessel_key"] for a in (kb.historical_mapping or {}).get("assessments", [])
                if a["status"] == "excluded"]
    return kb, resolve_suite(list(kb.tracks_by_key), ranked, excluded)


def test_nlp_suite_has_enough_questions_and_enough_refusals():
    """Masterplan p.15 asks for at least 30 questions across supported intents,
    paraphrases and ambiguous/unsupported cases."""
    _kb, suite = _suite()
    assert len(suite) >= 30, f"suite has only {len(suite)} questions"
    refusals = [q for q in suite if not q["expect_supported"]]
    assert len(refusals) >= 8, (
        "too few refusal cases — a suite of answerable questions measures coverage, "
        "not grounding")


@pytest.mark.parametrize("item", _suite()[1], ids=lambda i: i["question"][:48])
def test_nlp_suite_item(item):
    kb = CaseKB(CASE_DIR)
    result = ask(kb, item["question"])
    assert result.intent == item["expect_intent"], (
        f"intent mismatch for {item['question']!r}")
    assert result.supported == item["expect_supported"], (
        f"support mismatch for {item['question']!r}: {result.answer}")
    if result.supported and item.get("expect_citations", True):
        assert result.citations, f"uncited answer for {item['question']!r}"


# ------------------------------------------------------------------ API ---

def test_health_and_version():
    assert client.get("/api/health").json()["status"] == "ok"
    v = client.get("/api/version").json()
    assert v["compute_profile"] == "cpu"


def test_incident_list_shape():
    incidents = client.get("/api/incidents").json()
    assert len(incidents) >= 4, "at least four independently generated cases must exist"
    families = {i["family"] for i in incidents}
    for required in ("decoy", "moving_discharge", "absent_source"):
        assert required in families, f"no {required} case present"


@pytest.mark.parametrize("path", [
    "manifest", "scene", "historical-mapping", "attribution", "naive-baseline",
    "tracks", "fragility", "forecast", "coverage", "next-observation",
    "report", "report.md",
])
def test_endpoint_responds(path):
    resp = client.get(f"/api/incidents/{CASE}/{path}")
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"


def test_unknown_incident_is_404_not_500():
    assert client.get("/api/incidents/does_not_exist/manifest").status_code == 404


def test_path_traversal_rejected():
    resp = client.get("/api/incidents/..%2F..%2Fetc/manifest")
    assert resp.status_code in (400, 404)


def test_envelope_slider_is_live_and_time_varying():
    """The UTC control must be a live query, not a pre-rendered filmstrip:
    different requested times must return different envelope states."""
    a = client.get(f"/api/incidents/{CASE}/envelope?hours_before=0").json()
    b = client.get(f"/api/incidents/{CASE}/envelope?hours_before=12").json()
    assert a["time_utc"] != b["time_utc"]
    assert a["particles"] != b["particles"]
    assert a["layer_status"] == "observed" and a["hindcast"] is False
    assert b["layer_status"] == "modelled" and b["hindcast"] is True


def test_envelope_reports_per_time_membership():
    """Candidates must be able to enter and leave the envelope as time moves —
    that transition is the demonstration, not a static label."""
    states = set()
    for h in range(0, 25, 2):
        env = client.get(f"/api/incidents/{CASE}/envelope?hours_before={h}").json()
        for v in env["vessels"]:
            states.add(v["at_this_time"])
    assert "inside" in states and "outside" in states, (
        "no vessel ever changes envelope membership across the window")


def test_envelope_rejects_out_of_range_time():
    assert client.get(f"/api/incidents/{CASE}/envelope?hours_before=999").status_code == 422


def test_ask_endpoint_returns_filters_and_citations():
    resp = client.post(f"/api/incidents/{CASE}/ask",
                       json={"question": "What is the top candidate and why?"})
    body = resp.json()
    assert body["supported"] is True
    assert body["citations"]


def test_ask_endpoint_refuses_visibly():
    resp = client.post(f"/api/incidents/{CASE}/ask",
                       json={"question": "Write me a press release about this spill."})
    body = resp.json()
    assert body["supported"] is False
    assert body["intent"] == "unsupported"


def test_report_markdown_states_its_limits():
    text = client.get(f"/api/incidents/{CASE}/report.md").text
    assert "not a court-ready dossier" in text.lower()
    assert "not a legal finding" in text.lower()
    assert "sha-256" in text.lower()


def test_report_for_absent_source_case_says_unknown_source():
    absent = [i["incident_id"] for i in client.get("/api/incidents").json()
              if i["family"] == "absent_source"]
    assert absent
    text = client.get(f"/api/incidents/{absent[0]}/report.md").text
    assert "Unknown source" in text


def test_missing_stage_returns_actionable_404(tmp_path):
    """A missing artifact should say what to run, not fail opaquely."""
    empty = os.path.join("data", "cases", "_tmp_empty_case")
    os.makedirs(empty, exist_ok=True)
    try:
        with open(os.path.join(empty, "manifest.json"), "w") as f:
            json.dump({"incident_id": "_tmp_empty_case", "acquired_utc": "2026-09-10T04:30:00+00:00",
                       "bbox": {"min_lon": 0, "min_lat": 0, "max_lon": 1, "max_lat": 1},
                       "tracks": [], "image_path": "missing.png"}, f)
        resp = client.get("/api/incidents/_tmp_empty_case/attribution")
        assert resp.status_code == 404
        assert "run_pipeline" in resp.json()["detail"]
    finally:
        import shutil
        shutil.rmtree(empty, ignore_errors=True)
