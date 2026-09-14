"""GeoTIFF reader.

The imagery half of the "adapter, not a rewrite" claim. rasterio is an optional
dependency - it pulls GDAL and the shipped runtime does not need it - so these
tests skip where it is absent, except the one that checks the absence itself is
handled with an instruction rather than a traceback.
"""
import numpy as np
import pytest

from slicktrace_core.adapters.geotiff import (GeoTiffUnavailable, RASTERIO_MISSING,
                                              read_geotiff)

rasterio = pytest.importorskip("rasterio", reason="rasterio is optional")
from rasterio.transform import from_bounds  # noqa: E402


@pytest.fixture
def db_scene(tmp_path):
    """A dB-scaled scene in WGS84, like the Zenodo set."""
    p = tmp_path / "db.tif"
    arr = np.random.default_rng(0).uniform(-28, -5, (64, 64)).astype("float32")
    with rasterio.open(p, "w", driver="GTiff", height=64, width=64, count=1,
                       dtype="float32", crs="EPSG:4326",
                       transform=from_bounds(72.1, 18.4, 73.1, 19.4, 64, 64)) as d:
        d.write(arr, 1)
        d.update_tags(ACQUISITION_DATETIME="2026-09-10T04:30:00Z")
    return str(p)


@pytest.fixture
def dn_scene(tmp_path):
    """Uncalibrated digital numbers in a projected CRS, like a raw GRD."""
    p = tmp_path / "dn.tif"
    arr = np.random.default_rng(1).integers(0, 4095, (32, 32)).astype("uint16")
    with rasterio.open(p, "w", driver="GTiff", height=32, width=32, count=1,
                       dtype="uint16", crs="EPSG:32643",
                       transform=from_bounds(200000, 2050000, 230000, 2080000, 32, 32)) as d:
        d.write(arr, 1)
    return str(p)


def test_reads_pixels_and_shape(db_scene):
    r = read_geotiff(db_scene)
    assert r["shape"] == [64, 64] and r["dtype"] == "float32"
    assert isinstance(r["array"], np.ndarray)


def test_geographic_crs_gives_a_wgs84_box_directly(db_scene):
    r = read_geotiff(db_scene)
    assert r["crs_is_geographic"] is True
    assert abs(r["bbox_wgs84"]["min_lon"] - 72.1) < 1e-6
    assert r["pixel_size_units"] == "degrees"


def test_projected_crs_is_flagged_and_reprojected(dn_scene):
    """A projected scene must not be silently treated as degrees."""
    r = read_geotiff(dn_scene)
    assert r["crs_is_geographic"] is False
    assert "projected units, not degrees" in " ".join(r["notes"])
    assert r["bbox_wgs84"] is not None
    assert 70 < r["bbox_wgs84"]["min_lon"] < 75


def test_db_raster_is_detected_and_not_converted(db_scene):
    """The silent failure this guards: converting an already-dB raster yields
    an all-NaN array and an empty mask indistinguishable from clean sea."""
    r = read_geotiff(db_scene)
    assert r["radiometry"]["inferred_scale"] == "db"
    assert not np.isnan(r["array"]).any()


def test_integer_raster_is_reported_as_uncalibrated(dn_scene):
    r = read_geotiff(dn_scene)
    assert r["radiometry"]["inferred_scale"] == "dn_uint"


def test_declared_scale_is_recorded_alongside_the_inference(db_scene):
    """Declaration and inference are both kept so they can be compared."""
    r = read_geotiff(db_scene, declared_scale="db")
    assert r["radiometry"]["declared_scale"] == "db"
    assert r["radiometry"]["inferred_scale"] == "db"


def test_acquisition_time_is_read_from_tags(db_scene):
    assert read_geotiff(db_scene)["acquired_utc"].startswith("2026-09-10")


def test_missing_acquisition_time_is_none_not_the_file_mtime(dn_scene):
    """A file's modification time is when it was copied. Treating it as an
    observation time would silently shift every hindcast window."""
    assert read_geotiff(dn_scene)["acquired_utc"] is None


def test_absent_rasterio_gives_instructions_not_a_traceback():
    """Checks the message a user without rasterio would see."""
    assert "pip install rasterio" in RASTERIO_MISSING
    assert issubclass(GeoTiffUnavailable, RuntimeError)
