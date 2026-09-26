"""
Track display: what the map draws for each vessel, derived in the pipeline.

For every vessel in a case this records three things the interface needs and
must not compute itself.

  gaps          Windows inside the declared AIS window with no usable position
                report, each [start, end] with a kind: leading (window start to
                first fix), internal (consecutive fixes more than twice the
                track's median step apart), trailing (last fix to window end),
                or no_fixes. A fix whose position is a reserved sentinel
                (ais_quality) counts as missing. A gap is "no position
                reported": missing evidence, not proof of an outage (A6) and
                never culpability (A7).

  display_path  A centripetal Catmull-Rom curve (alpha 0.5) through the usable
                fixes, three points inserted per step, for rendering only. It
                passes through every fix, never bridges a gap, and is used by
                no analysis: the hindcast and forward replay interpolate
                linearly between the original fixes, which remain the source of
                truth. max_display_deviation_m says how far the curve strays
                from those straight segments.

  vessel_type   As the vessel's AIS static message (message 5) reports it, with
                its source. Never inferred: an MMSI does not encode ship type,
                so a vessel without static data stays "not reported".
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta

from slicktrace_core.ais_quality import validate_fix

DECIMALS = 5
INSERTED_PER_STEP = 3
INTERNAL_GAP_FACTOR = 2.0
METRES_PER_DEG = 6_371_008.8 * math.pi / 180.0
VESSEL_TYPE_SOURCE = ("not reported: an MMSI does not encode ship type, and this source "
                      "carries no AIS static data (message 5)")

GAP_RULE = ("Windows inside the declared AIS window with no usable position report. "
            "leading: window start to first fix; internal: consecutive fixes more than "
            f"{INTERNAL_GAP_FACTOR:g} x the track's median step apart; trailing: last fix to "
            "window end; no_fixes: no usable fix in the window. A sentinel position counts "
            "as missing. No position reported is missing evidence, not proof of an outage.")

DISPLAY_RULE = (f"Centripetal Catmull-Rom (alpha 0.5) through the usable fixes, "
                f"{INSERTED_PER_STEP} points inserted per step, never across a gap. For "
                "rendering only; every analysis uses the original fixes with straight-line "
                "interpolation.")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _gap(kind: str, start: datetime, end: datetime) -> dict:
    return {"kind": kind, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "hours": round((end - start).total_seconds() / 3600.0, 4)}


def find_gaps(fixes: list[dict], window_start: datetime, window_end: datetime):
    """(gaps, usable fixes inside the window, internal threshold in minutes)."""
    usable = sorted((f for f in fixes if validate_fix(f)["usable_position"]
                     and window_start <= _t(f["t_utc"]) <= window_end),
                    key=lambda f: _t(f["t_utc"]))
    if not usable:
        return [_gap("no_fixes", window_start, window_end)], [], None
    times = [_t(f["t_utc"]) for f in usable]
    steps = sorted((b - a).total_seconds() / 60.0 for a, b in zip(times, times[1:]))
    threshold = INTERNAL_GAP_FACTOR * steps[len(steps) // 2] if steps else None
    gaps = []
    if times[0] > window_start:
        gaps.append(_gap("leading", window_start, times[0]))
    for a, b in zip(times, times[1:]):
        if threshold is not None and (b - a).total_seconds() / 60.0 > threshold:
            gaps.append(_gap("internal", a, b))
    if times[-1] < window_end:
        gaps.append(_gap("trailing", times[-1], window_end))
    return gaps, usable, threshold


def _catmull_rom(p0, p1, p2, p3, n: int) -> list[tuple[float, float]]:
    """n points strictly between p1 and p2 on the centripetal Catmull-Rom curve.
    Knot spacing is sqrt(chord), computed with sqrt only so every platform
    rounds it identically."""
    def knot(a, b):
        return math.sqrt(max(math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2), 1e-12))

    t0 = 0.0
    t1 = t0 + knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)

    def lerp(a, b, ta, tb, t):
        wa, wb = (tb - t) / (tb - ta), (t - ta) / (tb - ta)
        return (wa * a[0] + wb * b[0], wa * a[1] + wb * b[1])

    out = []
    for k in range(1, n + 1):
        t = t1 + (t2 - t1) * k / (n + 1)
        a1, a2, a3 = lerp(p0, p1, t0, t1, t), lerp(p1, p2, t1, t2, t), lerp(p2, p3, t2, t3, t)
        b1, b2 = lerp(a1, a2, t0, t2, t), lerp(a2, a3, t1, t3, t)
        out.append(lerp(b1, b2, t1, t2, t))
    return out


def _segment_distance_m(p, a, b) -> float:
    """Distance from p to segment ab, all in local metres."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    s = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    ex, ey = p[0] - (a[0] + s * dx), p[1] - (a[1] + s * dy)
    return math.sqrt(ex * ex + ey * ey)


def display_path(usable: list[dict], gaps: list[dict], lat0: float):
    """(path points [lon, lat, t_utc, is_fix], max deviation from straight segments in m)."""
    kx = math.cos(math.radians(lat0))
    breaks = {_t(g["start_utc"]) for g in gaps if g["kind"] == "internal"}
    segments, cur = [], []
    for f in usable:
        cur.append(f)
        if _t(f["t_utc"]) in breaks:
            segments.append(cur)
            cur = []
    if cur:
        segments.append(cur)

    path, worst = [], 0.0
    for seg in segments:
        P = [(f["lon"] * kx, f["lat"]) for f in seg]
        T = [_t(f["t_utc"]) for f in seg]
        for i in range(len(seg)):
            path.append([round(seg[i]["lon"], DECIMALS), round(seg[i]["lat"], DECIMALS),
                         seg[i]["t_utc"], True])
            if i == len(seg) - 1:
                break
            p0 = P[i - 1] if i > 0 else (2 * P[0][0] - P[1][0], 2 * P[0][1] - P[1][1])
            p3 = P[i + 2] if i + 2 < len(P) else (2 * P[-1][0] - P[-2][0], 2 * P[-1][1] - P[-2][1])
            for k, (x, y) in enumerate(_catmull_rom(p0, P[i], P[i + 1], p3, INSERTED_PER_STEP), 1):
                t = T[i] + (T[i + 1] - T[i]) * (k / (INSERTED_PER_STEP + 1))
                path.append([round(x / kx, DECIMALS), round(y, DECIMALS), t.isoformat(), False])
                a = (P[i][0] * METRES_PER_DEG, P[i][1] * METRES_PER_DEG)
                b = (P[i + 1][0] * METRES_PER_DEG, P[i + 1][1] * METRES_PER_DEG)
                worst = max(worst, _segment_distance_m((x * METRES_PER_DEG, y * METRES_PER_DEG), a, b))
    return path, round(worst)


def run_track_display(case_dir: str) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    ws, we = _t(manifest["ais_window_start_utc"]), _t(manifest["ais_window_end_utc"])
    b = manifest["bbox"]
    lat0 = (b["min_lat"] + b["max_lat"]) / 2.0
    vessels = []
    for tr in manifest["tracks"]:
        gaps, usable, threshold = find_gaps(tr["fixes"], ws, we)
        path, deviation = display_path(usable, gaps, lat0)
        vessels.append({
            "vessel_key": tr["vessel_key"],
            "vessel_type": tr.get("ship_type"),
            "vessel_type_source": tr.get("static_source") or VESSEL_TYPE_SOURCE,
            "n_fixes": len(tr["fixes"]),
            "n_usable_fixes": len(usable),
            "internal_gap_threshold_minutes": threshold,
            "gaps": gaps,
            "hours_without_position": round(sum(g["hours"] for g in gaps), 4),
            "n_display_points": len(path),
            "max_display_deviation_m": deviation,
            "display_path": path,
        })
    out = {
        "incident_id": manifest["incident_id"],
        "ais_window_start_utc": manifest["ais_window_start_utc"],
        "ais_window_end_utc": manifest["ais_window_end_utc"],
        "gap_rule": GAP_RULE,
        "display_rule": DISPLAY_RULE,
        "vessels": vessels,
    }
    with open(os.path.join(case_dir, "track_display.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\n")
    return out
