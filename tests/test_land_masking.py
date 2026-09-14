"""Land rejection.

Every case in this repository places its slick in open water, so nothing here
exercises the guard. That is exactly why it needs testing: land is dark in SAR
for its own reasons - smooth terrain, wet soil, radar shadow behind relief - and
a darkness-threshold detector cannot distinguish that from a slick. On a coastal
scene, which is where spills are actually investigated, the difference is
between a detection and a hillside.
"""
import json
import numpy as np

from slicktrace_core.detection_geometry import _land_mask, _reject_land_regions


def _manifest():
    return json.load(open("data/cases/case_0001/manifest.json"))


def test_land_mask_is_east_of_the_coastline():
    land = _land_mask(_manifest(), (256, 256))
    assert land is not None
    assert land[:, -1].all(), "easternmost column should be land"
    assert not land[:, 0].any(), "westernmost column should be water"


def test_land_mask_absent_without_a_coastline():
    m = _manifest(); m["coastline"] = []
    assert _land_mask(m, (256, 256)) is None


def test_no_coastline_means_no_rejection_not_silent_failure():
    m = _manifest(); m["coastline"] = []
    pred = np.zeros((256, 256), dtype=np.uint8); pred[100:120, 100:120] = 1
    out, info = _reject_land_regions(pred, m)
    assert out.sum() == pred.sum(), "nothing should be dropped without a coastline"
    assert info["land_mask_available"] is False


def test_a_region_wholly_on_land_is_rejected():
    m = _manifest()
    pred = np.zeros((256, 256), dtype=np.uint8)
    pred[100:120, 245:255] = 1
    out, info = _reject_land_regions(pred, m)
    assert out.sum() == 0
    assert info["regions_rejected_as_land"] == 1


def test_a_region_wholly_at_sea_is_kept():
    m = _manifest()
    pred = np.zeros((256, 256), dtype=np.uint8)
    pred[100:120, 40:60] = 1
    out, info = _reject_land_regions(pred, m)
    assert out.sum() == pred.sum()
    assert info["regions_rejected_as_land"] == 0


def test_a_region_straddling_the_shoreline_is_kept():
    """Oil reaches coastlines. Discarding a landfall detection would be worse
    than the false positive the guard exists to prevent."""
    m = _manifest()
    pred = np.zeros((256, 256), dtype=np.uint8)
    pred[100:120, 225:245] = 1
    out, info = _reject_land_regions(pred, m)
    assert out.sum() == pred.sum(), "a landfall slick must survive"
    assert info["regions_rejected_as_land"] == 0


def test_sea_region_survives_while_land_region_is_dropped():
    m = _manifest()
    pred = np.zeros((256, 256), dtype=np.uint8)
    pred[60:80, 40:60] = 1
    pred[160:180, 245:255] = 1
    out, info = _reject_land_regions(pred, m)
    assert info["regions_rejected_as_land"] == 1
    assert out[60:80, 40:60].all() and not out[160:180, 245:255].any()


def test_real_cases_lose_nothing_to_land_rejection():
    import glob
    for f in sorted(glob.glob("data/cases/*/detection_result.json")):
        d = json.load(open(f))
        lr = d.get("land_rejection") or {}
        assert lr.get("regions_rejected_as_land") == 0, f"{f} lost a region to land"
