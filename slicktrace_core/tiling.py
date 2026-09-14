"""
Tiled inference over scenes too large to process in one pass.

A Sentinel-1 GRD product is roughly 25,000 x 16,000 pixels. Nothing in this
pipeline can hold that as a single array, so real imagery has to be processed in
tiles - and the moment it is, the seams become the problem.

WHY OVERLAP ALONE IS NOT ENOUGH
    Tile the scene without overlap and a slick crossing a boundary is cut in
    two: the connected-component stage then sees two regions where there is one,
    each smaller than the other, and the minimum-region filter may discard both.
    Overlap the tiles and the same pixel is decided twice, which is worse in a
    different way - the two decisions can disagree, and taking either one
    produces a visible step at the join.

    The fix is to let tiles vote with a weight that falls to zero at their own
    edges, so a pixel near a tile boundary is decided mostly by the tile that
    holds it comfortably inside. A cosine taper does this smoothly; the weights
    sum to a constant across the interior, so the result is a weighted average
    rather than a patchwork.

WHAT THIS DOES NOT DO
    It does not make a small scene more accurate. On anything that fits in one
    tile the output is identical to processing it whole, which is the property
    the tests pin down. This is machinery for real imagery, not a change to the
    current results.
"""
from __future__ import annotations

import numpy as np


def _cosine_taper(h: int, w: int, edge: int) -> np.ndarray:
    """Weight surface: 1.0 in the interior, falling smoothly to ~0 at the edges.

    A raised-cosine ramp rather than a linear one: linear ramps sum to a
    constant too, but their derivative is discontinuous at the ramp ends, which
    shows up as a faint line at exactly the place tiling was meant to hide.
    """
    def ramp(n: int) -> np.ndarray:
        v = np.ones(n)
        e = min(edge, n // 2)
        if e > 0:
            t = (np.arange(e) + 0.5) / e
            taper = 0.5 * (1 - np.cos(np.pi * t))
            v[:e] = taper
            v[-e:] = taper[::-1]
        return v
    return np.outer(ramp(h), ramp(w))


def tiled_predict(scene: np.ndarray, predict_fn, tile: int = 512,
                  overlap: int = 64, threshold: float = 0.5) -> dict:
    """Run `predict_fn` over overlapping tiles and blend the results.

    Returns the blended binary mask plus the tiling that produced it, so a
    reader can tell whether a result came from one pass or ninety.
    """
    h, w = scene.shape
    if tile <= 0 or overlap < 0 or overlap >= tile:
        raise ValueError("need 0 <= overlap < tile")

    # A scene that fits in one tile is processed whole: tiling it would add a
    # blend step with nothing to blend, and the identity is worth preserving.
    if h <= tile and w <= tile:
        return {
            "mask": predict_fn(scene).astype(np.uint8),
            "n_tiles": 1,
            "tiled": False,
            "note": "scene fits in a single tile; processed whole, no blending applied",
        }

    step = tile - overlap
    acc = np.zeros((h, w), dtype=float)
    wsum = np.zeros((h, w), dtype=float)
    n_tiles = 0

    for y0 in range(0, max(h - overlap, 1), step):
        for x0 in range(0, max(w - overlap, 1), step):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            y0c, x0c = max(y1 - tile, 0), max(x1 - tile, 0)
            sub = scene[y0c:y1, x0c:x1]
            m = predict_fn(sub).astype(float)
            wt = _cosine_taper(*sub.shape, edge=overlap)
            acc[y0c:y1, x0c:x1] += m * wt
            wsum[y0c:y1, x0c:x1] += wt
            n_tiles += 1

    # Any pixel not covered by a tapered tile interior would divide by zero.
    # There should be none, and if there are, they are left unset rather than
    # filled with a guess.
    covered = wsum > 1e-9
    blended = np.zeros((h, w), dtype=float)
    blended[covered] = acc[covered] / wsum[covered]

    return {
        "mask": (blended >= threshold).astype(np.uint8),
        "n_tiles": n_tiles,
        "tiled": True,
        "tile_px": tile,
        "overlap_px": overlap,
        "vote_threshold": threshold,
        "uncovered_px": int((~covered).sum()),
        "note": ("overlapping tiles vote with a cosine taper that falls to zero at "
                 "each tile's own edge, so a pixel near a seam is decided mostly by "
                 "the tile that holds it well inside; a slick crossing a boundary "
                 "stays one region"),
    }
