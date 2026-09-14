"""Tiled inference and seam blending.

Every scene in this repository is 256x256 and processed whole, so none of this
is exercised by the shipped data. It exists because a Sentinel-1 GRD product is
roughly 25,000 x 16,000 pixels: the moment imagery is real, tiling is not
optional, and a slick crossing a tile boundary is the thing that breaks.
"""
import numpy as np
from scipy.ndimage import label

from slicktrace_core.tiling import _cosine_taper, tiled_predict


def _dark(s):
    return (s < 120).astype(np.uint8)


def _scene_with_blob(n=1024, cy=500, cx=448, r=90):
    s = np.full((n, n), 200, dtype=np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    s[((yy - cy) ** 2 + (xx - cx) ** 2) <= r ** 2] = 40
    return s


def test_taper_is_one_inside_and_near_zero_at_the_edge():
    """Near zero, not zero: the ramp samples at pixel centres, so the outermost
    pixel sits half a step in. Asserting exact zero would be asserting an
    off-by-half-a-pixel sampling error."""
    t = _cosine_taper(512, 512, 64)
    assert t[256, 256] == 1.0
    assert t[0, 256] < 1e-3 and t[256, 0] < 1e-3
    assert t[0, 0] < t[0, 256], "corner must taper in both axes"


def test_small_scene_is_not_tiled_at_all():
    """A scene that fits in one tile must be processed whole: tiling it would
    add a blend step with nothing to blend."""
    s = _scene_with_blob(n=256, cy=128, cx=128, r=40)
    r = tiled_predict(s, _dark, tile=512, overlap=64)
    assert r["tiled"] is False and r["n_tiles"] == 1
    assert (r["mask"] == _dark(s)).all()


def test_slick_on_a_seam_stays_one_region():
    """Without blending this is the failure: the boundary cuts the slick in two
    and the minimum-region filter may then discard both halves."""
    s = _scene_with_blob()
    r = tiled_predict(s, _dark, tile=512, overlap=64)
    _, n = label(r["mask"])
    assert r["tiled"] is True
    assert n == 1, f"slick split into {n} regions at the tile boundary"


def test_tiled_result_matches_whole_scene_processing():
    s = _scene_with_blob()
    r = tiled_predict(s, _dark, tile=512, overlap=64)
    assert (r["mask"] == _dark(s)).all(), "blending changed the result"


def test_every_pixel_is_covered_by_some_tile():
    s = _scene_with_blob()
    r = tiled_predict(s, _dark, tile=512, overlap=64)
    assert r["uncovered_px"] == 0


def test_non_square_scene_is_handled():
    s = np.full((900, 1400), 200, dtype=np.uint8)
    yy, xx = np.mgrid[0:900, 0:1400]
    s[((yy - 450) ** 2 + (xx - 896) ** 2) <= 80 ** 2] = 40
    r = tiled_predict(s, _dark, tile=512, overlap=64)
    assert r["uncovered_px"] == 0
    assert (r["mask"] == _dark(s)).all()


def test_overlap_must_be_smaller_than_the_tile():
    import pytest
    with pytest.raises(ValueError):
        tiled_predict(_scene_with_blob(), _dark, tile=256, overlap=256)
