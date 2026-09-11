"""
Historical mapping: backward hindcast envelope + candidate filtering.

Implements the masterplan's "source-window map" (p.8) and step 1-2 of the
attribution pipeline (p.10), stopping short of forward-replay ranking
(that's step 4 / varuna_core.attribution — not built yet):

  1. Seed particles at the observed slick footprint (from the ground-truth
     mask here; a real system would use the detector's output polygon).
  2. Backtrack them under REVERSED wind/current forcing, with uncertainty
     (spread) growing the further back in time we go — release timing,
     duration and diffusivity are all unknown, so the envelope should
     diffuse, not converge to a point (explicit masterplan requirement,
     p.3 and p.10: "do not force particles to converge").
  3. At each hourly step backward, test every candidate vessel's
     (interpolated, gap-aware) position against the particle cloud. A
     vessel is only ever a "candidate" if it was physically inside the
     envelope at some point in the backward window — not merely closest to
     the slick at observation time.

Three explicit outcomes per vessel (never just candidate/excluded):
  - "candidate":   was inside the envelope at some queried time
  - "excluded":    track data covers the window, but never entered it
  - "unassessed":  track has no data covering the queried window at all
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

DEG_PER_MS_HR = 3600 / 111_000  # rough m/s -> deg/hr at these latitudes


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


@dataclass
class EnvelopeSnapshot:
    hours_before_acquisition: float
    time_utc: datetime
    particles_lon: np.ndarray
    particles_lat: np.ndarray


@dataclass
class VesselAssessment:
    vessel_key: str
    status: str  # "candidate" | "excluded" | "unassessed"
    first_entry_hours_before: float | None = None  # earliest time (backward) found inside
    reason: str = ""
    inside_at: list[float] = field(default_factory=list)  # hours_before values where inside


def _mask_to_lonlat_particles(mask_path: str, bbox: dict, img_size: int,
                                n_particles: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    mask = np.array(Image.open(mask_path)) > 127
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("empty mask — nothing to seed particles from")
    idx = rng.integers(0, len(xs), size=n_particles)
    xs, ys = xs[idx], ys[idx]
    lon = bbox["min_lon"] + (xs / img_size) * (bbox["max_lon"] - bbox["min_lon"])
    lat = bbox["max_lat"] - (ys / img_size) * (bbox["max_lat"] - bbox["min_lat"])
    return lon, lat


def build_backward_envelope(manifest: dict, hours_back: int = 24, step_hours: float = 1.0,
                              n_particles: int = 300, base_diffusivity_deg: float = 0.006,
                              growth_per_hour_deg: float = 0.0025,
                              seed: int = 123) -> list[EnvelopeSnapshot]:
    """Backtrack the observed slick footprint under reversed forcing.
    Spread grows with hours-back so the envelope diffuses rather than
    converging to a point — release time/duration/diffusivity are unknown."""
    rng = np.random.default_rng(seed)
    forcing = np.load(manifest["forcing_path"])
    u, v = float(forcing["u"]), float(forcing["v"])
    acquired = _parse(manifest["acquired_utc"])
    bbox = manifest["bbox"]
    img_size = 256  # matches synth_generator's img_size

    lon, lat = _mask_to_lonlat_particles(manifest["mask_groundtruth_path"], bbox, img_size,
                                          n_particles, rng)
    snapshots = [EnvelopeSnapshot(0.0, acquired, lon.copy(), lat.copy())]

    n_steps = int(hours_back / step_hours)
    for step in range(1, n_steps + 1):
        hrs = step * step_hours
        # reverse advection: subtract the forward drift
        lon = lon - u * step_hours * DEG_PER_MS_HR
        lat = lat - v * step_hours * DEG_PER_MS_HR
        # growing uncertainty: diffusivity increases the further back we go
        spread = base_diffusivity_deg + growth_per_hour_deg * hrs
        lon = lon + rng.normal(0, spread, size=lon.shape)
        lat = lat + rng.normal(0, spread, size=lat.shape)
        snapshots.append(EnvelopeSnapshot(hrs, acquired - timedelta(hours=hrs), lon.copy(), lat.copy()))

    return snapshots


def _interp_track_position(fixes: list[dict], t: datetime) -> tuple[float, float] | None:
    """Linear interpolation strictly within the track's own observed time
    range. Returns None (a data gap) rather than extrapolating."""
    times = [_parse(f["t_utc"]) for f in fixes]
    if not times or t < min(times) or t > max(times):
        return None
    for i in range(len(times) - 1):
        if times[i] <= t <= times[i + 1]:
            span = (times[i + 1] - times[i]).total_seconds()
            frac = 0.0 if span == 0 else (t - times[i]).total_seconds() / span
            lon = fixes[i]["lon"] + frac * (fixes[i + 1]["lon"] - fixes[i]["lon"])
            lat = fixes[i]["lat"] + frac * (fixes[i + 1]["lat"] - fixes[i]["lat"])
            return lon, lat
    return (fixes[0]["lon"], fixes[0]["lat"])  # exact match at an endpoint


def assess_vessels(manifest: dict, snapshots: list[EnvelopeSnapshot],
                    inclusion_radius_deg: float = 0.045) -> list[VesselAssessment]:
    """Test every candidate vessel's position, at every backward snapshot
    time, against the particle cloud (nearest-particle distance — NOT a
    convex hull, so disjoint/diffuse envelope lobes aren't falsely bridged)."""
    trees = {
        snap.hours_before_acquisition: cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))
        for snap in snapshots
    }

    results = []
    for tr in manifest["tracks"]:
        vkey = tr["vessel_key"]
        any_data = False
        inside_at = []
        for snap in snapshots:
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                continue
            any_data = True
            dist, _ = trees[snap.hours_before_acquisition].query([pos[0], pos[1]])
            if dist <= inclusion_radius_deg:
                inside_at.append(snap.hours_before_acquisition)

        if not any_data:
            results.append(VesselAssessment(vkey, "unassessed",
                                             reason="no track data covers the queried backward window"))
        elif inside_at:
            results.append(VesselAssessment(vkey, "candidate",
                                             first_entry_hours_before=max(inside_at),
                                             reason=f"inside envelope at {len(inside_at)} of "
                                                    f"{len(snapshots)} queried times",
                                             inside_at=sorted(inside_at)))
        else:
            results.append(VesselAssessment(vkey, "excluded",
                                             reason="track data present throughout window; "
                                                    "never inside the backward envelope"))
    return results


def run_historical_mapping(case_dir: str, hours_back: int = 24) -> dict:
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)
    snapshots = build_backward_envelope(manifest, hours_back=hours_back)
    assessments = assess_vessels(manifest, snapshots)

    out = {
        "incident_id": manifest["incident_id"],
        "hours_back": hours_back,
        "assessments": [a.__dict__ for a in assessments],
    }
    out_path = os.path.join(case_dir, "historical_mapping.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    result = run_historical_mapping("data/cases/case_0001")
    print(f"Historical mapping for {result['incident_id']} "
          f"({result['hours_back']}h backward window):\n")
    for a in result["assessments"]:
        print(f"  {a['vessel_key']:16s} -> {a['status']:11s}  {a['reason']}")
