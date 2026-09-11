"""
Render a filmstrip of the backward hindcast: the envelope diffusing further
back in time, with each vessel colored by whether it was inside the
envelope AT THAT SPECIFIC snapshot (not just its overall verdict) — this is
the static stand-in for the masterplan's interactive UTC time slider (p.8).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from varuna_core.hindcast import (
    build_backward_envelope,
    _interp_track_position,
    _parse,
)


def render(case_dir: str = "data/cases/case_0001", hours_back: int = 24,
           panel_hours: list[float] | None = None,
           out_path: str | None = None):
    with open(os.path.join(case_dir, "manifest.json")) as f:
        manifest = json.load(f)

    snapshots = build_backward_envelope(manifest, hours_back=hours_back)
    panel_hours = panel_hours or [0, 6, 12, 18, 24]
    bbox = manifest["bbox"]
    inclusion_radius = 0.045

    neutral_palette = ["#4c72b0", "#55a868", "#8172b2", "#937860", "#64b5cd", "#ccb974"]

    fig, axes = plt.subplots(1, len(panel_hours), figsize=(3.0 * len(panel_hours), 3.6), sharey=True)

    for ax, target_h in zip(axes, panel_hours):
        snap = min(snapshots, key=lambda s: abs(s.hours_before_acquisition - target_h))
        tree = cKDTree(np.column_stack([snap.particles_lon, snap.particles_lat]))

        ax.scatter(snap.particles_lon, snap.particles_lat, s=4, alpha=0.25,
                   color="#00b0a0", label="envelope particles" if target_h == 0 else None)

        neutral_i = 0
        for tr in manifest["tracks"]:
            pos = _interp_track_position(tr["fixes"], snap.time_utc)
            if pos is None:
                continue  # no data at this snapshot time — simply not drawn
            dist, _ = tree.query([pos[0], pos[1]])
            inside = dist <= inclusion_radius
            color = "#2ca02c" if inside else neutral_palette[neutral_i % len(neutral_palette)]
            neutral_i += 0 if inside else 1
            marker = "o" if inside else "x"
            ax.scatter(*pos, s=55 if inside else 35, color=color, marker=marker,
                       edgecolors="black" if inside else None, linewidths=0.6, zorder=5)

        ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
        ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
        ax.set_aspect("equal")
        ax.set_title(f"T-{target_h:.0f}h\n{snap.time_utc.strftime('%H:%M UTC')}", fontsize=9)
        ax.tick_params(labelsize=6)

    axes[0].set_ylabel("lat", fontsize=8)
    fig.suptitle(
        f"{manifest['incident_id']} — backward hindcast envelope\n"
        f"green circle = vessel inside envelope at this time  |  x = has data, outside  |  "
        f"[SYNTHETIC]",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.88])

    out_path = out_path or os.path.join(case_dir, "hindcast_filmstrip.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    path = render()
    print(f"Saved {path}")
