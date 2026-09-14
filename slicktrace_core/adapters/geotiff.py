"""
Read a GeoTIFF scene into the pixels, geometry and provenance this pipeline needs.

This is the other half of the "adapter, not a rewrite" claim. The AIS side has a
MarineCadastre reader; this is the imagery side. Everything downstream consumes
an array plus a bounding box plus a radiometric scale, so a reader that produces
those three is the whole integration.

WHY RASTERIO IS NOT IN requirements.lock
    It pulls GDAL, which is well over a hundred megabytes, and the shipped
    runtime does not need it: the demonstration cases are PNG and the classical
    detector reads arrays. Adding it would multiply the image size for a
    capability no shipped case exercises. It is therefore imported lazily, and
    its absence produces an instruction rather than an ImportError traceback -
    the same treatment torch gets for the same reason.

WHAT IT REFUSES TO DO
    It does not guess the radiometric scale silently. A GRD product is linear
    power and the Zenodo set is dB; converting the wrong one produces an empty
    mask that reads as a clean sea. The scale is inferred, reported with its
    evidence, and left unconverted - see `slicktrace_core.radiometry`. A caller
    that knows the scale should declare it.

    It does not reproject. The bounding box is returned in the raster's own CRS
    alongside a WGS84 box when the CRS is known, and a scene in a projected CRS
    is flagged rather than silently treated as degrees.
"""
from __future__ import annotations

import numpy as np

from slicktrace_core import radiometry

RASTERIO_MISSING = (
    "rasterio is not installed. It is deliberately absent from requirements.lock "
    "because it pulls GDAL (>100 MB) and the shipped runtime does not need it: "
    "the demonstration cases are PNG. Install it to read GeoTIFF:\n"
    "    pip install rasterio"
)


class GeoTiffUnavailable(RuntimeError):
    """Raised when rasterio is absent, with instructions rather than a traceback."""


def _require_rasterio():
    try:
        import rasterio  # noqa: F401
        return rasterio
    except ImportError as exc:
        raise GeoTiffUnavailable(RASTERIO_MISSING) from exc


def read_geotiff(path: str, band: int = 1, declared_scale: str | None = None) -> dict:
    """Read one band plus the geometry and provenance a scene needs.

    `declared_scale` skips radiometric inference. Pass it whenever the product
    is known: inference is a fallback, not a feature.
    """
    rio = _require_rasterio()

    with rio.open(path) as src:
        arr = src.read(band)
        crs = src.crs
        b = src.bounds
        tags = src.tags()

        bbox_native = {"min_x": float(b.left), "min_y": float(b.bottom),
                       "max_x": float(b.right), "max_y": float(b.top)}
        is_geographic = bool(crs and crs.is_geographic)

        bbox_wgs84 = None
        if crs is not None:
            if is_geographic:
                bbox_wgs84 = {"min_lon": float(b.left), "min_lat": float(b.bottom),
                              "max_lon": float(b.right), "max_lat": float(b.top)}
            else:
                try:
                    from rasterio.warp import transform_bounds
                    left, bot, right, top = transform_bounds(crs, "EPSG:4326", *b)
                    bbox_wgs84 = {"min_lon": float(left), "min_lat": float(bot),
                                  "max_lon": float(right), "max_lat": float(top)}
                except Exception:
                    bbox_wgs84 = None

        # Pixel size in the raster's own units. For a geographic CRS these are
        # degrees, not metres, and saying so prevents the 5% error assumption
        # A15 records from reappearing at a different layer.
        px_w, px_h = abs(src.transform.a), abs(src.transform.e)

        scale = radiometry.describe(arr)

        return {
            "path": path,
            "array": arr,
            "shape": [int(arr.shape[0]), int(arr.shape[1])],
            "dtype": str(arr.dtype),
            "band": band,
            "n_bands": int(src.count),
            "crs": str(crs) if crs else None,
            "crs_is_geographic": is_geographic,
            "bbox_native": bbox_native,
            "bbox_wgs84": bbox_wgs84,
            "pixel_size_native": [px_w, px_h],
            "pixel_size_units": "degrees" if is_geographic else "CRS units (projected)",
            "nodata": None if src.nodata is None else float(src.nodata),
            "acquired_utc": _acquisition_time(tags),
            "radiometry": ({"declared_scale": declared_scale, **scale}
                           if declared_scale else scale),
            "tags": {k: v for k, v in tags.items() if len(str(v)) < 200},
            "notes": _notes(crs, is_geographic, declared_scale, scale),
        }


def _acquisition_time(tags: dict) -> str | None:
    """Acquisition time from whichever tag the producer used, or None.

    None rather than the file mtime: a file's modification time is when it was
    copied, and treating that as an observation time would silently shift every
    hindcast window.
    """
    for key in ("ACQUISITION_DATETIME", "TIFFTAG_DATETIME", "DATETIME",
                "start_time", "ACQUISITION_START_TIME"):
        if tags.get(key):
            return str(tags[key])
    return None


def _notes(crs, is_geographic: bool, declared: str | None, scale: dict) -> list[str]:
    out = []
    if crs is None:
        out.append("no CRS on this raster: pixel coordinates cannot be georeferenced, "
                   "so any position derived from it is in image space only")
    elif not is_geographic:
        out.append(f"projected CRS ({crs}): pixel sizes are in projected units, not "
                   "degrees. A WGS84 bounding box is supplied for convenience; the "
                   "native box is authoritative")
    if declared is None:
        out.append(f"radiometric scale inferred as '{scale['inferred_scale']}' and not "
                   "converted. Declare the scale where it is known: a wrong conversion "
                   "does not raise, it returns a plausible-looking wrong answer")
    return out
