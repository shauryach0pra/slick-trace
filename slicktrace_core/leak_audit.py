"""
Leak audit: can a rule that uses NO physics pick the true source?

Forward replay earns its headline only if the benchmark does not hand the
answer over through something unrelated to the slick. Each rule below looks at
track bookkeeping alone - how many fixes, when they start and stop, how fast
and how straight the vessel moves, what its reported speed says - and names
one vessel per case. A rule that names the true source far more often than
chance means the generator is leaking the answer through that attribute.

Rules and the threshold were fixed before the generator was changed:
a rule that picks the source in 3 or more of the source-present cases is
flagged. Ties count as misses: a rule that cannot single out one vessel has
not picked anyone.
"""
from __future__ import annotations
import json, math, os
from datetime import datetime

FLAG_AT = 3


def _t(s):
    return datetime.fromisoformat(s)


def _km(a, b):
    kx = 111.0 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 111.0)


def _features(track, slick_c):
    f = track["fixes"]
    pts = [(x["lon"], x["lat"]) for x in f]
    hours = (_t(f[-1]["t_utc"]) - _t(f[0]["t_utc"])).total_seconds() / 3600 if len(f) > 1 else 0.0
    path = sum(_km(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    net = _km(pts[0], pts[-1]) if len(pts) > 1 else 0.0
    actual_kn = (path / hours) / 1.852 if hours else 0.0
    reported_kn = sum(x["sog_knots"] for x in f) / len(f)
    # Each quantity at the resolution it is reported to. Comparing floats at
    # full precision let coordinate rounding (1e-5 degrees) break ties between
    # vessels that are, at any meaningful precision, identical - two rules
    # "found" the source that way on noise alone.
    return {
        "n_fixes": len(f),
        "first_fix": _t(f[0]["t_utc"]).timestamp(),
        "last_fix": _t(f[-1]["t_utc"]).timestamp(),
        "span_h": round(hours, 2),
        "actual_speed_kn": round(actual_kn, 1),
        "straightness": round((net / path) if path > 0 else 1.0, 3),
        "speed_mismatch_kn": round(abs(reported_kn - actual_kn), 1),
        "nearest_to_slick_km": round(min(_km(p, slick_c) for p in pts), 1),
        "ship_type": track.get("ship_type"),
    }


def _pick(values, how):
    """Key of the single vessel the rule selects, or None on a tie."""
    if how.startswith("only:"):                     # the one vessel of a given type
        keys = [k for k, v in values.items() if v == how[5:]]
        return keys[0] if len(keys) == 1 else None
    if how == "unique":
        counts = {}
        for v in values.values():
            counts[v] = counts.get(v, 0) + 1
        singles = [k for k, v in values.items() if counts[v] == 1]
        return singles[0] if len(singles) == 1 else None
    # min / max, or the runner-up on that axis ("min2" / "max2"). The runner-up
    # rules exist because an always-extreme decoy can hide a source at rank 2:
    # the first leak found here was "second-fewest fixes", not "fewest".
    distinct = sorted(set(round(v, 9) for v in values.values()), reverse=how.startswith("max"))
    rank = 1 if how.endswith("2") else 0
    if len(distinct) <= rank:
        return None
    target = distinct[rank]
    keys = [k for k, v in values.items() if abs(round(v, 9) - target) < 1e-9]
    return keys[0] if len(keys) == 1 else None


RULES = [("only vessel with a unique fix count", "n_fixes", "unique"),
         ("only vessel of its ship type", "ship_type", "unique"),
         ("the only tanker (tankers carry oil)", "ship_type", "only:tanker")]
for _label, _feat in [("fix count", "n_fixes"), ("first fix time", "first_fix"),
                      ("last fix time", "last_fix"), ("track span", "span_h"),
                      ("actual speed", "actual_speed_kn"), ("straightness", "straightness"),
                      ("reported-vs-actual speed gap", "speed_mismatch_kn"),
                      ("closest approach to the slick", "nearest_to_slick_km")]:
    for _how, _word in [("min", "lowest"), ("min2", "second-lowest"),
                        ("max", "highest"), ("max2", "second-highest")]:
        RULES.append((f"{_word} {_label}", _feat, _how))


def audit(cases_root="data/cases"):
    cases = []
    for cid in sorted(os.listdir(cases_root)):
        d = os.path.join(cases_root, cid)
        truth = json.load(open(os.path.join(d, "truth.json")))
        if not truth.get("true_vessel_key"):
            continue
        manifest = json.load(open(os.path.join(d, "manifest.json")))
        det = json.load(open(os.path.join(d, "detection_result.json")))
        c = det["geometry"]["centroid"]
        feats = {t["vessel_key"]: _features(t, (c[0], c[1])) for t in manifest["tracks"]}
        cases.append((cid, truth["true_vessel_key"], feats))
    rows = []
    for name, feat, how in RULES:
        hits = [cid for cid, true_key, feats in cases
                if _pick({k: v[feat] for k, v in feats.items()}, how) == true_key]
        rows.append({"rule": name, "hits": len(hits), "n": len(cases),
                     "flagged": len(hits) >= FLAG_AT, "cases": hits})
    # Probability a rule that picks one vessel at random reaches FLAG_AT hits
    probs = [1.0 / len(feats) for _, _, feats in cases]
    dist = [1.0]
    for p in probs:
        dist = [a * (1 - p) + (dist[i - 1] * p if i else 0.0) for i, a in enumerate(dist + [0.0])]
    p_chance = sum(dist[FLAG_AT:])
    return {"flag_at": FLAG_AT, "n_source_present": len(cases), "rules": rows,
            "chance_p_per_rule": round(p_chance, 4),
            "chance_expected_flags": round(p_chance * len(rows), 2),
            "any_flagged": any(r["flagged"] for r in rows),
            "note": "Rules use track bookkeeping only, no physics. Ties count as misses. "
                    f"A rule picking the true source in {FLAG_AT} or more cases is flagged as a leak."}


if __name__ == "__main__":
    r = audit()
    for row in r["rules"]:
        print(f"  {'LEAK ' if row['flagged'] else '     '} {row['hits']}/{row['n']}  {row['rule']}")
    print("any rule flagged:", r["any_flagged"])
