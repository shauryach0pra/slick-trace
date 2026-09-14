"""
SAR radiometry: what scale is this raster on, and what happens if you guess.

A SAR amplitude image can arrive on any of three scales, and they are not
interchangeable:

    DN          raw digital numbers from a GRD product, uncalibrated
    linear      sigma-nought as a power ratio, typically 1e-4 to 10
    dB          sigma-nought in decibels, typically -35 to +5

The failure this module exists to prevent is silent. Applying a linear-to-dB
conversion to a raster already in dB takes the logarithm of negative numbers:
every negative pixel becomes NaN, the mask comes back empty, and an empty mask
is indistinguishable from a scene with no oil in it. The pipeline reports a
clean sea and nothing anywhere says an error occurred.

Going the other way is quieter still and worse. Treating dB values as linear
power produces a raster where the darkest pixels have the largest magnitude,
because -30 dB is a smaller number than -5 dB. A darkness threshold then selects
open water and rejects the slick, and the result looks like a detection.

WHY THIS IS INFERENCE, NOT CONFIGURATION
    A caller can always declare the scale and should. When nothing is declared,
    the scale is inferred from the value distribution - the three scales occupy
    ranges that barely overlap - and the inference is returned with its evidence
    so a caller can disagree. Where the evidence is genuinely ambiguous the
    answer is "unknown" and no conversion is applied, because a wrong guess here
    does not raise; it returns a plausible-looking wrong answer.

    This repository's own scenes are 8-bit uint synthetic amplitude, which is
    none of the three. They are reported as such rather than forced into the
    nearest category.
"""
from __future__ import annotations

import numpy as np

# Below this, a negative-valued raster is not plausibly anything but dB.
DB_PLAUSIBLE_MIN = -60.0
DB_PLAUSIBLE_MAX = 20.0
# Sigma-nought as a power ratio over open water rarely exceeds ~10.
LINEAR_PLAUSIBLE_MAX = 50.0


class RadiometryError(ValueError):
    """Raised rather than returning a quietly wrong raster."""


def infer_scale(arr: np.ndarray) -> dict:
    """Infer the radiometric scale, with the evidence for the inference.

    Returns one of: 'db', 'linear', 'dn_uint', 'unknown'. Never converts.
    """
    a = np.asarray(arr)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return {"scale": "unknown", "reason": "no finite values in the raster"}

    lo, hi = float(finite.min()), float(finite.max())
    ev = {"min": round(lo, 4), "max": round(hi, 4), "dtype": str(a.dtype)}

    # Integer rasters are digital numbers: sigma-nought is a real-valued
    # quantity and is not stored as uint8 or uint16 by anything that calibrated it.
    if np.issubdtype(a.dtype, np.integer):
        return {"scale": "dn_uint", "evidence": ev,
                "reason": ("integer dtype: these are digital numbers, not calibrated "
                           "sigma-nought. Calibration to linear or dB requires the "
                           "product's own calibration LUT, which is not derivable "
                           "from the pixel values")}

    if lo < 0:
        if lo < DB_PLAUSIBLE_MIN or hi > DB_PLAUSIBLE_MAX:
            return {"scale": "unknown", "evidence": ev,
                    "reason": (f"negative values imply dB, but the range "
                               f"[{lo:.1f}, {hi:.1f}] falls outside the plausible dB "
                               f"span [{DB_PLAUSIBLE_MIN}, {DB_PLAUSIBLE_MAX}]")}
        return {"scale": "db", "evidence": ev,
                "reason": ("negative values: linear power cannot be negative, so this "
                           "is dB")}

    if hi > LINEAR_PLAUSIBLE_MAX:
        return {"scale": "unknown", "evidence": ev,
                "reason": (f"non-negative but maximum {hi:.1f} exceeds the plausible "
                           f"linear sigma-nought ceiling of {LINEAR_PLAUSIBLE_MAX}")}

    return {"scale": "linear", "evidence": ev,
            "reason": ("non-negative and within the plausible sigma-nought range; "
                       "note that an all-positive dB raster would look identical, "
                       "so declare the scale explicitly where it is known")}


def to_db(arr: np.ndarray, scale: str | None = None):
    """Convert to dB, refusing rather than guessing when the scale is unclear.

    `scale` declares the input scale and skips inference. Passing the wrong
    value here is the one way to still get a wrong answer, which is why the
    inference is returned alongside so the two can be compared.
    """
    a = np.asarray(arr, dtype=float)
    inferred = infer_scale(arr)
    used = scale or inferred["scale"]

    if used == "db":
        return a, {"converted": False, "input_scale": "db", "inferred": inferred,
                   "note": "already in dB; no conversion applied"}

    if used == "linear":
        if np.any(a < 0):
            raise RadiometryError(
                "raster declared linear but contains negative values; linear power "
                "cannot be negative, so either the declaration or the data is wrong. "
                "Converting anyway would produce NaN for every negative pixel and an "
                "empty mask indistinguishable from a clean sea.")
        with np.errstate(divide="ignore"):
            out = 10.0 * np.log10(np.where(a > 0, a, np.nan))
        return out, {"converted": True, "input_scale": "linear", "inferred": inferred,
                     "zeros_masked": int((a == 0).sum()),
                     "note": "10*log10 applied; exact zeros are NaN, not -inf"}

    if used == "dn_uint":
        raise RadiometryError(
            "raster is uncalibrated digital numbers. Converting DN to dB requires the "
            "product's calibration LUT and cannot be done from pixel values alone. "
            "Calibrate first, or declare the scale if these are in fact sigma-nought.")

    raise RadiometryError(
        f"radiometric scale could not be determined: {inferred.get('reason')}. "
        "Declare it explicitly rather than allowing a guess: applying the wrong "
        "conversion here does not raise, it returns a plausible-looking wrong answer.")


def describe(arr: np.ndarray) -> dict:
    """Radiometric provenance for an artifact, safe on any input."""
    inf = infer_scale(arr)
    return {
        "inferred_scale": inf["scale"],
        "reason": inf.get("reason"),
        "evidence": inf.get("evidence"),
        "detection_assumes": ("a darkness threshold on amplitude. On a dB raster the "
                              "ordering is preserved, so the threshold still selects "
                              "dark pixels; on a raster whose scale has been "
                              "misidentified and converted, it selects the wrong ones "
                              "and reports a confident detection"),
    }
