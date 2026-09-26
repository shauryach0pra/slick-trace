"""
Synthetic incident generator — multi-family, ground-truth-safe.

Produces self-contained "cases" satisfying slicktrace_core.schema's join contract
(masterplan p.7). Three things changed from v0.1 and they matter:

  1. GROUND TRUTH NO LONGER LIVES IN THE MANIFEST. It is written to a
     separate `truth.json` that the API never serves and the UI never reads.
     Previously `manifest.json` carried `true_vessel_key_HIDDEN` and a
     per-track `is_true_source` flag, and the manifest endpoint handed the
     answer to anyone with devtools open.

  2. VESSEL KEYS ARE NEUTRAL MMSI-LIKE IDENTIFIERS. Names like
     "V-TRUE-0001" / "V-DECOY-NEAR" leaked the answer into every chart,
     screenshot and video frame. A ranking that puts "V-TRUE" on top proves
     nothing to a reviewer. Track order is shuffled too.

  3. CASE FAMILIES. One case cannot support an attribution claim
     (masterplan p.15: minimum four independently generated cases, spanning
     the decoy, moving-discharge and absent-source families). Families:

       "decoy"            — true source transited the origin zone hours
                            earlier; a different, innocent vessel is nearest
                            to the slick at acquisition. Naive proximity
                            should fall for it.
       "moving_discharge" — true source discharges continuously along a long
                            track, producing an elongated slick that a
                            single-point pulse hypothesis fits badly.
       "absent_source"    — the true source's AIS track is absent entirely
                            (left the scene / not broadcasting). Correct
                            output is UNKNOWN SOURCE, not the least-bad name.
                            A near-miss decoy survives hindcast filtering so
                            the abstention gate is genuinely exercised.
       "crowded"          — many vessels inside the envelope; tests whether
                            ranking degrades into a near-tie.

MODEL MISMATCH IS DELIBERATE. The generator advects under a spatially
varying current field; the attribution simulator assumes a constant field.
Per masterplan p.15, the evaluated method should not be solving an exact
copy of the simulator that produced the answer.

Everything is labelled DataStatus.SYNTHETIC. Synthetic ranking accuracy is
not a claim about real-world attribution accuracy.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, hypot, radians

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from slicktrace_core.geography import coastline_for_bbox, land_mask, on_land
from slicktrace_core.schema import BBox, CaseState, DataStatus

IMG_SIZE = 256
DEG_PER_MS_HR = 3600 / 111_000
BASE_DIFFUSIVITY = 0.020  # deg at 1h elapsed; grows as sqrt(t)

CASE_FAMILIES = ("decoy", "moving_discharge", "absent_source", "crowded",
                 "along_track_ribbon")

# Nine independently seeded cases spanning the required families. Used by
# scripts/generate_cases.py and by the validation harness so that no headline
# number comes from a single case.
CASE_PLAN = [
    ("case_0001", "decoy", 42),
    ("case_0002", "moving_discharge", 1701),
    ("case_0003", "absent_source", 2026),
    ("case_0004", "crowded", 8813),
    ("case_0005", "decoy", 5150),
    ("case_0006", "absent_source", 9074),
    ("case_0007", "decoy", 3312),
    ("case_0008", "moving_discharge", 6421),
    ("case_0009", "along_track_ribbon", 7734),
]


# ----------------------------------------------------------------- helpers --

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _mmsi_pool(rng: np.random.Generator, n: int) -> list[str]:
    """Neutral, fictional MMSI-like identifiers (419xxxxxx = India MID).
    Deliberately carries no hint of the vessel's role in the case."""
    seen: set[str] = set()
    out = []
    while len(out) < n:
        m = f"419{int(rng.integers(100000, 999999))}"
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _spatial_current(lon, lat, u0, v0, swirl):
    """Current field with a smooth spatial gradient. The attribution
    simulator assumes (u0, v0) everywhere, so this is an honest forward-model
    mismatch rather than a self-fulfilling identical simulator."""
    du = swirl * np.sin((lat - 18.9) * 6.0)
    dv = swirl * np.cos((lon - 72.6) * 6.0)
    return u0 + du, v0 + dv


def _advect_forward(lon, lat, u0, v0, swirl, hours, rng, diffusivity=BASE_DIFFUSIVITY):
    """Advect with time-scaled (approximately Fickian, sqrt(t)) dispersion.
    A fixed-width jump independent of drift duration would let a vessel that
    was briefly near the slick fake a plausible footprint regardless of how
    implausible its timing was (masterplan p.10, assumptions register A1)."""
    hours = np.maximum(hours, 0.0)
    u, v = _spatial_current(lon, lat, u0, v0, swirl)
    spread = diffusivity * np.sqrt(np.maximum(hours, 0.05))
    lon2 = lon + u * hours * DEG_PER_MS_HR + rng.normal(0, 1, np.shape(lon)) * spread
    lat2 = lat + v * hours * DEG_PER_MS_HR + rng.normal(0, 1, np.shape(lat)) * spread
    return lon2, lat2


# ------------------------------------------------------------ vessel tracks --
#
# Every vessel, whatever its role, draws its track bookkeeping from the SAME
# distributions: when its first fix is, its reporting cadence, how fast it
# moves, and whether its route passes near the slick. Only what the release
# physics requires differs by role (the source must be where its release was).
#
# This replaced role-specific track spans that leaked the answer. The true
# source's track length came from its release story (13 or 19 fixes against
# 21 for everyone else and 6 for the near decoy), it stopped reporting before
# the image in four cases, it loitered at a speed no other vessel had while
# reporting 9.5 kn, and background traffic never came near the slick. The leak
# audit in scripts/run_validation.py found rules using none of the physics that
# named the true source in up to 7 of 7 cases; it now runs on every regeneration.

TRACK_STEP_MIN = 30
# Every vessel is tracked over the whole AIS window, as a real archive query
# for the area returns it: the published fixes are those inside the scene, so a
# ship enters and leaves through the frame edges. An earlier version started
# every track 10-16 h before the image, so ships appeared in open water.
AIS_WINDOW_H = 24.0
# A genuine AIS gap - transponder switched off, then on - for any vessel, any role.
DARK_P = 0.15
# AIS static data (message 5): ship type, as real AIS broadcasts it. Drawn from
# behaviour alone - loitering vessels are mostly fishing boats, tugs and ships
# at anchor; vessels under way are mostly cargo ships, tankers and passenger
# ships - never from role, and from a separate random stream so no track,
# slick or analysis result changes.
SHIP_TYPE_LABEL = {30: "fishing", 52: "tug", 60: "passenger", 70: "cargo", 80: "tanker"}
LOITER_TYPES = ((30, 0.60), (52, 0.15), (70, 0.15), (80, 0.10))
TRANSIT_TYPES = ((70, 0.40), (80, 0.25), (60, 0.15), (30, 0.10), (52, 0.10))
STATIC_SOURCE = "AIS static message 5 (synthetic)"
DARK_HOURS = (1.0, 3.0)
LOITER_P = 0.4                        # share of vessels loitering (fishing, waiting, drifting)
LOITER_SPEED_DEG_H = (0.002, 0.008)   # ~0.1-0.5 kn
TRANSIT_SPEED_DEG_H = (0.020, 0.120)  # ~1.2-7 kn
PASS_NEAR_P = 0.5                     # background vessels whose route passes near the slick
# A passer-by comes as close to the slick as a polluter does. The source is
# 0.7-2.7 km from the slick centroid at its closest (it was at the release
# point hours earlier, and the slick drifts a few km), so background passes
# are drawn over the same range; farther passes made 'second closest to the
# slick' a way to find the source without any physics.
PASS_NEAR_RADIUS_DEG = (0.005, 0.030)
SEA_MARGIN_DEG = 0.02                 # vessels keep this far clear of land (~2 km)
# Physical identifiability: no innocent vessel is within this distance of the
# source while the source is releasing. A vessel at the release point during
# the release is physically indistinguishable from the polluter - no method
# built on drift physics can separate them - so a case containing one tests
# nothing. Both innocents the first regeneration named were within 2 km.
IDENTIFIABLE_KM = 8.0


def _track_start(rng: np.random.Generator, acquired: datetime) -> datetime:
    return acquired - timedelta(hours=AIS_WINDOW_H)


def _static(spec, rng):
    """Ship type as a vessel's AIS static message reports it."""
    sog = [f["sog_knots"] for f in spec["fixes"]]
    table = LOITER_TYPES if (sum(sog) / len(sog) if sog else 0.0) < 1.0 else TRANSIT_TYPES
    codes, p = zip(*table)
    code = int(rng.choice(codes, p=p))
    return {"ship_type_code": code, "ship_type": SHIP_TYPE_LABEL[code], "static_source": STATIC_SOURCE}


def _published(fixes, bbox, rng):
    """What an AIS query for the scene returns: fixes inside it, minus any
    stretch where the transponder was switched off. Drawn for every vessel the
    same way, whatever its role."""
    out = _in_scene(fixes, bbox)
    if len(out) > 4 and rng.random() < DARK_P:
        dur = round(float(rng.uniform(*DARK_HOURS)) * 2) / 2
        t0 = datetime.fromisoformat(out[0]["t_utc"]) + timedelta(hours=1)
        t1 = datetime.fromisoformat(out[-1]["t_utc"]) - timedelta(hours=1 + dur)
        if t1 > t0:
            start = t0 + (t1 - t0) * float(rng.random())
            end = start + timedelta(hours=dur)
            out = [f for f in out if not (start < datetime.fromisoformat(f["t_utc"]) < end)]
    return out


def _speed(rng: np.random.Generator) -> float:
    if rng.random() < LOITER_P:
        return float(rng.uniform(*LOITER_SPEED_DEG_H))
    return float(rng.uniform(*TRANSIT_SPEED_DEG_H))


def _heading_velocity(speed: float, bearing_deg: float) -> tuple[float, float]:
    b = radians(bearing_deg)
    return speed * np.sin(b), speed * np.cos(b)


def _clear_water(lon: float, lat: float) -> bool:
    m = SEA_MARGIN_DEG
    return not any(on_land(lon + dx, lat + dy)
                   for dx, dy in ((0, 0), (m, 0), (-m, 0), (0, m), (0, -m)))


def _walk(lon, lat, vlon, vlat, n_steps, direction):
    """n_steps half-hour positions from (lon, lat), forward or backward in time.

    A vessel about to leave clear water turns away: the first of its velocity
    with the east-west part reversed, the north-south part reversed, or both,
    that keeps it at sea. Boxed in, it holds position.
    """
    dt = TRACK_STEP_MIN / 60.0
    out = []
    for _ in range(n_steps):
        for cand in ((vlon, vlat), (-vlon, vlat), (vlon, -vlat), (-vlon, -vlat)):
            nl, na = lon + direction * cand[0] * dt, lat + direction * cand[1] * dt
            if _clear_water(nl, na):
                vlon, vlat = cand
                break
        else:
            nl, na = lon, lat
        lon, lat = nl, na
        out.append((lon, lat))
    return out


def _fixes(points, times):
    """AIS-like fixes. Reported speed and course are the vessel's actual motion."""
    hrs = TRACK_STEP_MIN / 60.0
    out = []
    for i, ((lo, la), t) in enumerate(zip(points, times)):
        j0, j1 = (i, i + 1) if i + 1 < len(points) else (max(i - 1, 0), i)
        (a, b), (c, d) = points[j0], points[j1]
        dx = (c - a) * 111.0 * cos(radians((b + d) / 2))
        dy = (d - b) * 111.0
        out.append({
            "t_utc": t.isoformat(),
            "lon": round(float(lo), 5),
            "lat": round(float(la), 5),
            "sog_knots": round(hypot(dx, dy) / hrs / 1.852, 1),
            "cog_deg": round((degrees(atan2(dx, dy)) + 360.0) % 360.0, 1),
            "interpolated": False,
        })
    return out


def _track_through(anchor, anchor_t, velocity, t_start, t_end):
    """A track that is at `anchor` at `anchor_t`, walked back to t_start and on
    to t_end at the given velocity (degrees per hour), steering clear of land."""
    step = timedelta(minutes=TRACK_STEP_MIN)
    n_back = int(round((anchor_t - t_start) / step))
    n_fwd = int(round((t_end - anchor_t) / step))
    back = _walk(anchor[0], anchor[1], velocity[0], velocity[1], n_back, -1)[::-1]
    fwd = _walk(anchor[0], anchor[1], velocity[0], velocity[1], n_fwd, +1)
    pts = back + [tuple(anchor)] + fwd
    first_t = anchor_t - n_back * step
    return _fixes(pts, [first_t + i * step for i in range(len(pts))])


def _closest_during_release_km(fixes, source_fixes, release_start, duration_hours):
    """Closest distance between a vessel and the source over the release window."""
    step = timedelta(minutes=TRACK_STEP_MIN)
    n = int(round(timedelta(hours=duration_hours) / step))
    best = float("inf")
    for i in range(n + 1):
        t = release_start + i * step
        a, b = _interp(fixes, t), _interp(source_fixes, t)
        if a is None or b is None:
            continue
        dx = (a[0] - b[0]) * 111.0 * cos(radians((a[1] + b[1]) / 2))
        best = min(best, hypot(dx, (a[1] - b[1]) * 111.0))
    return best


def _in_scene(fixes, bbox):
    """The fixes an AIS query for the scene area returns: those inside it."""
    return [f for f in fixes
            if bbox.min_lon <= f["lon"] <= bbox.max_lon and bbox.min_lat <= f["lat"] <= bbox.max_lat]


def _interp(fixes, t):
    times = [datetime.fromisoformat(f["t_utc"]) for f in fixes]
    if not times or t < min(times) or t > max(times):
        return None
    for i in range(len(times) - 1):
        if times[i] <= t <= times[i + 1]:
            span = (times[i + 1] - times[i]).total_seconds()
            frac = 0.0 if span == 0 else (t - times[i]).total_seconds() / span
            return (fixes[i]["lon"] + frac * (fixes[i + 1]["lon"] - fixes[i]["lon"]),
                    fixes[i]["lat"] + frac * (fixes[i + 1]["lat"] - fixes[i]["lat"]))
    return (fixes[-1]["lon"], fixes[-1]["lat"])


def _lonlat_to_px(lon, lat, bbox, img_size=IMG_SIZE):
    xs = ((lon - bbox.min_lon) / (bbox.max_lon - bbox.min_lon) * img_size).astype(int)
    ys = ((bbox.max_lat - lat) / (bbox.max_lat - bbox.min_lat) * img_size).astype(int)
    return np.clip(xs, 0, img_size - 1), np.clip(ys, 0, img_size - 1)


def _rasterise(lon, lat, bbox, img_size=IMG_SIZE, sigma=3, thresh_frac=0.15):
    mask = np.zeros((img_size, img_size), dtype=np.uint8)
    xs, ys = _lonlat_to_px(lon, lat, bbox, img_size)
    mask[ys, xs] = 1
    blurred = gaussian_filter(mask.astype(float), sigma=sigma)
    if blurred.max() == 0:
        return blurred.astype(np.uint8)
    return (blurred > blurred.max() * thresh_frac).astype(np.uint8)


def _simulate_release(fixes, release_start, duration_hours, is_continuous,
                      acquired, u0, v0, swirl, rng, n_particles=500):
    """Ground-truth forward run: release along the vessel's own track, then
    drift to acquisition time under the spatially varying field."""
    offsets = (rng.uniform(0, duration_hours, n_particles) if is_continuous
               else np.zeros(n_particles))
    lons = np.zeros(n_particles)
    lats = np.zeros(n_particles)
    for i, off in enumerate(offsets):
        pos = _interp(fixes, release_start + timedelta(hours=float(off)))
        if pos is None:
            pos = _interp(fixes, release_start) or (fixes[0]["lon"], fixes[0]["lat"])
        lons[i], lats[i] = pos
    drift_h = np.array([(acquired - (release_start + timedelta(hours=float(o)))).total_seconds() / 3600
                        for o in offsets])
    return _advect_forward(lons, lats, u0, v0, swirl, drift_h, rng)


# ------------------------------------------------------------ case families --

def _build_family(family: str, rng: np.random.Generator, acquired: datetime,
                  origin_lon: float, origin_lat: float):
    """Returns (tracks_spec, true_spec) where tracks_spec is a list of
    {role, fixes} and true_spec describes the release that made the slick.

    Each family fixes only what its release needs: where the source is when the
    release starts, how it moves while releasing, and for how long. The track
    before and after comes from the same builder and the same span as every
    other vessel.

    `role` is retained ONLY for the dev-only truth sidecar and the validation
    harness; it never reaches the manifest, the API or the UI.
    """
    t_start = _track_start(rng, acquired)
    if family in ("decoy", "crowded"):
        # A 2 h release. The source's speed is drawn like any vessel's: loitering
        # it leaves a compact patch, under way a short streak. Fixing it to
        # loitering made "the slowest vessel" a way to find the source.
        release_start = acquired - timedelta(hours=6)
        anchor = (origin_lon - 0.338, origin_lat + 0.291)
        velocity = _heading_velocity(_speed(rng), 127.0)
        duration, continuous, role = 2.0, True, "true_source"
    elif family == "absent_source":
        # The source discharged and then left the scene / stopped broadcasting.
        # Its track is generated so the slick is physically real, then dropped
        # from the manifest entirely.
        release_start = acquired - timedelta(hours=6)
        anchor = (origin_lon - 0.348, origin_lat + 0.301)
        velocity = _heading_velocity(_speed(rng), 127.0)
        duration, continuous, role = 2.0, True, "absent_true_source"
    elif family == "moving_discharge":
        # long transit, continuous discharge over 4 h
        release_start = acquired - timedelta(hours=7)
        anchor = (origin_lon - 0.34, origin_lat + 0.304)
        velocity = (0.030, -0.018)
        duration, continuous, role = 4.0, True, "true_source"
    elif family == "along_track_ribbon":
        # Routine bilge discharge from a vessel under way: a long, thin ribbon
        # laid along its track rather than a compact patch.
        #
        # The other families produce near-circular slicks, which published SAR
        # morphology work would classify as look-alikes rather than oil (A16);
        # this family exists because that was a real gap in the benchmark. The
        # ribbon runs along the shore, as coastal traffic does: an earlier
        # version headed east into the coast, where the clamp that kept the ship
        # at sea bent the ribbon along the shoreline and onto land.
        release_start = acquired - timedelta(hours=8)
        anchor = (origin_lon - 0.17, origin_lat + 0.30)
        velocity = (0.020, -0.095)
        duration, continuous, role = 7.0, True, "true_source"
    else:
        raise ValueError(f"unknown family: {family}")

    fixes = _track_through(anchor, release_start, velocity, t_start, acquired)
    specs = [{"role": role, "fixes": fixes}]
    true_spec = {"release_start": release_start, "duration_hours": duration,
                 "is_continuous": continuous, "track_index": 0}
    return specs, true_spec


def generate_case(incident_id: str = "case_0001", family: str = "decoy",
                  seed: int = 42, out_dir: str = "data/cases",
                  img_size: int = IMG_SIZE) -> tuple[dict, dict]:
    if family not in CASE_FAMILIES:
        raise ValueError(f"family must be one of {CASE_FAMILIES}")
    rng = np.random.default_rng(seed)
    case_dir = os.path.join(out_dir, incident_id)
    os.makedirs(case_dir, exist_ok=True)

    origin_lon, origin_lat = 72.60, 18.90  # off the Maharashtra coast, arbitrary
    bbox = BBox(min_lon=origin_lon - 0.5, min_lat=origin_lat - 0.5,
                max_lon=origin_lon + 0.5, max_lat=origin_lat + 0.5)
    acquired = datetime(2026, 9, 10, 4, 30, tzinfo=timezone.utc)

    u0, v0 = 0.15, -0.05                      # m/s mean drift
    swirl = float(rng.uniform(0.010, 0.020))  # spatial variation the simulator won't know about
    noise = gaussian_filter(rng.normal(0, 0.02, size=(32, 32, 2)), sigma=2)
    forcing_path = os.path.join(case_dir, "forcing.npz")
    np.savez(forcing_path, u=u0, v=v0, noise=noise, swirl_TRUE_HIDDEN=swirl)

    specs, true_spec = _build_family(family, rng, acquired, origin_lon, origin_lat)
    true_fixes = specs[true_spec["track_index"]]["fixes"]

    # --- render the observed slick from the true release ---
    px, py = _simulate_release(true_fixes, true_spec["release_start"],
                               true_spec["duration_hours"], true_spec["is_continuous"],
                               acquired, u0, v0, swirl, rng)
    mask = _rasterise(px, py, bbox, img_size)
    centroid_lon = float(np.mean(px))
    centroid_lat = float(np.mean(py))

    # --- the nearest-at-acquisition decoy, aimed at the ACTUAL post-drift
    # slick centroid (not the scene centre). Aiming it at the scene centre
    # would leave the proximity baseline untrapped and flatter the method.
    # It arrives from seaward, at a speed and over a span drawn like any other. ---
    rs, dur = true_spec["release_start"], true_spec["duration_hours"]

    def _identifiable(draw):
        """Draw an innocent's track until it is not at the release while it happens."""
        for _ in range(60):
            fixes = draw()
            if _closest_during_release_km(fixes, true_fixes, rs, dur) >= IDENTIFIABLE_KM:
                return fixes
        raise RuntimeError("could not draw a physically identifiable innocent track")

    specs.append({"role": "near_decoy", "fixes": _identifiable(lambda: _track_through(
        (centroid_lon, centroid_lat), acquired,
        _heading_velocity(_speed(rng), float(rng.uniform(30.0, 150.0))),
        _track_start(rng, acquired), acquired))})

    # --- a near-miss decoy that DOES survive hindcast filtering but fits
    # the observed footprint badly. In absent_source cases this is what
    # actually exercises the abstention gate: the system has something
    # plausible to name, and must decline to name it. ---
    specs.append({"role": "near_miss_decoy", "fixes": _identifiable(lambda: _track_through(
        (centroid_lon - 0.02, centroid_lat + 0.22), acquired, _heading_velocity(_speed(rng), 310.0),
        _track_start(rng, acquired), acquired))})

    # --- unrelated traffic: some of it passes near the slick, as real traffic
    # does, so being near it at some point is not evidence by construction ---
    n_other = 8 if family == "crowded" else 3
    step = timedelta(minutes=TRACK_STEP_MIN)
    def _background():
        t0 = _track_start(rng, acquired)
        v = _heading_velocity(_speed(rng), float(rng.uniform(0.0, 360.0)))
        anchor = None
        if rng.random() < PASS_NEAR_P:
            for _try in range(20):
                r = float(rng.uniform(*PASS_NEAR_RADIUS_DEG))
                a = float(rng.uniform(0.0, 2 * np.pi))
                cand = (centroid_lon + r * np.cos(a), centroid_lat + r * np.sin(a))
                if _clear_water(*cand):
                    n_steps = int(round((acquired - t0) / step))
                    anchor, anchor_t = cand, t0 + int(rng.integers(0, n_steps + 1)) * step
                    break
        if anchor is None:
            for _try in range(200):
                cand = (float(rng.uniform(bbox.min_lon + 0.05, bbox.max_lon - 0.05)),
                        float(rng.uniform(bbox.min_lat + 0.05, bbox.max_lat - 0.05)))
                if _clear_water(*cand):
                    anchor, anchor_t = cand, t0
                    break
        return _track_through(anchor, anchor_t, v, t0, acquired)

    for _ in range(n_other):
        specs.append({"role": "background", "fixes": _identifiable(_background)})

    # --- assign neutral identities and shuffle so ordering leaks nothing ---
    mmsis = _mmsi_pool(rng, len(specs))
    for spec, mmsi in zip(specs, mmsis):
        spec["vessel_key"] = mmsi
    order = rng.permutation(len(specs))
    specs = [specs[i] for i in order]

    true_vessel_key = next((s["vessel_key"] for s in specs if s["role"] == "true_source"), None)
    absent_vessel_key = next((s["vessel_key"] for s in specs if s["role"] == "absent_true_source"), None)

    # the absent source is removed from the manifest — this is the whole point
    for s in specs:
        s["published"] = _published(s["fixes"], bbox, rng)
    published = [s for s in specs if s["role"] != "absent_true_source"
                 and len(s["published"]) >= 2]

    identity_from = (acquired - timedelta(days=365)).isoformat()
    type_rng = np.random.default_rng([int(seed), 5])     # separate stream: see SHIP_TYPE_LABEL
    tracks = [{
        "vessel_key": s["vessel_key"],
        "mmsi": s["vessel_key"],
        "imo": None,
        "name": None,
        "identity_valid_from": identity_from,
        "identity_valid_to": None,
        "fixes": s["published"],
        **_static(s, type_rng),
        "missing_intervals": [],
        "provenance": {"status": DataStatus.SYNTHETIC.value,
                       "source": "slicktrace_core.synth_generator v0.2 (fictional AIS)"},
    } for s in published]

    # --- scene raster: sea speckle, darker where oil damps the waves, and
    # land from the real coastline, brighter and textured as it is in SAR ---
    coastline = coastline_for_bbox(bbox.model_dump())
    land = land_mask(bbox.model_dump(), (img_size, img_size), coastline)
    if land is None:
        land = np.zeros((img_size, img_size), dtype=bool)
    mask = (mask.astype(bool) & ~land).astype(np.uint8)   # the truth slick is at sea only
    speckle = rng.gamma(shape=4.0, scale=0.25, size=(img_size, img_size))
    scene = speckle.copy()
    scene[mask == 1] *= 0.35  # oil dampens capillary waves -> darker in SAR
    relief = gaussian_filter(rng.normal(0, 1, (img_size, img_size)), sigma=5)
    relief = relief / (np.abs(relief).max() + 1e-9)
    scene[land] = speckle[land] * (2.1 + 0.6 * relief[land])
    scene_img = (255 * np.clip(scene / np.percentile(scene, 99.7), 0, 1)).astype(np.uint8)
    image_path = os.path.join(case_dir, "scene.png")
    mask_path = os.path.join(case_dir, "mask_groundtruth.png")
    Image.fromarray(scene_img, mode="L").save(image_path)
    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(mask_path)

    # --- sensitive areas, for the forward exposure mode. The coastline is the
    # real one (slicktrace_core.geography), clipped to the scene above. ---
    # Placed relative to the ACTUAL post-drift slick centroid and the mean
    # drift direction, so the forward exposure mode has something real to
    # intersect. Areas parked in a corner the slick never reaches would make
    # every forecast report "no contact" regardless of whether the
    # intersection logic worked at all.
    drift_lon_24h = u0 * 24 * DEG_PER_MS_HR
    drift_lat_24h = v0 * 24 * DEG_PER_MS_HR
    fg_lon = centroid_lon + drift_lon_24h * 0.55
    fg_lat = centroid_lat + drift_lat_24h * 0.55

    def _box(cx, cy):
        return [[round(cx - 0.06, 5), round(cy - 0.08, 5)], [round(cx + 0.14, 5), round(cy - 0.08, 5)],
                [round(cx + 0.14, 5), round(cy + 0.08, 5)], [round(cx - 0.06, 5), round(cy + 0.08, 5)]]
    fishing = _box(fg_lon, fg_lat)
    for _ in range(40):                     # a fishing ground is at sea: move it seaward until it is
        if not any(on_land(x, y, coastline) for x, y in fishing):
            break
        fg_lon -= 0.02
        fishing = _box(fg_lon, fg_lat)

    # A mangrove fringe is intertidal: a strip straddling the open coast, the
    # first land met from seaward at each latitude. Following every coastline
    # vertex in the band instead traced both banks of the creeks and gave a
    # polygon that crossed itself.
    def _open_coast_lon(lat):
        lon = bbox.min_lon
        while lon < bbox.max_lon and not on_land(lon, lat, coastline):
            lon += 0.002
        return lon
    band = np.arange(origin_lat + 0.10, origin_lat + 0.28 + 1e-9, 0.01)
    shore = [(_open_coast_lon(float(la)), float(la)) for la in band]
    mangrove = ([[round(x - 0.015, 5), round(y, 5)] for x, y in shore]
                + [[round(x + 0.015, 5), round(y, 5)] for x, y in reversed(shore)])
    sensitive_areas = [
        {"name": "Fishing ground (synthetic)", "kind": "fishery", "polygon": fishing},
        {"name": "Mangrove reserve (synthetic)", "kind": "mangrove", "polygon": mangrove},
    ]

    deg_lat_m = 111_000.0
    pixel_spacing_m = round((bbox.max_lat - bbox.min_lat) * deg_lat_m / img_size, 2)

    # --- manifest: the join contract (masterplan p.7). No ground truth here. ---
    manifest = {
        "incident_id": incident_id,
        "scene_id": f"{incident_id}_S1SYN_{acquired.strftime('%Y%m%dT%H%M%S')}",
        "case_state": CaseState.POTENTIAL_SLICK.value,
        "acquired_utc": acquired.isoformat(),
        "crs": "EPSG:4326",
        "metric_crs": "EPSG:32643",  # UTM 43N — for area/perimeter/axis measurement
        "bbox": bbox.model_dump(),
        "img_size_px": img_size,
        "pixel_spacing_m": pixel_spacing_m,
        "sensor": "synthetic SAR-like (VV proxy, single channel)",
        "image_path": image_path,
        "mask_groundtruth_path": mask_path,
        "label_source": "generator ground truth (synthetic) — not a human or "
                        "independently confirmed label",
        "forcing_path": forcing_path,
        "forcing_product": "slicktrace_core.synth_generator constant+spatial field v0.2",
        "forcing_valid_from_utc": (acquired - timedelta(hours=24)).isoformat(),
        "forcing_valid_to_utc": acquired.isoformat(),
        "ais_source": "synthetic (fictional MMSIs; no real broadcast data)",
        "ais_window_start_utc": (acquired - timedelta(hours=24)).isoformat(),
        "ais_window_end_utc": acquired.isoformat(),
        "data_licence": "Synthetic data generated by this repository; released "
                        "under the repository licence. No third-party data terms apply.",
        "coastline": coastline,
        "sensitive_areas": sensitive_areas,
        "tracks": tracks,
        "provenance": {
            "status": DataStatus.SYNTHETIC.value,
            "source": "slicktrace_core.synth_generator v0.2",
            "license": "repository licence (see LICENSE)",
        },
        "generator": {"family": family, "seed": seed, "version": "0.2"},
        "checksums": {
            "scene.png": _sha256(image_path),
            "mask_groundtruth.png": _sha256(mask_path),
            "forcing.npz": _sha256(forcing_path),
        },
    }
    with open(os.path.join(case_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    # --- dev-only truth sidecar. Never served by the API, never read by the UI. ---
    truth = {
        "incident_id": incident_id,
        "family": family,
        "seed": seed,
        "true_vessel_key": true_vessel_key,          # None for absent_source
        "absent_true_vessel_key": absent_vessel_key,  # set only for absent_source
        "source_is_in_manifest": true_vessel_key is not None,
        "expected_outcome": "unknown_source" if true_vessel_key is None else "named_candidate",
        "release_start_utc": true_spec["release_start"].isoformat(),
        "release_duration_hours": true_spec["duration_hours"],
        "is_continuous": true_spec["is_continuous"],
        "swirl": swirl,
        "roles": {s["vessel_key"]: s["role"] for s in specs},
        "slick_centroid": [centroid_lon, centroid_lat],
        "WARNING": "Dev/validation only. Not served by the API, not read by the UI, "
                   "and not required to reproduce any result shown to a reviewer.",
    }
    with open(os.path.join(case_dir, "truth.json"), "w") as f:
        json.dump(truth, f, indent=2, default=str)

    return manifest, truth


def generate_all(out_dir: str = "data/cases") -> list[tuple[dict, dict]]:
    return [generate_case(cid, fam, seed, out_dir) for cid, fam, seed in CASE_PLAN]


if __name__ == "__main__":
    for manifest, truth in generate_all():
        n_cand = len(manifest["tracks"])
        print(f"{manifest['incident_id']}  family={truth['family']:17s} "
              f"seed={truth['seed']:<5d} vessels={n_cand:<3d} "
              f"expected={truth['expected_outcome']}")
    print("\nGround truth written to each case's truth.json (dev-only; "
          "manifest.json and the API carry none of it).")
