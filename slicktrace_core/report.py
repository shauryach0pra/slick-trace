"""
Investigation report export (masterplan p.13).

Exports the observed footprint, historical tracks, origin/time interval,
candidate comparisons, rank fragility, unmatched contacts, forward exposure,
query history, uncertainty and run metadata into one reviewable artefact.

Two deliberate boundaries:

  This is a reproducible investigation report, not a court-ready dossier.
  A software export does not establish responsibility or legal admissibility.
  The wording in the generated document says so in the document itself, not
  only in this docstring.

  Hashes verify file integrity. They do not prove that an observation is true,
  that a label is correct, or that the analysis is sufficient for any legal
  purpose. A conventional audit log is enough here; a blockchain would add no
  capability this problem needs.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

ARTEFACTS = [
    "manifest.json",
    "historical_mapping.json",
    "naive_baseline_result.json",
    "attribution_result.json",
    "fragility_result.json",
    "coverage_result.json",
    "forecast_result.json",
    "next_observation_result.json",
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unavailable (not a git checkout, or git not installed)"


def _load(case_dir: str, name: str):
    path = os.path.join(case_dir, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def build_report(case_dir: str, query_history: list[dict] | None = None) -> dict:
    manifest = _load(case_dir, "manifest.json")
    if manifest is None:
        raise FileNotFoundError(f"no manifest.json in {case_dir}")

    data = {name: _load(case_dir, name) for name in ARTEFACTS}
    checksums = {name: _sha256(os.path.join(case_dir, name))
                 for name in ARTEFACTS if os.path.exists(os.path.join(case_dir, name))}
    for asset in ("scene.png", "mask_groundtruth.png", "forcing.npz"):
        p = os.path.join(case_dir, asset)
        if os.path.exists(p):
            checksums[asset] = _sha256(p)

    attribution = data["attribution_result.json"] or {}
    hm = data["historical_mapping.json"] or {}

    status_counts = {}
    for a in hm.get("assessments", []):
        status_counts[a["status"]] = status_counts.get(a["status"], 0) + 1

    return {
        "report_type": "reproducible investigation report",
        "not_a": "This is not a court-ready dossier, a legal finding, or an accusation. "
                 "It records what the system computed and under which assumptions.",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "incident_id": manifest["incident_id"],
        "scene": {
            "scene_id": manifest.get("scene_id"),
            "acquired_utc": manifest["acquired_utc"],
            "sensor": manifest.get("sensor"),
            "crs": manifest.get("crs"),
            "metric_crs": manifest.get("metric_crs"),
            "pixel_spacing_m": manifest.get("pixel_spacing_m"),
            "bbox": manifest["bbox"],
            "data_status": manifest.get("provenance", {}).get("status"),
            "label_source": manifest.get("label_source"),
        },
        "evidence_layers": {
            "ais_source": manifest.get("ais_source"),
            "ais_window": [manifest.get("ais_window_start_utc"), manifest.get("ais_window_end_utc")],
            "forcing_product": manifest.get("forcing_product"),
            "forcing_window": [manifest.get("forcing_valid_from_utc"), manifest.get("forcing_valid_to_utc")],
            "data_licence": manifest.get("data_licence"),
        },
        "historical_filtering": {
            "hours_back": hm.get("hours_back"),
            "status_counts": status_counts,
            "assessments": hm.get("assessments", []),
            "state_meaning": {
                "candidate": "track data present and inside the backward envelope at some queried time",
                "excluded": "track data at every queried time, never inside the envelope",
                "unassessed": "never inside where track data exists, but no track data at one or "
                              "more queried times — missing evidence, NOT exoneration",
            },
        },
        "attribution": {
            "outcome": "unknown_source" if attribution.get("unknown_source") else "named_candidate",
            "top_candidate": attribution.get("top_candidate_id"),
            "abstention_iou_gate": attribution.get("abstention_iou_gate"),
            "loss_weights": attribution.get("loss_weights"),
            "n_ensemble_variants": attribution.get("n_ensemble_variants"),
            "ranking": attribution.get("ranking", []),
            "baseline_comparison": data["naive_baseline_result.json"],
        },
        "rank_fragility": data["fragility_result.json"],
        "unmatched_contacts": data["coverage_result.json"],
        "forward_exposure": data["forecast_result.json"],
        "next_observation": data["next_observation_result.json"],
        "query_history": query_history or [],
        "uncertainty_statement": [
            "Rankings express physical consistency under tested assumptions. They are not "
            "proof of responsibility.",
            "Ensemble and perturbation-grid win frequencies are evidence scores, not "
            "calibrated probabilities. No calibration against held-out real outcomes exists.",
            "Where no candidate clears the absolute fit gate the system reports unknown "
            "source rather than naming the least-bad option.",
            "Synthetic ranking accuracy is not a measurement of real-world attribution "
            "accuracy.",
        ],
        "run_metadata": {
            "git_revision": _git_revision(),
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "argv0": os.path.basename(sys.argv[0]) if sys.argv else None,
        },
        "checksums_sha256": checksums,
        "checksum_note": "Hashes verify file integrity only. They do not establish that an "
                         "observation is true, that a label is correct, or that this analysis "
                         "is legally sufficient.",
    }


def render_markdown(report: dict) -> str:
    L = []
    a = report["attribution"]
    w = L.append

    w(f"# Investigation report — {report['incident_id']}")
    w("")
    w(f"*{report['not_a']}*")
    w("")
    w(f"Generated {report['generated_utc']} · git `{report['run_metadata']['git_revision']}` "
      f"· {report['run_metadata']['platform']}")
    w("")

    w("## Outcome")
    w("")
    if a["outcome"] == "unknown_source":
        w(f"**Unknown source.** No candidate cleared the absolute fit gate "
          f"(IoU ≥ {a['abstention_iou_gate']}). The system declines to name a vessel rather "
          f"than returning the least-bad option.")
    else:
        top = a["ranking"][0] if a["ranking"] else {}
        w(f"**Leading candidate: `{a['top_candidate']}`** — mean IoU "
          f"{top.get('mean_iou', float('nan')):.3f}, leading in "
          f"{top.get('ensemble_win_count')}/{top.get('n_ensemble')} shared forcing variants.")
        w("")
        w("This is an investigative lead for a human analyst. It is not a legal finding, "
          "and it is not an accusation.")
    w("")

    w("## Scene and evidence")
    w("")
    s = report["scene"]
    w(f"| Field | Value |")
    w(f"| --- | --- |")
    for k, label in [("scene_id", "Scene"), ("acquired_utc", "Acquired (UTC)"),
                     ("sensor", "Sensor"), ("crs", "CRS"),
                     ("pixel_spacing_m", "Pixel spacing (m)"),
                     ("data_status", "Data status"), ("label_source", "Label source")]:
        w(f"| {label} | {s.get(k)} |")
    e = report["evidence_layers"]
    w(f"| AIS source | {e.get('ais_source')} |")
    w(f"| AIS window | {e['ais_window'][0]} → {e['ais_window'][1]} |")
    w(f"| Forcing | {e.get('forcing_product')} |")
    w(f"| Data licence | {e.get('data_licence')} |")
    w("")

    w("## Historical filtering")
    w("")
    hf = report["historical_filtering"]
    w(f"Backward window: {hf.get('hours_back')} h. "
      f"Outcomes: {', '.join(f'{v} {k}' for k, v in hf['status_counts'].items())}.")
    w("")
    w("| Vessel | State | Reason |")
    w("| --- | --- | --- |")
    for asmt in hf["assessments"]:
        w(f"| `{asmt['vessel_key']}` | {asmt['status']} | {asmt['reason']} |")
    w("")
    w("> `unassessed` means the track had no data at one or more queried times and was "
      "never inside the envelope where it did. Those hours are missing evidence, not "
      "exoneration, so the vessel is not `excluded`: that state requires data at every "
      "queried time.")
    w("")

    w("## Candidate comparison")
    w("")
    if a["ranking"]:
        w("| Vessel | Mean IoU | Mean loss | Ensemble wins | Release hypothesis |")
        w("| --- | --- | --- | --- | --- |")
        for r in a["ranking"]:
            kind = "continuous" if r["is_continuous"] else "pulse"
            w(f"| `{r['vessel_key']}` | {r['mean_iou']:.3f} | {r['mean_loss']:.4f} | "
              f"{r['ensemble_win_count']}/{r['n_ensemble']} | {r['duration_hours']} h {kind} |")
    else:
        w("_No candidates survived historical filtering._")
    w("")
    nb = a.get("baseline_comparison")
    if nb:
        w(f"Naive nearest-at-acquisition baseline over the full unfiltered vessel list picked "
          f"`{nb['top_candidate_id']}`.")
        w("")

    frag = report.get("rank_fragility")
    if frag and frag.get("testable"):
        w("## Rank fragility")
        w("")
        w(f"{frag['n_points_tested']} perturbations tested; the leader changed in "
          f"{frag['n_points_flipped']} of them "
          f"({frag['lead_retained_fraction'] * 100:.0f}% lead retention).")
        w("")
        if frag.get("flip_found"):
            f = frag["smallest_flip"]
            changes = ", ".join(f"`{k}` = {v}" for k, v in f["changed_axes"].items())
            w(f"Smallest tested rank-changing perturbation (standardised magnitude "
              f"{f['magnitude']}): {changes} → leader becomes `{f['top_candidate']}`.")
        else:
            w("No tested perturbation changed the leader.")
        w("")
        w(f"> {frag['coverage_note']}")
        w("")
        w(f"> {frag['interpretation_note']}")
        w("")

    fc = report.get("forward_exposure")
    if fc:
        w("## Forward exposure")
        w("")
        w(f"_{fc['forcing_mode']}_")
        w("")
        w("| Horizon | Envelope area (km²) | Shoreline fraction | Sensitive-area contact |")
        w("| --- | --- | --- | --- |")
        for h in fc["horizons"]:
            contacts = ", ".join(x["name"] for x in h["sensitive_area_exposure"] if x["any_contact"]) or "none"
            w(f"| +{h['horizon_hours']} h | {h['envelope_area_km2']} | "
              f"{h['modelled_shoreline_fraction']} | {contacts} |")
        w("")
        w(f"> {fc['interpretation_note']}")
        w("")

    cov = report.get("unmatched_contacts")
    if cov:
        w("## Unmatched SAR contacts — coverage-aware assessment")
        w("")
        op = cov["operating_point"]
        w(f"Operating point: match gate {op['gate_radius_deg']}°, contact position noise "
          f"{op['contact_position_noise_deg']}°.")
        w("")
        w("| Condition | Hidden-AIS recovery | False unmatched-alert | Mistaken promotion |")
        w("| --- | --- | --- | --- |")
        for cond, r in cov["conditions"].items():
            w(f"| {cond} | {r['hidden_ais_recovery_rate']} ({r['hidden_ais_recovery_n']}) | "
              f"{r['false_unmatched_alert_rate']} ({r['false_unmatched_alert_n']}) | "
              f"{r['mistaken_promotion_rate']} ({r['mistaken_promotion_n']}) |")
        w("")

    nxt = report.get("next_observation")
    if nxt and nxt.get("applicable"):
        rec = nxt["recommended_window"]
        w("## Recommended next observation")
        w("")
        w(f"Most informative tested window: **+{rec['horizon_hours']} h** "
          f"(disagreement score {rec['disagreement_score']}). {rec['schedule_status']}.")
        w("")
        w(f"> {nxt['scope_note']}")
        w("")

    if report["query_history"]:
        w("## Query history")
        w("")
        for q in report["query_history"]:
            w(f"- **{q.get('question')}** → intent `{q.get('intent')}`"
              f"{'' if q.get('supported') else ' (refused)'}")
        w("")

    w("## Uncertainty and limits")
    w("")
    for line in report["uncertainty_statement"]:
        w(f"- {line}")
    w("")

    w("## Integrity")
    w("")
    w(f"> {report['checksum_note']}")
    w("")
    w("| Artefact | SHA-256 |")
    w("| --- | --- |")
    for name, h in report["checksums_sha256"].items():
        w(f"| `{name}` | `{h[:16]}…` |")
    w("")
    return "\n".join(L)


def export_report(case_dir: str, query_history: list[dict] | None = None) -> tuple[str, str]:
    report = build_report(case_dir, query_history)
    json_path = os.path.join(case_dir, "investigation_report.json")
    md_path = os.path.join(case_dir, "investigation_report.md")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(md_path, "w") as f:
        f.write(render_markdown(report))
    return json_path, md_path


if __name__ == "__main__":
    import sys as _sys
    case_dir = _sys.argv[1] if len(_sys.argv) > 1 else "data/cases/case_0001"
    jp, mp = export_report(case_dir)
    print(f"Exported:\n  {jp}\n  {mp}")
