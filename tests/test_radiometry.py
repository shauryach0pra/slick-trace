"""SAR radiometric scale handling.

This repository's scenes are 8-bit synthetic amplitude, so none of this is
exercised by the shipped data. It exists because the failure it prevents is
silent: a dB raster pushed through a linear-to-dB conversion becomes entirely
NaN, the mask comes back empty, and an empty mask is indistinguishable from a
scene with no oil in it.
"""
import numpy as np
import pytest

from slicktrace_core.radiometry import (RadiometryError, describe, infer_scale,
                                        to_db)


def _db(n=64, seed=0):
    return np.random.default_rng(seed).uniform(-28, -5, (n, n))


def _linear(n=64, seed=0):
    return 10 ** (_db(n, seed) / 10)


def test_negative_values_are_recognised_as_db():
    assert infer_scale(_db())["scale"] == "db"


def test_positive_small_values_are_recognised_as_linear():
    assert infer_scale(_linear())["scale"] == "linear"


def test_integer_raster_is_digital_numbers_not_sigma_nought():
    a = np.random.default_rng(0).integers(0, 255, (64, 64), dtype=np.uint8)
    assert infer_scale(a)["scale"] == "dn_uint"


def test_digital_numbers_cannot_be_converted_without_a_calibration_lut():
    a = np.random.default_rng(0).integers(0, 255, (64, 64), dtype=np.uint8)
    with pytest.raises(RadiometryError, match="calibration LUT"):
        to_db(a)


def test_db_raster_is_not_converted_twice():
    """The headline failure. Converting an already-dB raster takes the log of
    negative numbers and yields an all-NaN array."""
    a = _db()
    out, info = to_db(a)
    assert info["converted"] is False
    assert np.array_equal(out, a)
    assert not np.isnan(out).any()


def test_declaring_the_wrong_scale_raises_rather_than_returning_nan():
    with pytest.raises(RadiometryError, match="cannot be negative"):
        to_db(_db(), scale="linear")


def test_linear_converts_to_a_plausible_db_range():
    out, info = to_db(_linear())
    assert info["converted"] is True
    assert -35 < np.nanmin(out) and np.nanmax(out) < 5


def test_conversion_round_trips():
    lin = _linear()
    out, _ = to_db(lin)
    assert np.allclose(out, 10 * np.log10(lin))


def test_zeros_become_nan_not_negative_infinity():
    a = _linear(); a[0, 0] = 0.0
    out, info = to_db(a)
    assert np.isnan(out[0, 0]) and not np.isinf(out).any()
    assert info["zeros_masked"] == 1


def test_implausible_range_is_unknown_rather_than_guessed():
    a = np.random.default_rng(0).uniform(-500, 500, (64, 64))
    assert infer_scale(a)["scale"] == "unknown"
    with pytest.raises(RadiometryError, match="could not be determined"):
        to_db(a)


def test_all_positive_db_is_genuinely_ambiguous_and_the_docstring_says_so():
    """An all-positive dB raster is indistinguishable from linear by range
    alone. Inference reports linear; the honest fix is for the caller to
    declare the scale, and the returned reason says exactly that."""
    a = np.random.default_rng(0).uniform(1, 8, (64, 64))
    r = infer_scale(a)
    assert r["scale"] == "linear"
    assert "declare the scale explicitly" in r["reason"]
    out, info = to_db(a, scale="db")
    assert info["converted"] is False


def test_describe_is_safe_on_our_own_scenes():
    import json
    from PIL import Image
    s = np.array(Image.open("data/cases/case_0001/scene.png").convert("L"))
    d = describe(s)
    assert d["inferred_scale"] == "dn_uint"
    json.dumps(d)
