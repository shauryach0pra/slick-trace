"""
Ask Slick Trace — grounded NLP query layer (masterplan p.5).

Deliberately NOT a chatbot wrapping an LLM. Per the masterplan:
  "Use deterministic answer templates first ... Never execute arbitrary
   SQL or code produced from user text or retrieved documents."

This module:
  1. Parses a question into one of a FIXED set of intents (regex/keyword
     based — no model call, so behavior is fully inspectable and testable).
  2. Resolves each intent via a fixed, read-only Python function over the
     already-computed incident artifacts (manifest, historical_mapping,
     attribution_result, naive_baseline_result) — the stand-in for
     "allowlisted read-only SQL over DuckDB" the masterplan specifies; we
     don't have DuckDB wired up yet (see step 6), so this queries the JSON
     artifacts directly, but the intent/resolver split is the same shape
     the DuckDB version will have.
  3. Always returns the interpreted filters (so a user can see WHY the
     system answered the way it did) and citations (which record/file the
     answer came from) alongside the templated answer text.
  4. Explicitly refuses (rather than guesses) when a question doesn't match
     any supported intent, or when supported but the data can't answer it
     (e.g. similarity search with only one incident indexed).
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slicktrace_core.hindcast import _interp_track_position, _parse, build_backward_envelope
import numpy as np
from scipy.spatial import cKDTree


@dataclass
class QueryResult:
    question: str
    intent: str
    filters: dict = field(default_factory=dict)
    answer: str = ""
    citations: list[str] = field(default_factory=list)
    supported: bool = True


class CaseKB:
    """Loads every artifact produced by steps 1-4 for one incident."""

    def __init__(self, case_dir: str):
        self.case_dir = case_dir
        with open(os.path.join(case_dir, "manifest.json")) as f:
            self.manifest = json.load(f)
        self.historical_mapping = self._load_optional("historical_mapping.json")
        self.attribution = self._load_optional("attribution_result.json")
        self.naive_baseline = self._load_optional("naive_baseline_result.json")
        self.fragility = self._load_optional("fragility_result.json")
        self.forecast = self._load_optional("forecast_result.json")
        self.coverage = self._load_optional("coverage_result.json")
        self.next_observation = self._load_optional("next_observation_result.json")
        self.tracks_by_key = {t["vessel_key"]: t for t in self.manifest["tracks"]}
        self._envelope_snapshots = None  # computed lazily, only if a time-window query needs it

    def _load_optional(self, fname):
        path = os.path.join(self.case_dir, fname)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    @property
    def envelope_snapshots(self):
        if self._envelope_snapshots is None:
            self._envelope_snapshots = build_backward_envelope(self.manifest)
        return self._envelope_snapshots


# ---------------------------------------------------------------- parsing --

_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
# Matches MMSI-style numeric identifiers (the current vessel_key format) and
# the legacy V-XXX-NNN keys, so a manifest adapted from another source with
# alphanumeric keys still resolves.
_VESSEL_ID_RE = re.compile(r"\b(?:\d{7,9}|V-[A-Z]+-?\d*)\b", re.IGNORECASE)

RANK_WORDS_TOP = {"top", "leading", "first", "best", "highest", "preferred"}
RANK_WORDS_SECOND = {"second", "runner-up", "runner up", "next", "alternative"}
RANK_WORDS_LAST = {"last", "worst", "lowest", "bottom"}


def _extract_times(question: str) -> list[tuple[int, int]]:
    return [(int(h), int(m)) for h, m in _TIME_RE.findall(question)]


def _extract_vessel_ids(question: str, known_keys: list[str]) -> list[str]:
    hits = []
    for m in _VESSEL_ID_RE.findall(question):
        for k in known_keys:
            if k.lower().startswith(m.lower()) or m.lower() in k.lower():
                if k not in hits:
                    hits.append(k)
    return hits


def parse_intent(question: str) -> str:
    q = question.lower()
    if re.search(r"which vessels?.*(cross|enter|were|within).*(zone|envelope|area)", q) or \
       ("vessel" in q and len(_extract_times(question)) >= 2):
        return "time_window_vessels"
    if re.search(r"why (is|does|did|was)\b.*(above|ahead|beat|rank(ed)? (higher|above|before)|preferred over|over)", q):
        return "candidate_comparison"
    if re.search(r"(top|leading|best|most likely) candidate|which vessel (is|was) the source|who (is|was) the source", q):
        return "top_candidate"
    if re.search(r"(list|show|which).*(candidates|candidate vessels)|candidates for this incident", q):
        return "candidate_list"
    if re.search(r"(current|wind).*(field|data).*(source|used)|forcing.*(source|used)|source.*forcing", q):
        return "forcing_provenance"
    # Forecast is tested BEFORE stability: "what sensitive areas are at risk"
    # otherwise matches the stability pattern on the word "sensitive" and
    # answers a question about perturbation grids instead of about the coast.
    if re.search(r"(where will|where does|forecast|drift to|next \d+ ?h|exposure|shoreline|"
                 r"coast|sensitive area|at risk|fishing ground|mangrove)", q):
        return "forecast_exposure"
    if re.search(r"(how )?(stable|robust|fragil|sensitiv)", q) or \
       re.search(r"what would (have to )?(change|be different)", q) or \
       "change the (answer|ranking|result)" in q:
        return "rank_stability"
    if re.search(r"(unmatched|unidentified|dark (vessel|ship|target)|not broadcasting|"
                 r"radar contact|sar contact|hidden ais|coverage)", q):
        return "unmatched_contacts"
    if re.search(r"(next observation|when should|observe again|another (image|pass|"
                 r"observation)|re-?image)", q):
        return "next_observation"
    if re.search(r"(route|history|track|position)s?.*(of|for)\b", q) or "24 hours before" in q:
        return "vessel_history"
    if re.search(r"similar.*(slick|case|incident)|find cases similar", q):
        return "similarity_search"
    return "unsupported"


# ------------------------------------------------------------- resolvers --

def _resolve_time_window_vessels(kb: CaseKB, question: str) -> QueryResult:
    times = _extract_times(question)
    acquired = _parse(kb.manifest["acquired_utc"])
    if len(times) < 2:
        return QueryResult(question, "time_window_vessels", supported=False,
                            answer="I need a start and end time (e.g. '02:00 to 05:00 UTC') to run this query.")
    (h1, m1), (h2, m2) = times[0], times[1]
    window_start = acquired - timedelta(hours=24)  # full backward search range

    def _window_for_date(d):
        s = datetime.combine(d, datetime.min.time()).replace(hour=h1, minute=m1, tzinfo=acquired.tzinfo)
        e = datetime.combine(d, datetime.min.time()).replace(hour=h2, minute=m2, tzinfo=acquired.tzinfo)
        if e < s:
            e += timedelta(days=1)
        return s, e

    # the requested HH:MM could fall on the acquisition date or the day
    # before it, since the backward envelope crosses midnight — pick
    # whichever placement actually overlaps the searchable window
    candidates = [_window_for_date(acquired.date()), _window_for_date(acquired.date() - timedelta(days=1))]
    overlapping = [(s, e) for s, e in candidates if e >= window_start and s <= acquired]
    t_start, t_end = overlapping[0] if overlapping else candidates[0]

    inclusion_radius = 0.045
    hits = []
    for snap in kb.envelope_snapshots:
        if not (t_start <= snap.time_utc <= t_end):
            continue
        tree = cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
        for tr in kb.manifest["tracks"]:
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                continue
            dist, _ = tree.query([pos[0], pos[1]])
            if dist <= inclusion_radius:
                hits.append((tr["vessel_key"], snap.time_utc, float(dist)))

    filters = {"time_start_utc": t_start.isoformat(), "time_end_utc": t_end.isoformat(),
               "inclusion_radius_deg": inclusion_radius}
    if not hits:
        answer = (f"No vessels were found inside the origin envelope between "
                  f"{t_start.strftime('%H:%M')} and {t_end.strftime('%H:%M')} UTC.")
    else:
        seen = sorted({h[0] for h in hits})
        detail = "; ".join(f"{v} at {t.strftime('%H:%M')} UTC" for v, t, _ in hits)
        answer = f"Vessels inside the origin envelope in this window: {', '.join(seen)}. ({detail})"
    citations = [f"historical_mapping (recomputed) incident={kb.manifest['incident_id']}"] + \
                [f"vessel={v} snapshot_time={t.isoformat()}" for v, t, _ in hits]
    return QueryResult(question, "time_window_vessels", filters, answer, citations)


def _pick_ranked(kb: CaseKB, word: str) -> dict | None:
    if kb.attribution is None or not kb.attribution["ranking"]:
        return None
    ranking = kb.attribution["ranking"]
    if word in RANK_WORDS_TOP:
        return ranking[0]
    if word in RANK_WORDS_SECOND:
        return ranking[1] if len(ranking) > 1 else None
    if word in RANK_WORDS_LAST:
        return ranking[-1]
    return None


def _resolve_candidate_comparison(kb: CaseKB, question: str) -> QueryResult:
    if kb.attribution is None:
        return QueryResult(question, "candidate_comparison", supported=False,
                            answer="No attribution ranking has been computed for this incident yet.")
    known_keys = list(kb.tracks_by_key.keys())
    explicit = _extract_vessel_ids(question, known_keys)
    q = question.lower()
    refs = list(explicit)
    if len(refs) < 2:
        for word_set, label in [(RANK_WORDS_TOP, "top"), (RANK_WORDS_SECOND, "second"), (RANK_WORDS_LAST, "last")]:
            if any(w in q for w in word_set):
                r = _pick_ranked(kb, next(w for w in word_set if w in q))
                if r and r["vessel_key"] not in refs:
                    refs.append(r["vessel_key"])
    if len(refs) < 2:
        return QueryResult(question, "candidate_comparison", supported=False,
                            answer="Please specify two candidates to compare, by vessel ID or by rank "
                                   "(e.g. 'the top candidate' and 'the second candidate').")

    ranking_by_key = {r["vessel_key"]: r for r in kb.attribution["ranking"]}
    a_key, b_key = refs[0], refs[1]
    a, b = ranking_by_key.get(a_key), ranking_by_key.get(b_key)
    if a is None or b is None:
        return QueryResult(question, "candidate_comparison", supported=False,
                            answer=f"One of {a_key}, {b_key} was not part of the attribution ranking "
                                   f"(it may have been filtered out as excluded or unassessed).")

    answer = (f"{a_key} ranks above {b_key}: mean IoU {a['mean_iou']:.2f} vs {b['mean_iou']:.2f}, "
              f"mean loss {a['mean_loss']:.3f} vs {b['mean_loss']:.3f}, winning {a['ensemble_win_count']}/"
              f"{a['n_ensemble']} ensemble variants vs {b['ensemble_win_count']}/{b['n_ensemble']}. "
              f"Both were tested under the same {a['n_ensemble']} shared forcing perturbations.")
    if a["mean_loss"] > b["mean_loss"]:
        answer = (f"Careful: {b_key} actually has the lower loss ({b['mean_loss']:.3f} vs "
                  f"{a['mean_loss']:.3f}) in the current ranking — {a_key} is not actually ahead of it.")
    citations = [f"attribution_result.json candidate={a_key} run={a['candidate_id']}",
                 f"attribution_result.json candidate={b_key} run={b['candidate_id']}"]
    return QueryResult(question, "candidate_comparison",
                        {"compared": [a_key, b_key]}, answer, citations)


def _resolve_top_candidate(kb: CaseKB, question: str) -> QueryResult:
    if kb.attribution is None:
        return QueryResult(question, "top_candidate", supported=False,
                            answer="No attribution ranking has been computed for this incident yet.")
    if kb.attribution["unknown_source"]:
        answer = ("No candidate cleared the absolute fit gate "
                  f"(IoU >= {kb.attribution['abstention_iou_gate']}) — reporting UNKNOWN SOURCE "
                  "rather than naming a vessel.")
        citations = ["attribution_result.json field=unknown_source"]
    else:
        top = kb.attribution["ranking"][0]
        runner_up = kb.attribution["ranking"][1] if len(kb.attribution["ranking"]) > 1 else None
        answer = (f"Top candidate: {top['vessel_key']} (mean IoU {top['mean_iou']:.2f}, "
                  f"won {top['ensemble_win_count']}/{top['n_ensemble']} ensemble variants, "
                  f"release hypothesis: {top['duration_hours']}h "
                  f"{'continuous' if top['is_continuous'] else 'pulse'}).")
        if runner_up:
            answer += f" Runner-up: {runner_up['vessel_key']} (IoU {runner_up['mean_iou']:.2f})."
        citations = [f"attribution_result.json candidate={top['vessel_key']} run={top['candidate_id']}"]
    return QueryResult(question, "top_candidate", {}, answer, citations)


def _resolve_candidate_list(kb: CaseKB, question: str) -> QueryResult:
    if kb.historical_mapping is None:
        return QueryResult(question, "candidate_list", supported=False,
                            answer="No historical mapping has been computed for this incident yet.")
    cands = [a for a in kb.historical_mapping["assessments"] if a["status"] == "candidate"]
    by_state = {s: [a["vessel_key"] for a in kb.historical_mapping["assessments"] if a["status"] == s]
                for s in ("candidate", "excluded", "unassessed")}

    def _keys(state: str) -> str:
        return ", ".join(by_state[state]) or "none"

    answer = (f"{len(cands)} candidate(s) survived historical filtering: {_keys('candidate')}. "
              f"{len(by_state['excluded'])} excluded (track data at every queried time, never "
              f"inside): {_keys('excluded')}. {len(by_state['unassessed'])} unassessed (never "
              f"inside where data exists, but data missing at some queried times; missing "
              f"evidence is not exoneration): {_keys('unassessed')}.")
    citations = [f"historical_mapping.json vessel={a['vessel_key']}" for a in cands]
    return QueryResult(question, "candidate_list", {}, answer, citations)


def _resolve_forcing_provenance(kb: CaseKB, question: str) -> QueryResult:
    prov = kb.manifest.get("provenance", {})
    answer = (f"Wind/current field: {kb.manifest['forcing_path']}. "
              f"Provenance status: {prov.get('status', 'unknown')}, source: {prov.get('source', 'unknown')}. "
              f"Model: constant advection + spatially smoothed noise (synthetic — not a reanalysis product).")
    citations = [f"manifest.json field=forcing_path incident={kb.manifest['incident_id']}"]
    return QueryResult(question, "forcing_provenance", {}, answer, citations)


def _resolve_vessel_history(kb: CaseKB, question: str) -> QueryResult:
    known_keys = list(kb.tracks_by_key.keys())
    explicit = _extract_vessel_ids(question, known_keys)
    if not explicit:
        return QueryResult(question, "vessel_history", supported=False,
                            answer=f"Which vessel? Known IDs in this incident: {', '.join(known_keys)}.")
    vkey = explicit[0]
    fixes = kb.tracks_by_key[vkey]["fixes"]
    answer = (f"{vkey} has {len(fixes)} recorded fixes from "
              f"{fixes[0]['t_utc']} to {fixes[-1]['t_utc']}. "
              f"Route: " + " -> ".join(f"({f['lon']:.3f},{f['lat']:.3f} @ {f['t_utc'][11:16]})" for f in fixes))
    citations = [f"manifest.json vessel={vkey}"]
    return QueryResult(question, "vessel_history", {"vessel_key": vkey}, answer, citations)


def _resolve_rank_stability(kb: CaseKB, question: str) -> QueryResult:
    if kb.fragility is None:
        return QueryResult(question, "rank_stability", supported=False,
                            answer="No rank-fragility analysis has been computed for this "
                                   "incident yet. Run the fragility stage first.")
    f = kb.fragility
    if not f.get("testable"):
        return QueryResult(question, "rank_stability", supported=False,
                            answer=f"Rank stability is not testable here: {f.get('reason')}")
    parts = [f"The leading candidate held its position in "
             f"{f['lead_retained_fraction'] * 100:.0f}% of {f['n_points_tested']} tested "
             f"perturbations."]
    if f.get("flip_found"):
        sf = f["smallest_flip"]
        changes = ", ".join(f"{k} = {v}" for k, v in sf["changed_axes"].items())
        parts.append(f"The smallest tested change that flips the leader is {changes} "
                     f"(standardised magnitude {sf['magnitude']}), after which "
                     f"{sf['top_candidate']} leads instead.")
    else:
        parts.append("No tested perturbation changed the leader.")
    parts.append("This is a sensitivity counterfactual, not proof of causal responsibility, "
                 "and only single- and two-axis perturbations were tested.")
    filters = {"n_points_tested": f["n_points_tested"],
               "axes_tested": list(f.get("axes", {}).keys())}
    citations = [f"fragility_result.json incident={f['incident_id']}"]
    if f.get("flip_found"):
        citations.append(f"fragility_result.json point={f['smallest_flip']['point_id']}")
    return QueryResult(question, "rank_stability", filters, " ".join(parts), citations)


def _resolve_forecast_exposure(kb: CaseKB, question: str) -> QueryResult:
    if kb.forecast is None:
        return QueryResult(question, "forecast_exposure", supported=False,
                            answer="No forward exposure forecast has been computed for this "
                                   "incident yet.")
    fc = kb.forecast
    lines = []
    for h in fc["horizons"]:
        contacts = [e["name"] for e in h["sensitive_area_exposure"] if e["any_contact"]]
        lines.append(f"+{h['horizon_hours']}h: modelled envelope {h['envelope_area_km2']} km²"
                     + (f", intersects {', '.join(contacts)}" if contacts else ", no sensitive-area contact"))
    shore = fc.get("first_modelled_shoreline_contact_h")
    answer = ("Modelled surface exposure under the tested forcing ensemble. " + " | ".join(lines)
              + ". First modelled shoreline contact: "
              + (f"+{shore}h." if shore else "none within the tested horizons.")
              + " These are modelled exposure and arrival intervals, not guaranteed damage; "
                "weathering and shoreline interaction are not modelled.")
    filters = {"horizons_hours": [h["horizon_hours"] for h in fc["horizons"]],
               "n_ensemble_variants": fc["n_ensemble_variants"]}
    return QueryResult(question, "forecast_exposure", filters, answer,
                        [f"forecast_result.json incident={fc['incident_id']}"])


def _resolve_unmatched_contacts(kb: CaseKB, question: str) -> QueryResult:
    if kb.coverage is None:
        return QueryResult(question, "unmatched_contacts", supported=False,
                            answer="No coverage-aware contact matching has been run for this "
                                   "incident yet.")
    cov = kb.coverage
    op = cov["operating_point"]
    sel = cov["conditions"]["selective"]
    fail = cov["conditions"]["coverage_failure"]
    answer = (f"At a {op['gate_radius_deg']}° match gate: hidden-AIS recovery rate "
              f"{sel['hidden_ais_recovery_rate']} ({sel['hidden_ais_recovery_n']}), false "
              f"unmatched-alert rate {sel['false_unmatched_alert_rate']} "
              f"({sel['false_unmatched_alert_n']}), mistaken-promotion rate "
              f"{sel['mistaken_promotion_rate']} ({sel['mistaken_promotion_n']}) under selective "
              f"hiding; under a simulated coverage failure those are "
              f"{fail['hidden_ais_recovery_rate']}, {fail['false_unmatched_alert_rate']} and "
              f"{fail['mistaken_promotion_rate']}. An unmatched contact is an unresolved "
              f"identity, not a suspect: it may be a vessel not broadcasting, a timing or "
              f"positioning mismatch, a fixed object or a false detection.")
    return QueryResult(question, "unmatched_contacts", {"operating_point": op}, answer,
                        [f"coverage_result.json incident={cov['incident_id']}"])


def _resolve_next_observation(kb: CaseKB, question: str) -> QueryResult:
    if kb.next_observation is None:
        return QueryResult(question, "next_observation", supported=False,
                            answer="No next-observation analysis has been computed for this "
                                   "incident yet.")
    nx = kb.next_observation
    if not nx.get("applicable"):
        return QueryResult(question, "next_observation", supported=False,
                            answer=f"Not applicable here: {nx.get('reason')}")
    rec = nx["recommended_window"]
    answer = (f"The most informative tested window is +{rec['horizon_hours']}h "
              f"({rec['valid_utc']}), where the two leading hypotheses disagree most "
              f"(disagreement score {rec['disagreement_score']}; predicted footprint overlap "
              f"IoU {rec['predicted_overlap_iou']}). {rec['schedule_status']}. The system "
              f"recommends evidence; it does not task satellites and cannot confirm an "
              f"acquisition is available then.")
    return QueryResult(question, "next_observation",
                        {"windows_tested": [w["horizon_hours"] for w in nx["windows"]]},
                        answer, [f"next_observation_result.json incident={nx['incident_id']}"])


def _resolve_similarity_search(kb: CaseKB, question: str) -> QueryResult:
    return QueryResult(question, "similarity_search", supported=False,
                        answer="Similarity search needs an indexed corpus of prior incidents. Only "
                               f"{kb.manifest['incident_id']} is indexed right now, so there is nothing "
                               "to compare it against yet — this is not implemented as a guess.")


_RESOLVERS = {
    "time_window_vessels": _resolve_time_window_vessels,
    "candidate_comparison": _resolve_candidate_comparison,
    "top_candidate": _resolve_top_candidate,
    "candidate_list": _resolve_candidate_list,
    "forcing_provenance": _resolve_forcing_provenance,
    "vessel_history": _resolve_vessel_history,
    "similarity_search": _resolve_similarity_search,
    "rank_stability": _resolve_rank_stability,
    "forecast_exposure": _resolve_forecast_exposure,
    "unmatched_contacts": _resolve_unmatched_contacts,
    "next_observation": _resolve_next_observation,
}


def ask(kb: CaseKB, question: str) -> QueryResult:
    intent = parse_intent(question)
    if intent == "unsupported":
        return QueryResult(question, "unsupported", supported=False,
                            answer="I don't have a supported query template for this question. "
                                   "Supported topics: candidate vessels, the top candidate and why, "
                                   "a specific vessel's route, rank stability, forward exposure, "
                                   "unmatched contacts, the recommended next observation, and the "
                                   "forcing-field source.")
    return _RESOLVERS[intent](kb, question)


if __name__ == "__main__":
    kb = CaseKB("data/cases/case_0001")
    demo_questions = [
        "Which vessels crossed the likely origin zone from 22:00 to 23:59 UTC?",
        "What is the top candidate and why?",
        "Why is the top candidate above the second candidate?",
        "List the candidates for this incident.",
        "Find the current-field source used in this report.",
        "Show the route for V-DECOY-NEAR.",
        "Find cases similar to this curved slick.",
        "How stable is this ranking?",
        "Where will the slick drift in the next 24 hours?",
        "Are there any unmatched radar contacts?",
        "When should we observe again?",
        "What's the weather like in Mumbai today?",  # deliberately unsupported
    ]
    for q in demo_questions:
        r = ask(kb, q)
        print(f"\nQ: {r.question}")
        print(f"   intent: {r.intent}  supported: {r.supported}")
        if r.filters:
            print(f"   filters: {r.filters}")
        print(f"   A: {r.answer}")
        if r.citations:
            print(f"   citations: {r.citations}")
