"""
Lee adaptive speckle filtering.

SAR speckle is multiplicative noise from coherent imaging: neighbouring
resolution cells with identical backscatter still differ, because the returns
from scatterers inside each cell add with random phase. A simple box blur
suppresses it, and takes the slick boundary with it.

Lee's filter (1980) blurs adaptively. Where local variance is close to the
scene-wide variance, the variation is speckle and the pixel is pulled toward its
local mean. Where local variance is much higher, the variation is structure -
an edge - and the pixel is left alone. The weight is the ratio of the two.

WHY THIS IS BENCHMARKED RATHER THAN ASSUMED
    The masterplan requires measuring whether speckle filtering helps rather
    than assuming it. It was measured, and the result is not the usual
    trade-off. Filtering raises recall AND permits a stricter darkness
    threshold, so the false-positive rate on look-alikes stays at zero:

        raw, threshold 0.75      val IoU 0.677  recall 0.682  FP 0.000
        Lee 7x7, threshold 0.65  val IoU 0.857  recall 0.860  FP 0.000

    The threshold was chosen on the training split before val or test were
    looked at. Recall clears the 0.85 target for the first time, and the
    operating point is not paid for elsewhere - which is worth stating plainly,
    because the previous operating-point sweep showed that buying recall by
    loosening the threshold alone costs false positives steeply.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

DEFAULT_WINDOW = 7


def lee_filter(img: np.ndarray, size: int = DEFAULT_WINDOW) -> np.ndarray:
    """Lee 1980 adaptive filter. Returns float, same shape as input.

    Window size is a resolution choice, not a tuning knob: it should span
    several resolution cells without spanning the narrowest feature worth
    keeping. At 434 m pixels a 7x7 window is about 3 km, well below the
    narrowest slick dimension measured here (15.8 km on the ribbon case).
    """
    if size < 3 or size % 2 == 0:
        raise ValueError("window size must be odd and at least 3")
    a = img.astype(float)
    mean = uniform_filter(a, size)
    sq_mean = uniform_filter(a ** 2, size)
    local_var = np.maximum(sq_mean - mean ** 2, 0.0)
    overall_var = float(np.mean(local_var))
    # Weight -> 0 in flat areas (trust the local mean), -> 1 at edges (trust the
    # pixel). The epsilon keeps a perfectly uniform image from dividing by zero.
    w = local_var / (local_var + overall_var + 1e-9)
    return mean + w * (a - mean)
