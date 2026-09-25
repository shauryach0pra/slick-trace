"""
Forward response mode (masterplan p.13).

Seed the observed slick and generate 6/12/24 h spread envelopes, then
intersect them with the coastline and available sensitive-area layers.

What is reported is MODELLED EXPOSURE and ARRIVAL INTERVALS, not guaranteed
damage. An envelope touching a mangrove polygon at +12 h means the modelled
surface particles reach it under the tested forcing, not that oil will come
ashore there. The distinction is kept in the field names, not left to the
reader.

For retrospective tests, reanalysis forcing is acceptable. An operational
forecast would need fields available at issuance — a reanalysis-driven
forecast is a hindcast wearing a forecast's clothes, and is labelled as such
in `forcing_mode`.
"""

from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image

from slicktrace_core.attribution import lonlat_to_px
from slicktrace_core.geography import on_land
from slicktrace_core.hindcast import DEG_PER_MS_HR, _parse

HORIZONS_H = (6, 12, 24)
BASE_DIFFUSIVITY = 0.020


def _seed_particles(mask_path: str, bbox: dict, img_size: int, n: int,
                    rng: np.random.Generator):
    mask = np.array(Image.open(mask_path)) > 127
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("empty observed mask — nothing to seed a forecast from")
    idx = rng.integers(0, len(xs), size=n)
    xs, ys = xs[idx], ys[idx]
    lon = bbox["min_lon"] + (xs / img_size) * (bbox["max_lon"] - bbox["min_lon"])
    lat = bbox["max_lat"] - (ys / img_size) * (bbox["max_lat"] - bbox["min_lat"])
    return lon, lat


def _point_in_polygon(lon, lat, poly) -> np.ndarray:
    """Vectorised ray casting. poly is a list of [lon, lat]."""
    px = np.asarray([p[0] for p in poly])
    py = np.asarray([p[1] for p in poly])
    inside = np.zeros(np.shape(lon), dtype=bool)
    n = len(poly)
    j = n - 1
    for i in range(n):
        cond = ((py[i] > lat) != (py[j] > lat)) & (
            lon < (px[j] - px[i]) * (lat - py[i]) / (py[j] - py[i] + 1e-12) + px[i])
        inside ^= cond
        j = i
    return inside


def run_forecast(case_dir: str, horizons_h=HORIZONS_H, n_particles: int = 600,
                 n_ensemble: int = 6, seed: int = 77) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    forcing = np.load(manifest["forcing_path"])
    u0, v0 = float(forcing["u"]), float(forcing["v"])
    bbox = manifest["bbox"]
    img_size = manifest.get("img_size_px", 256)
    acquired = _parse(manifest["acquired_utc"])

    rng = np.random.default_rng(seed)
    lon0, lat0 = _seed_particles(manifest["mask_groundtruth_path"], bbox, img_size,
                                 n_particles, rng)

    # same shared-ensemble discipline as attribution: identical perturbations,
    # so the spread between horizons is comparable
    variants = [
        {"name": "nominal", "du": 0.0, "dv": 0.0, "kscale": 1.0},
        {"name": "current+20pct", "du": 0.03, "dv": 0.0, "kscale": 1.0},
        {"name": "current-20pct", "du": -0.03, "dv": 0.0, "kscale": 1.0},
        {"name": "cross-current+", "du": 0.0, "dv": 0.03, "kscale": 1.0},
        {"name": "cross-current-", "du": 0.0, "dv": -0.03, "kscale": 1.0},
        {"name": "high-diffusivity", "du": 0.0, "dv": 0.0, "kscale": 1.8},
    ][:n_ensemble]

    coastline = manifest.get("coastline", [])
    sensitive = manifest.get("sensitive_areas", [])

    # Beaching. Each particle draws the same normals at every horizon, so its
    # position is one smooth path in time: drift * t plus a fixed direction
    # scaled by sqrt(t). Stepping that path hourly finds the first hour it
    # reaches land; from then on it stays there, stranded, and counts as
    # shoreline contact. Particles that never touch land are unchanged.
    h_max = max(horizons_h)
    hours = np.arange(1, h_max + 1, dtype=float)

    def _paths(vi, var):
        r = np.random.default_rng(seed + vi)
        z_lon = r.normal(0, 1.0, len(lon0))
        z_lat = r.normal(0, 1.0, len(lat0))
        k = BASE_DIFFUSIVITY * var["kscale"]
        def at(t):
            return (lon0 + (u0 + var["du"]) * t * DEG_PER_MS_HR + z_lon * k * np.sqrt(t),
                    lat0 + (v0 + var["dv"]) * t * DEG_PER_MS_HR + z_lat * k * np.sqrt(t))
        strand_h = np.full(len(lon0), np.inf)
        if coastline:
            for t in hours:
                lo, la = at(t)
                hit = np.isinf(strand_h) & on_land(lo, la, coastline)
                strand_h[hit] = t
        return at, strand_h

    paths = [_paths(vi, var) for vi, var in enumerate(variants)]

    horizons = []
    particles_by_horizon = []  # the same particles, kept for forecast_contours.json
    first_contact = {a["name"]: None for a in sensitive}
    first_shore_contact = None

    for h in horizons_h:
        all_lon, all_lat, stranded = [], [], []
        for at, strand_h in paths:
            t_eff = np.minimum(float(h), strand_h)
            lon, lat = at(t_eff)
            all_lon.append(lon)
            all_lat.append(lat)
            stranded.append(strand_h <= h)
        lon_h = np.concatenate(all_lon)
        lat_h = np.concatenate(all_lat)
        stranded_h = np.concatenate(stranded)
        particles_by_horizon.append((lon_h, lat_h))

        xs, ys = lonlat_to_px(lon_h, lat_h, bbox, img_size)
        grid = np.zeros((img_size, img_size), dtype=np.int32)
        np.add.at(grid, (ys, xs), 1)
        occupied = int((grid > 0).sum())
        deg2_per_px = ((bbox["max_lon"] - bbox["min_lon"]) / img_size) * \
                      ((bbox["max_lat"] - bbox["min_lat"]) / img_size)
        area_km2 = occupied * deg2_per_px * (111.0 ** 2)

        exposures = []
        for area in sensitive:
            frac = float(_point_in_polygon(lon_h, lat_h, area["polygon"]).mean())
            exposures.append({
                "name": area["name"], "kind": area["kind"],
                "modelled_particle_fraction": round(frac, 4),
                "any_contact": frac > 0.0,
            })
            if frac > 0.0 and first_contact[area["name"]] is None:
                first_contact[area["name"]] = h

        shore_frac = float(stranded_h.mean()) if coastline else None
        if shore_frac and shore_frac > 0.0 and first_shore_contact is None:
            first_shore_contact = h

        horizons.append({
            "horizon_hours": h,
            "valid_utc": (acquired + __import__("datetime").timedelta(hours=h)).isoformat(),
            "envelope_area_km2": round(area_km2, 1),
            "centroid": [round(float(lon_h.mean()), 5), round(float(lat_h.mean()), 5)],
            "modelled_shoreline_fraction": round(shore_frac, 4) if shore_frac is not None else None,
            "sensitive_area_exposure": exposures,
            "particles": n_particles * len(variants),
        })

    out = {
        "incident_id": manifest["incident_id"],
        "issued_from_utc": manifest["acquired_utc"],
        "forcing_mode": "reanalysis-style retrospective field — NOT an operational "
                        "forecast issued from fields available at issuance time",
        "n_ensemble_variants": len(variants),
        "horizons": horizons,
        "first_modelled_shoreline_contact_h": first_shore_contact,
        "first_modelled_sensitive_contact_h": {k: v for k, v in first_contact.items()},
        "interpretation_note": "Modelled surface-particle exposure and arrival intervals "
                               "under the tested forcing ensemble. Not a prediction of "
                               "beaching, concentration, or environmental damage. A particle "
                               "that reaches the coastline is held where it arrives (simple "
                               "stranding, checked hourly); refloating, weathering and "
                               "emulsification are not modelled.",
    }
    with open(os.path.join(case_dir, "forecast_result.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    from slicktrace_core.display_geometry import write_forecast_contours
    write_forecast_contours(case_dir, out, particles_by_horizon)
    return out


if __name__ == "__main__":
    import sys
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/cases/case_0001"
    res = run_forecast(case_dir)
    print(f"Forward exposure forecast — {res['incident_id']}")
    print(f"  {res['forcing_mode']}\n")
    for h in res["horizons"]:
        print(f"  +{h['horizon_hours']:>2}h  envelope {h['envelope_area_km2']:>8.1f} km²  "
              f"shoreline fraction {h['modelled_shoreline_fraction']}")
        for e in h["sensitive_area_exposure"]:
            if e["any_contact"]:
                print(f"         contact: {e['name']} "
                      f"({e['modelled_particle_fraction'] * 100:.1f}% of particles)")
    print(f"\n  first modelled shoreline contact: "
          f"{res['first_modelled_shoreline_contact_h'] or 'none within tested horizons'}")
