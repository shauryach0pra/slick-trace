"""
Real geography for the scene, and one land test everything shares.

The coastline is the committed Natural Earth 10 m extract (data/geo). Before
this module, three different approximations stood in for it: the generator
drew an invented coastline about 19 km east of the real one, the detector
treated land as everything east of a latitude-interpolated line (which
zig-zags on a creek-cut shore), and the forecast counted anything east of the
coastline's westernmost point as ashore. On real imagery that put a synthetic
mangrove reserve over the city and let a forecast plume drift inland.

Here the coastline is closed around the land that lies east of it into a
polygon, and "on land" is a point-in-polygon test against that. It is still a
scene-scale shoreline, not a harbour chart: Natural Earth 10 m resolves the
Mumbai creeks only coarsely, and that is stated wherever it matters.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

import numpy as np
from matplotlib.path import Path

_COAST_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "geo", "coastline_mumbai.json")

# Land lies east of this coastline. The polygon is closed this far east of the
# easternmost coastline point, well outside any scene it serves.
_EAST_CLOSE_DEG = 1.0

SOURCE_NOTE = ("Natural Earth 10 m coastline (public domain); land is the area east of it. "
               "Scene-scale: narrow creeks and harbour detail are resolved only coarsely.")


@lru_cache(maxsize=1)
def real_coastline() -> list[list[float]] | None:
    """The committed coastline as one [lon, lat] polyline, or None if absent."""
    if not os.path.exists(_COAST_FILE):
        return None
    with open(_COAST_FILE) as fh:
        geo = json.load(fh)
    coords = geo.get("coordinates") or geo.get("geometry", {}).get("coordinates") or []
    segs = coords if coords and isinstance(coords[0][0], (list, tuple)) else [coords]
    line = max(segs, key=len) if segs else []
    return [[float(x), float(y)] for x, y in line] if len(line) > 1 else None


def _land_path(coastline) -> Path | None:
    if not coastline or len(coastline) < 2:
        return None
    line = np.asarray(coastline, dtype=float)
    east = float(line[:, 0].max()) + _EAST_CLOSE_DEG
    first, last = line[0], line[-1]
    ring = np.vstack([line, [east, last[1]], [east, first[1]], first])
    return Path(ring)


@lru_cache(maxsize=8)
def _cached_path(key: tuple) -> Path | None:
    return _land_path([list(p) for p in key])


def land_path(coastline) -> Path | None:
    """Closed land polygon for a coastline polyline (land to its east)."""
    if not coastline or len(coastline) < 2:
        return None
    return _cached_path(tuple((float(x), float(y)) for x, y in coastline))


def on_land(lon, lat, coastline=None):
    """True where (lon, lat) is on land. Scalars or arrays.

    With no coastline given, the real one is used. With no coastline at all,
    nothing is land: the absence of a shoreline is never reported as sea
    that happens to be dry.
    """
    path = land_path(coastline if coastline is not None else real_coastline())
    lon_a, lat_a = np.broadcast_arrays(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    if path is None:
        out = np.zeros(lon_a.shape, dtype=bool)
    else:
        pts = np.column_stack([lon_a.ravel(), lat_a.ravel()])
        out = path.contains_points(pts).reshape(lon_a.shape)
    return bool(out) if out.ndim == 0 else out


def land_mask(bbox: dict, shape: tuple[int, int], coastline=None) -> np.ndarray | None:
    """Boolean raster, True where a pixel centre is on land. Row 0 is north."""
    path = land_path(coastline if coastline is not None else real_coastline())
    if path is None:
        return None
    h, w = shape
    lats = bbox["max_lat"] - (np.arange(h) + 0.5) / h * (bbox["max_lat"] - bbox["min_lat"])
    lons = bbox["min_lon"] + (np.arange(w) + 0.5) / w * (bbox["max_lon"] - bbox["min_lon"])
    lon_g, lat_g = np.meshgrid(lons, lats)
    return on_land(lon_g, lat_g, coastline if coastline is not None else real_coastline())


def coastline_for_bbox(bbox: dict, margin_deg: float = 0.05, decimals: int = 5) -> list[list[float]]:
    """The real coastline, cut to the vertices within the scene plus a margin.

    A contiguous run is kept (from the first vertex inside to the last), so the
    polyline stays one piece and the land polygon built from it stays closed
    the right way round.
    """
    line = real_coastline() or []
    inside = [i for i, (x, y) in enumerate(line)
              if bbox["min_lat"] - margin_deg <= y <= bbox["max_lat"] + margin_deg]
    if not inside:
        return []
    run = line[inside[0]: inside[-1] + 1]
    return [[round(x, decimals), round(y, decimals)] for x, y in run]
