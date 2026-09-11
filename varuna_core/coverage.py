"""
Coverage-aware unmatched-SAR-contact branch (masterplan p.11).

An unmatched SAR detection is a contact whose identity has not been resolved
from available AIS. It may be a vessel that was not broadcasting, a
positioning or timing mismatch, a fixed object, or a false detection. SAR
cannot generally recover a ship's name from a bright point. Nothing here
promotes an unmatched contact to prime suspect, and there is no AIS-gap
culpability bonus.

The contribution is not radar/AIS matching itself — Cerulean already
documents dark-source association. It is the coverage-aware treatment plus a
controlled benchmark under a NAMED, DEFINED metric, so another team can
reproduce the stress test rather than take a qualitative claim on trust.

THE THREE RATES, defined at a stated operating point (the gate radius):

  hidden-AIS recovery rate
      Of the vessels whose AIS records were deliberately hidden, the
      proportion that matching correctly surfaces as unidentified contacts.
      High is good: the system notices something is there.

  false unmatched-alert rate
      Of the contacts declared unidentified, the proportion whose broadcast
      was in fact available. High is bad: the system cries dark vessel at
      ships that were announcing themselves.

  mistaken-promotion rate
      The proportion of runs in which an unrelated target is advanced in the
      candidate ranking as a result of the hidden records. This is the one
      that matters operationally, because it is the failure that produces a
      wrong name rather than merely a wrong count.

Two hiding conditions are reported separately:
  "selective"        — a fraction of individual vessels' AIS is hidden.
  "coverage_failure" — a whole spatial neighbourhood goes dark at once,
                       imitating a receiver or provider outage rather than
                       deliberate non-broadcasting.

These are simulation experiments on synthetic data. They are kept strictly
separate from any claim about real intentional non-broadcasting.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import numpy as np

from varuna_core.hindcast import _interp_track_position, _parse

# Operating point. Both numbers are reported with every result — a rate
# without its gate is not a comparable measurement.
#
# The noise is deliberately a substantial fraction of the gate. An earlier
# setting (noise 0.004 against a 0.02 gate) made matching trivially easy and
# produced a 100% recovery rate with zero false alerts — a number that looks
# like a result but only measures how generous the gate was. At roughly
# 1.3 km combined geolocation and time-projection error against a ~2.2 km
# gate, a realistic share of pairs fall outside the gate and the metric has
# something to measure.
GATE_RADIUS_DEG = 0.02          # match gate: AIS position vs contact position
CONTACT_POSITION_NOISE_DEG = 0.012  # SAR geolocation + AIS time-projection error


def synth_contacts(manifest: dict, rng: np.random.Generator,
                   false_detection_rate: float = 0.15,
                   miss_rate: float = 0.15) -> list[dict]:
    """Stand-in for a validated ship detector: contacts at each vessel's
    position at acquisition time, plus some false detections (fixed objects,
    bright targets, speckle artefacts).

    Explicitly NOT derived from the binary Zenodo-style oil masks — an oil
    mask contains no ship information, and deriving ship labels from one
    would be a fabricated capability (masterplan p.11).
    """
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    contacts = []
    for tr in manifest["tracks"]:
        pos = _interp_track_position(tr["fixes"], acquired)
        if pos is None:
            continue  # vessel had left the scene / no data at acquisition
        if rng.random() < miss_rate:
            continue  # detector missed it — small/low-contrast target, sea state
        contacts.append({
            "contact_id": f"C{len(contacts):03d}",
            "lon": float(pos[0] + rng.normal(0, CONTACT_POSITION_NOISE_DEG)),
            "lat": float(pos[1] + rng.normal(0, CONTACT_POSITION_NOISE_DEG)),
            "truth_vessel_key": tr["vessel_key"],  # experiment bookkeeping only
            "is_false_detection": False,
        })
    n_false = int(round(false_detection_rate * max(len(contacts), 1)))
    for _ in range(n_false):
        contacts.append({
            "contact_id": f"C{len(contacts):03d}",
            "lon": float(rng.uniform(bbox["min_lon"], bbox["max_lon"])),
            "lat": float(rng.uniform(bbox["min_lat"], bbox["max_lat"])),
            "truth_vessel_key": None,
            "is_false_detection": True,
        })
    return contacts


def match_contacts(contacts: list[dict], manifest: dict, visible_keys: set[str],
                   gate_deg: float = GATE_RADIUS_DEG) -> dict:
    """Greedy one-to-one matching within a motion/positional gate, with an
    explicit unmatched option. Ambiguous pairs are retained in
    `alternatives` rather than silently resolved."""
    acquired = _parse(manifest["acquired_utc"])
    ais_positions = {}
    for tr in manifest["tracks"]:
        if tr["vessel_key"] not in visible_keys:
            continue  # hidden for this run
        pos = _interp_track_position(tr["fixes"], acquired)
        if pos is not None:
            ais_positions[tr["vessel_key"]] = pos

    pairs = []
    for c in contacts:
        for vkey, pos in ais_positions.items():
            d = float(np.hypot(c["lon"] - pos[0], c["lat"] - pos[1]))
            if d <= gate_deg:
                pairs.append((d, c["contact_id"], vkey))
    pairs.sort()

    used_contacts, used_vessels = set(), set()
    matched = {}
    alternatives = {}
    for d, cid, vkey in pairs:
        if cid in used_contacts or vkey in used_vessels:
            alternatives.setdefault(cid, []).append({"vessel_key": vkey, "distance_deg": round(d, 5)})
            continue
        matched[cid] = {"vessel_key": vkey, "distance_deg": round(d, 5)}
        used_contacts.add(cid)
        used_vessels.add(vkey)

    unmatched = [c["contact_id"] for c in contacts if c["contact_id"] not in matched]
    return {"matched": matched, "unmatched": unmatched, "alternatives": alternatives,
            "gate_radius_deg": gate_deg, "n_ais_visible": len(ais_positions)}


def _neighbourhood_keys(manifest: dict, centre: tuple[float, float], radius_deg: float) -> set[str]:
    acquired = _parse(manifest["acquired_utc"])
    out = set()
    for tr in manifest["tracks"]:
        pos = _interp_track_position(tr["fixes"], acquired)
        if pos is None:
            continue
        if np.hypot(pos[0] - centre[0], pos[1] - centre[1]) <= radius_deg:
            out.add(tr["vessel_key"])
    return out


def run_hidden_ais_experiment(case_dir: str, n_runs: int = 40, hide_fraction: float = 0.3,
                              seed: int = 4242) -> dict:
    """Hide AIS records, rerun matching, and report the three rates under both
    the selective and coverage-failure conditions."""
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    attribution_path = os.path.join(case_dir, "attribution_result.json")
    baseline_top = None
    if os.path.exists(attribution_path):
        with open(attribution_path) as f:
            baseline_top = json.load(f).get("top_candidate_id")

    rng = np.random.default_rng(seed)
    all_keys = [t["vessel_key"] for t in manifest["tracks"]]

    conditions = {}
    for condition in ("selective", "coverage_failure"):
        recovered, hidden_total = 0, 0
        false_alerts, unmatched_total = 0, 0
        mistaken_promotions, runs_scored = 0, 0

        for run_i in range(n_runs):
            contacts = synth_contacts(manifest, np.random.default_rng(seed + run_i))

            if condition == "selective":
                n_hide = max(1, int(round(hide_fraction * len(all_keys))))
                hidden = set(rng.choice(all_keys, size=n_hide, replace=False).tolist())
            else:
                # a whole neighbourhood goes dark at once — a receiver/provider
                # outage, not deliberate non-broadcasting by one ship
                seed_key = all_keys[int(rng.integers(0, len(all_keys)))]
                pos = _interp_track_position(
                    next(t for t in manifest["tracks"] if t["vessel_key"] == seed_key)["fixes"],
                    _parse(manifest["acquired_utc"]))
                if pos is None:
                    continue
                hidden = _neighbourhood_keys(manifest, pos, radius_deg=0.25)
                if not hidden:
                    continue

            visible = set(all_keys) - hidden
            result = match_contacts(contacts, manifest, visible)
            unmatched_ids = set(result["unmatched"])
            by_id = {c["contact_id"]: c for c in contacts}

            # --- hidden-AIS recovery rate ---
            # Denominator is every hidden vessel PRESENT IN THE SCENE, including
            # those the detector missed. Counting only vessels that produced a
            # contact would quietly exclude the detector's own failures and
            # inflate the rate to a structural 1.0.
            acq = _parse(manifest["acquired_utc"])
            contact_by_vessel = {c["truth_vessel_key"]: c["contact_id"] for c in contacts
                                 if c["truth_vessel_key"] is not None}
            for tr in manifest["tracks"]:
                vkey = tr["vessel_key"]
                if vkey not in hidden:
                    continue
                if _interp_track_position(tr["fixes"], acq) is None:
                    continue  # not in the scene at acquisition — nothing to recover
                hidden_total += 1
                cid = contact_by_vessel.get(vkey)
                if cid is not None and cid in unmatched_ids:
                    recovered += 1

            # --- false unmatched-alert rate ---
            for cid in unmatched_ids:
                c = by_id[cid]
                unmatched_total += 1
                # a contact declared unidentified whose broadcast WAS available
                if c["truth_vessel_key"] is not None and c["truth_vessel_key"] in visible:
                    false_alerts += 1

            # --- mistaken-promotion rate ---
            # Does hiding records cause an unrelated target to be advanced?
            # Promotion here means: the previously leading candidate is hidden,
            # and an unmatched contact unconnected to it becomes the highest
            # ranked object the analyst would look at.
            if baseline_top is not None:
                runs_scored += 1
                if baseline_top in hidden:
                    promoted = [by_id[cid]["truth_vessel_key"] for cid in unmatched_ids
                                if by_id[cid]["truth_vessel_key"] not in (baseline_top, None)]
                    if promoted:
                        mistaken_promotions += 1

        conditions[condition] = {
            "n_runs": n_runs,
            "hidden_ais_recovery_rate": round(recovered / hidden_total, 4) if hidden_total else None,
            "hidden_ais_recovery_n": f"{recovered}/{hidden_total}",
            "false_unmatched_alert_rate": round(false_alerts / unmatched_total, 4) if unmatched_total else None,
            "false_unmatched_alert_n": f"{false_alerts}/{unmatched_total}",
            "mistaken_promotion_rate": round(mistaken_promotions / runs_scored, 4) if runs_scored else None,
            "mistaken_promotion_n": f"{mistaken_promotions}/{runs_scored}",
        }

    out = {
        "incident_id": manifest["incident_id"],
        "operating_point": {
            "gate_radius_deg": GATE_RADIUS_DEG,
            "contact_position_noise_deg": CONTACT_POSITION_NOISE_DEG,
            "detector_miss_rate": 0.15,
            "false_detection_rate": 0.15,
            "hide_fraction_selective": hide_fraction,
            "coverage_failure_radius_deg": 0.25,
        },
        "conditions": conditions,
        "limits": [
            "Synthetic contacts from a stand-in detector, not a validated ship detector "
            "on real SAR. The rates measure the matching and coverage logic, not detection quality.",
            "A source vessel may have left the scene before acquisition. Same-scene ship "
            "detection cannot recover a contact absent from the image; the correct output "
            "in that situation stays unknown source.",
            "These are simulated hiding experiments. They are not evidence about real "
            "intentional non-broadcasting by any vessel.",
            "Neighbouring broadcast density is a weak proxy for reception quality; sparse "
            "traffic cannot establish good or bad coverage.",
        ],
    }
    with open(os.path.join(case_dir, "coverage_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    import sys
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/cases/case_0001"
    res = run_hidden_ais_experiment(case_dir)
    print(f"Hidden-AIS experiment — {res['incident_id']}")
    op = res["operating_point"]
    print(f"  operating point: gate {op['gate_radius_deg']} deg, "
          f"contact noise {op['contact_position_noise_deg']} deg\n")
    for cond, r in res["conditions"].items():
        print(f"  [{cond}] over {r['n_runs']} runs")
        print(f"    hidden-AIS recovery rate    {r['hidden_ais_recovery_rate']}  ({r['hidden_ais_recovery_n']})")
        print(f"    false unmatched-alert rate  {r['false_unmatched_alert_rate']}  ({r['false_unmatched_alert_n']})")
        print(f"    mistaken-promotion rate     {r['mistaken_promotion_rate']}  ({r['mistaken_promotion_n']})")
