"""
Probability contours for the backward origin envelope.

The envelope is a particle cloud, and a cloud of three hundred dots communicates
"somewhere around here" without saying how much of the probability sits where. A
reviewer looking at it cannot tell whether the spread is tight or diffuse, which
is precisely the judgement the envelope exists to support.

Contours enclosing 50, 75 and 90 percent of the density say it directly. They
are computed by kernel density estimate over the particles, then by finding the
density level whose superlevel set holds the requested fraction of total mass -
not by drawing an ellipse at some number of standard deviations, which would
assume the cloud is Gaussian when the whole point of the ensemble is that it is
not.

WHAT THESE ARE NOT
    Not a confidence region for the release point. The particles come from one
    transport model over one forcing field; the contours describe where that
    model puts the mass, and inherit every assumption the model makes. A tight
    90 percent contour means the model is confident, not that the answer is
    certain.
"""
from __future__ import annotations

import numpy as np

DEFAULT_LEVELS = (0.5, 0.75, 0.9)
MIN_PARTICLES = 12


def rings_of(contour_set) -> list[list[list[float]]]:
    """Every loop of a contour set as its own ring.

    Since matplotlib 3.8 each level comes back as one Path holding all of its
    loops, separated by MOVETO codes. Taking the vertices whole joins disjoint
    lobes into a single polygon with a false edge between them; splitting at
    each MOVETO keeps them apart and leaves single-loop rings unchanged.
    """
    rings = []
    for path in contour_set.get_paths():
        codes = path.codes
        starts = np.flatnonzero(codes == path.MOVETO) if codes is not None else np.array([0])
        for seg in np.split(path.vertices, starts[1:]):
            if len(seg) >= 4:
                rings.append(seg.tolist())
    return rings


def density_contours(lon, lat, levels=DEFAULT_LEVELS, grid: int = 80) -> list[dict]:
    """Contours enclosing the given fractions of estimated probability mass.

    Returns [] rather than raising when the cloud is too small or degenerate to
    estimate a density from: a handful of collinear particles has no meaningful
    contour, and drawing one anyway would be inventing precision.
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    if lon.size < MIN_PARTICLES or np.ptp(lon) < 1e-9 or np.ptp(lat) < 1e-9:
        return []

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import gaussian_kde

    pad_x = 0.15 * np.ptp(lon) + 1e-3
    pad_y = 0.15 * np.ptp(lat) + 1e-3
    xs = np.linspace(lon.min() - pad_x, lon.max() + pad_x, grid)
    ys = np.linspace(lat.min() - pad_y, lat.max() + pad_y, grid)
    X, Y = np.meshgrid(xs, ys)

    try:
        kde = gaussian_kde(np.vstack([lon, lat]))
        Z = kde(np.vstack([X.ravel(), Y.ravel()])).reshape(X.shape)
    except np.linalg.LinAlgError:
        return []          # singular covariance: the cloud is effectively 1-D

    # Sort densities descending; the level enclosing fraction f is the density
    # at which the cumulative mass first reaches f.
    flat = np.sort(Z.ravel())[::-1]
    cum = np.cumsum(flat)
    if cum[-1] <= 0:
        return []
    cum = cum / cum[-1]

    out = []
    fig, ax = plt.subplots()
    try:
        for frac in levels:
            thr = float(flat[min(int(np.searchsorted(cum, frac)), flat.size - 1)])
            cs = ax.contour(X, Y, Z, levels=[thr])
            out.append({"fraction": frac, "polygons": rings_of(cs)})
    finally:
        plt.close(fig)
    return out
