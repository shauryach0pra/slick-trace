"""Multi-region detection geometry.

None of this repository's own cases contains more than one slick, so the
previous single-contour behaviour was invisible here and wrong everywhere else:
a real scene routinely holds a broken discharge trail or two unrelated slicks,
and the second was not reported as unmeasured, it was simply absent. These
tests construct the case the data does not provide.
"""
import json
import numpy as np

from slicktrace_core.detection_geometry import _all_regions, _measure_region


def _manifest():
    return {
        "incident_id": "synthetic_two_region",
        "bbox": {"min_lon": 72.1, "min_lat": 18.4, "max_lon": 73.1, "max_lat": 19.4},
        "img_size_px": 256,
    }


def _two_blobs(n=256):
    """Two disjoint discs, one clearly larger than the other."""
    m = np.zeros((n, n), dtype=np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    m[((yy - 70) ** 2 + (xx - 70) ** 2) <= 25 ** 2] = 1     # larger
    m[((yy - 180) ** 2 + (xx - 190) ** 2) <= 15 ** 2] = 1   # smaller
    return m


def test_both_regions_are_measured():
    regions = _all_regions(_two_blobs(), _manifest(), 411.0, 434.0)
    assert len(regions) == 2, "second slick was dropped"


def test_regions_are_ordered_largest_first():
    regions = _all_regions(_two_blobs(), _manifest(), 411.0, 434.0)
    assert regions[0]["region_px"] > regions[1]["region_px"]


def test_regions_are_measured_separately_not_merged():
    """A merged measurement would span both blobs and report an elongation and
    a centroid belonging to neither."""
    regions = _all_regions(_two_blobs(), _manifest(), 411.0, 434.0)
    a, b = regions
    assert a["centroid"] != b["centroid"]
    assert a["elongation"] < 1.3 and b["elongation"] < 1.3


def test_total_area_is_the_sum_of_regions():
    regions = _all_regions(_two_blobs(), _manifest(), 411.0, 434.0)
    total = sum(r["area_km2"] for r in regions)
    assert total > regions[0]["area_km2"], "total ignores the second region"


def test_single_region_matches_whole_mask_measurement():
    """One region must measure identically whether taken alone or as regions[0],
    so existing single-slick results are unchanged."""
    m = np.zeros((256, 256), dtype=np.uint8)
    yy, xx = np.mgrid[0:256, 0:256]
    m[((yy - 128) ** 2 + (xx - 128) ** 2) <= 30 ** 2] = 1
    whole = _measure_region(m, _manifest(), 411.0, 434.0)
    regions = _all_regions(m, _manifest(), 411.0, 434.0)
    assert len(regions) == 1
    assert regions[0]["area_km2"] == whole["area_km2"]
    assert regions[0]["elongation"] == whole["elongation"]


def test_real_cases_report_their_regions():
    """Every shipped case currently has exactly one region; if this changes the
    generator changed, not the measurement."""
    import glob
    for f in sorted(glob.glob("data/cases/*/detection_result.json")):
        d = json.load(open(f))
        if not d.get("geometry"):
            continue
        assert d["n_regions"] >= 1
        assert d["regions"][0]["area_km2"] == d["geometry"]["area_km2"]
