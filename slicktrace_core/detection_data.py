"""
Synthetic *detection*-stage dataset generator.

Produces (scene, mask, label) samples in three classes, mirroring the
masterplan's real-detection design (p.7, p.9):
  - "oil":       a genuine dark slick patch  -> mask has a positive region
  - "clean":     open water, no slick        -> mask all zero
  - "lookalike": a dark patch NOT caused by oil (e.g. a low-wind/biogenic
                 slick-like feature) -> mask all zero, even though a naive
                 threshold detector would flag it. This is the
                 "Part II negatives" idea: look-alike masks are zero-valued
                 oil masks, not outlines of the look-alike itself.

This is independent from `synth_generator.py` (which builds a full
attribution-ready *incident*, with tracks + forcing). This module only
produces scene/mask pairs for training and evaluating the detector.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation


@dataclass
class DetectionSample:
    sample_id: str
    kind: str  # "oil" | "clean" | "lookalike"
    image_path: str
    mask_path: str


def _speckled_sea(img_size: int, rng: np.random.Generator) -> np.ndarray:
    return rng.gamma(shape=4.0, scale=0.25, size=(img_size, img_size))


def _random_blob_mask(img_size: int, rng: np.random.Generator,
                       min_r=15, max_r=45, elongate=True) -> np.ndarray:
    cx, cy = rng.integers(40, img_size - 40, size=2)
    r = rng.integers(min_r, max_r)
    yy, xx = np.mgrid[0:img_size, 0:img_size]
    if elongate and rng.random() < 0.6:
        theta = rng.uniform(0, np.pi)
        stretch = rng.uniform(1.5, 3.0)
        xr = (xx - cx) * np.cos(theta) + (yy - cy) * np.sin(theta)
        yr = -(xx - cx) * np.sin(theta) + (yy - cy) * np.cos(theta)
        dist = (xr / (r * stretch)) ** 2 + (yr / r) ** 2
    else:
        dist = ((xx - cx) ** 2 + (yy - cy) ** 2) / r ** 2
    blob = (dist < 1.0).astype(float)
    blob = gaussian_filter(blob, sigma=2)
    return (blob > blob.max() * 0.4).astype(np.uint8) if blob.max() > 0 else blob.astype(np.uint8)


def make_sample(kind: str, sample_id: str, out_dir: str, img_size: int,
                 rng: np.random.Generator) -> DetectionSample:
    scene = _speckled_sea(img_size, rng)
    mask = np.zeros((img_size, img_size), dtype=np.uint8)

    if kind == "oil":
        blob = _random_blob_mask(img_size, rng)
        scene[blob == 1] *= rng.uniform(0.25, 0.45)  # strong, consistent dampening
        mask = blob
    elif kind == "lookalike":
        blob = _random_blob_mask(img_size, rng, min_r=10, max_r=35)
        # look-alikes dampen backscatter too (that's *why* they're confusable)
        # but more weakly/patchily than real oil, and mask stays empty
        patchy = blob * (rng.random(blob.shape) > 0.3)
        scene[patchy == 1] *= rng.uniform(0.55, 0.75)
        mask[:] = 0
    elif kind == "clean":
        pass
    else:
        raise ValueError(kind)

    scene = np.clip(scene, 0, None)
    scene_img = (255 * (scene / scene.max())).astype(np.uint8)

    img_path = os.path.join(out_dir, f"{sample_id}_scene.png")
    mask_path = os.path.join(out_dir, f"{sample_id}_mask.png")
    Image.fromarray(scene_img, mode="L").save(img_path)
    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(mask_path)
    return DetectionSample(sample_id, kind, img_path, mask_path)


def build_dataset(out_dir: str = "data/detection", n_oil=60, n_clean=30,
                   n_lookalike=30, img_size: int = 128, seed: int = 7,
                   split: str = "train") -> list[DetectionSample]:
    rng = np.random.default_rng(seed)
    split_dir = os.path.join(out_dir, split)
    os.makedirs(split_dir, exist_ok=True)
    samples = []
    counts = {"oil": n_oil, "clean": n_clean, "lookalike": n_lookalike}
    for kind, n in counts.items():
        for i in range(n):
            sid = f"{split}_{kind}_{i:04d}"
            samples.append(make_sample(kind, sid, split_dir, img_size, rng))
    return samples


# Split seeds are fixed and distinct so the three splits never share a sample.
# The TEST split is locked: it is generated once and is not consulted during
# development. Reporting a tuned number on it would make it a validation set
# wearing a test set's name.
SPLIT_SPEC = {
    "train": {"n_oil": 60, "n_clean": 30, "n_lookalike": 30, "seed": 7},
    "val": {"n_oil": 15, "n_clean": 8, "n_lookalike": 8, "seed": 99},
    "test": {"n_oil": 20, "n_clean": 12, "n_lookalike": 12, "seed": 31337},
}


def build_all(out_dir: str = "data/detection") -> dict[str, list[DetectionSample]]:
    return {split: build_dataset(out_dir=out_dir, split=split, **spec)
            for split, spec in SPLIT_SPEC.items()}


if __name__ == "__main__":
    from collections import Counter
    splits = build_all()
    for name, samples in splits.items():
        breakdown = dict(Counter(s.kind for s in samples))
        lock = "  [LOCKED — not used for development]" if name == "test" else ""
        print(f"{name:6s}: {len(samples):3d} samples  {breakdown}{lock}")
    print("\n-> data/detection/")
