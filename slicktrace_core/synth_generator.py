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

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from slicktrace_core.schema import BBox, CaseState, DataStatus

IMG_SIZE = 256
DEG_PER_MS_HR = 3600 / 111_000
BASE_DIFFUSIVITY = 0.020  # deg at 1h elapsed; grows as sqrt(t)

CASE_FAMILIES = ("decoy", "moving_discharge", "absent_source", "crowded")

# Six independently seeded cases spanning the required families. Used by
# scripts/generate_cases.py and by the validation harness so that no headline
# number comes from a single case.
CASE_PLAN = [
    ("case_0001", "decoy", 42),
    ("case_0002", "moving_discharge", 1701),
    ("case_0003", "absent_source", 2026),
    ("case_0004", "crowded", 8813),
    ("case_0005", "decoy", 5150),
    ("case_0006", "absent_source", 9074),
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


def _track(start_lon, start_lat, dlon_per_hr, dlat_per_hr, t0, hours, step_min=30,
           sog=9.5, cog=140.0):
    fixes = []
    t = t0
    n = int(hours * 60 / step_min) + 1
    for i in range(n):
        h = i * step_min / 60.0
        fixes.append({
            "t_utc": (t + timedelta(minutes=i * step_min)).isoformat(),
            "lon": round(float(start_lon + dlon_per_hr * h), 5),
            "lat": round(float(start_lat + dlat_per_hr * h), 5),
            "sog_knots": round(float(sog), 1),
            "cog_deg": round(float(cog), 1),
            "interpolated": False,
        })
    return fixes


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

    `role` is retained ONLY for the dev-only truth sidecar and the validation
    harness; it never reaches the manifest, the API or the UI.
    """
    specs = []

    if family in ("decoy", "crowded", "moving_discharge"):
        if family == "moving_discharge":
            # long transit, continuous discharge over 4h
            release_start = acquired - timedelta(hours=7)
            true_fixes = _track(origin_lon - 0.40, origin_lat + 0.34,
                                0.030, -0.018, release_start - timedelta(hours=2),
                                hours=9, sog=11.0, cog=145.0)
            duration, continuous = 4.0, True
        else:
            release_start = acquired - timedelta(hours=6)
            true_fixes = _track(origin_lon - 0.35, origin_lat + 0.30,
                                0.004, -0.003, release_start - timedelta(hours=3),
                                hours=6, sog=9.5, cog=140.0)
            duration, continuous = 2.0, True
        specs.append({"role": "true_source", "fixes": true_fixes})
        true_spec = {"release_start": release_start, "duration_hours": duration,
                     "is_continuous": continuous, "track_index": 0}
    elif family == "absent_source":
        # The source discharged and then left the scene / stopped broadcasting.
        # Its track is generated so the slick is physically real, then dropped
        # from the manifest entirely.
        release_start = acquired - timedelta(hours=6)
        true_fixes = _track(origin_lon - 0.36, origin_lat + 0.31,
                            0.004, -0.003, release_start - timedelta(hours=3),
                            hours=6, sog=10.0, cog=140.0)
        specs.append({"role": "absent_true_source", "fixes": true_fixes})
        true_spec = {"release_start": release_start, "duration_hours": 2.0,
                     "is_continuous": True, "track_index": 0}
    else:
        raise ValueError(f"unknown family: {family}")

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
    # would leave the proximity baseline untrapped and flatter the method. ---
    if family != "crowded":
        near_start_lon, near_start_lat = origin_lon + 0.15, origin_lat - 0.15
    else:
        near_start_lon, near_start_lat = origin_lon + 0.20, origin_lat - 0.20
    near_fixes = []
    t = acquired - timedelta(hours=2.5)
    n_steps = 6
    for step in range(n_steps):
        frac = step / (n_steps - 1)
        near_fixes.append({
            "t_utc": (t + timedelta(minutes=30 * step)).isoformat(),
            "lon": round(float(near_start_lon + frac * (centroid_lon - near_start_lon)), 5),
            "lat": round(float(near_start_lat + frac * (centroid_lat - near_start_lat)), 5),
            "sog_knots": 11.0, "cog_deg": 310.0, "interpolated": False,
        })
    specs.append({"role": "near_decoy", "fixes": near_fixes})

    # --- a near-miss decoy that DOES survive hindcast filtering but fits
    # the observed footprint badly. In absent_source cases this is what
    # actually exercises the abstention gate: the system has something
    # plausible to name, and must decline to name it. ---
    miss_start_lon = centroid_lon + 0.10
    miss_start_lat = centroid_lat + 0.12
    specs.append({"role": "near_miss_decoy",
                  "fixes": _track(miss_start_lon, miss_start_lat, -0.012, 0.010,
                                  acquired - timedelta(hours=10), hours=10,
                                  sog=7.0, cog=95.0)})

    # --- unrelated traffic ---
    n_other = 8 if family == "crowded" else 3
    for _ in range(n_other):
        specs.append({"role": "background",
                      "fixes": _track(origin_lon + float(rng.uniform(-0.45, 0.45)),
                                      origin_lat + float(rng.uniform(-0.45, 0.45)),
                                      float(rng.uniform(-0.03, 0.03)),
                                      float(rng.uniform(-0.03, 0.03)),
                                      acquired - timedelta(hours=10), hours=10,
                                      sog=float(rng.uniform(4, 14)),
                                      cog=float(rng.uniform(0, 360)))})

    # --- assign neutral identities and shuffle so ordering leaks nothing ---
    mmsis = _mmsi_pool(rng, len(specs))
    for spec, mmsi in zip(specs, mmsis):
        spec["vessel_key"] = mmsi
    order = rng.permutation(len(specs))
    specs = [specs[i] for i in order]

    true_vessel_key = next((s["vessel_key"] for s in specs if s["role"] == "true_source"), None)
    absent_vessel_key = next((s["vessel_key"] for s in specs if s["role"] == "absent_true_source"), None)

    # the absent source is removed from the manifest — this is the whole point
    published = [s for s in specs if s["role"] != "absent_true_source"]

    identity_from = (acquired - timedelta(days=365)).isoformat()
    tracks = [{
        "vessel_key": s["vessel_key"],
        "mmsi": s["vessel_key"],
        "imo": None,
        "name": None,
        "identity_valid_from": identity_from,
        "identity_valid_to": None,
        "fixes": s["fixes"],
        "missing_intervals": [],
        "provenance": {"status": DataStatus.SYNTHETIC.value,
                       "source": "slicktrace_core.synth_generator v0.2 (fictional AIS)"},
    } for s in published]

    # --- scene raster ---
    speckle = rng.gamma(shape=4.0, scale=0.25, size=(img_size, img_size))
    scene = speckle.copy()
    scene[mask == 1] *= 0.35  # oil dampens capillary waves -> darker in SAR
    scene_img = (255 * (np.clip(scene, 0, None) / scene.max())).astype(np.uint8)
    image_path = os.path.join(case_dir, "scene.png")
    mask_path = os.path.join(case_dir, "mask_groundtruth.png")
    Image.fromarray(scene_img, mode="L").save(image_path)
    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(mask_path)

    # --- synthetic coastline + sensitive areas, for the forward exposure mode ---
    coast_lon = bbox.max_lon - 0.06
    coastline = [[round(coast_lon + 0.015 * np.sin(i * 0.7), 5),
                  round(bbox.min_lat + i * (bbox.max_lat - bbox.min_lat) / 19, 5)]
                 for i in range(20)]
    # Sensitive areas are placed relative to the ACTUAL post-drift slick
    # centroid and the mean drift direction, so the forward exposure mode has
    # something real to intersect. Areas parked in a corner the slick never
    # reaches would make every forecast report "no contact" regardless of
    # whether the intersection logic worked at all.
    drift_lon_24h = u0 * 24 * DEG_PER_MS_HR
    drift_lat_24h = v0 * 24 * DEG_PER_MS_HR
    fg_lon = centroid_lon + drift_lon_24h * 0.55
    fg_lat = centroid_lat + drift_lat_24h * 0.55
    sensitive_areas = [
        {"name": "Fishing ground (synthetic)", "kind": "fishery",
         "polygon": [[round(fg_lon - 0.06, 5), round(fg_lat - 0.08, 5)],
                     [round(fg_lon + 0.14, 5), round(fg_lat - 0.08, 5)],
                     [round(fg_lon + 0.14, 5), round(fg_lat + 0.08, 5)],
                     [round(fg_lon - 0.06, 5), round(fg_lat + 0.08, 5)]]},
        {"name": "Mangrove reserve (synthetic)", "kind": "mangrove",
         "polygon": [[round(coast_lon - 0.05, 5), round(origin_lat + 0.10, 5)],
                     [round(coast_lon, 5), round(origin_lat + 0.10, 5)],
                     [round(coast_lon, 5), round(origin_lat + 0.28, 5)],
                     [round(coast_lon - 0.05, 5), round(origin_lat + 0.28, 5)]]},
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
