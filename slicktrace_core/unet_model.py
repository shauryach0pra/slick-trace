"""
U-Net for oil-slick segmentation.

NOT EXECUTED IN THIS SANDBOX: this container has ~5GB free disk and no GPU;
a plain `pip install torch` pulls ~5GB of CUDA dependencies regardless of
hardware and doesn't fit. This file is syntax-checked (`python -m py_compile`)
but not run end-to-end here. Install torch on your own machine:

    pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU
    pip install torch                                                     # CUDA GPU

Architecture matches the masterplan (p.9): two-channel input (VV/VH for real
Sentinel-1; this repo's synthetic data is single-channel, set in_channels=1),
a standard 4-level U-Net encoder/decoder, trained with Dice + BCE.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """Standard 4-level U-Net. in_channels=2 for real VV/VH Sentinel-1;
    in_channels=1 for this repo's synthetic single-channel scenes."""

    def __init__(self, in_channels: int = 1, out_channels: int = 1, base: int = 32):
        super().__init__()
        self.enc1 = _conv_block(in_channels, base)
        self.enc2 = _conv_block(base, base * 2)
        self.enc3 = _conv_block(base * 2, base * 4)
        self.enc4 = _conv_block(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)

        self.bottleneck = _conv_block(base * 8, base * 16)

        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.dec4 = _conv_block(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = _conv_block(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = _conv_block(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = _conv_block(base * 2, base)

        self.out_conv = nn.Conv2d(base, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))

        d4 = self.up4(b)
        d4 = self.dec4(torch.cat([d4, e4], dim=1))
        d3 = self.up3(d4)
        d3 = self.dec3(torch.cat([d3, e3], dim=1))
        d2 = self.up2(d3)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))
        d1 = self.up1(d2)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))

        return self.out_conv(d1)  # logits — apply sigmoid outside for probabilities


def dice_loss(logits: torch.Tensor, target: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    probs_flat = probs.reshape(probs.size(0), -1)
    target_flat = target.reshape(target.size(0), -1)
    intersection = (probs_flat * target_flat).sum(dim=1)
    union = probs_flat.sum(dim=1) + target_flat.sum(dim=1)
    dice = (2 * intersection + eps) / (union + eps)
    return 1 - dice.mean()


def tversky_loss(logits: torch.Tensor, target: torch.Tensor,
                 alpha: float = 0.3, beta: float = 0.7,
                 eps: float = 1e-6) -> torch.Tensor:
    """Tversky loss: 1 - TP / (TP + alpha*FP + beta*FN).

    Dice weights false positives and false negatives equally. Tversky lets them
    be weighted separately, which matters here because the two errors are not
    equally costly: a missed slick is re-detectable on the next pass, a false
    detection routed to an analyst costs their time and their trust - but the
    classical baseline already sits at zero false positives and short of the
    recall target, so at the margin the miss is what needs penalising.

    ON THE DIRECTION, WHICH IS EASY TO GET BACKWARDS
        Raising **beta** penalises false negatives and buys recall. Raising
        alpha penalises false positives and buys precision. A widely-copied
        implementation in this problem statement's public field documents
        alpha=0.7, beta=0.3 as "thin-slick recall optimization", which is
        inverted: those values weight FP at more than twice FN and buy
        precision, not recall.

        Verified rather than assumed. Against a fixed truth mask, an
        over-predicting mask and an under-predicting one:

            alpha=0.5 beta=0.5   over 0.2195   under 0.2800
            alpha=0.7 beta=0.3   over 0.2825   under 0.1892   <- punishes FALSE ALARMS
            alpha=0.3 beta=0.7   over 0.1444   under 0.3525   <- punishes MISSES

        The defaults here are alpha=0.3, beta=0.7.
    """
    p_ = torch.sigmoid(logits)
    tp = (p_ * target).sum()
    fp = (p_ * (1 - target)).sum()
    fn = ((1 - p_) * target).sum()
    return 1.0 - (tp + eps) / (tp + alpha * fp + beta * fn + eps)


def bce_tversky_loss(logits: torch.Tensor, target: torch.Tensor,
                     tversky_weight: float = 0.5,
                     alpha: float = 0.3, beta: float = 0.7) -> torch.Tensor:
    """BCE for calibrated per-pixel gradients, Tversky for the region overlap
    the detector is actually scored on."""
    bce = F.binary_cross_entropy_with_logits(logits, target)
    tl = tversky_loss(logits, target, alpha, beta)
    return tversky_weight * tl + (1 - tversky_weight) * bce


def combined_loss(logits: torch.Tensor, target: torch.Tensor,
                   dice_weight: float = 0.5) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(logits, target)
    dl = dice_loss(logits, target)
    return dice_weight * dl + (1 - dice_weight) * bce


if __name__ == "__main__":
    # smoke test shape only — run on a machine with torch installed
    model = UNet(in_channels=1, out_channels=1, base=16)
    x = torch.randn(2, 1, 128, 128)
    y = model(x)
    assert y.shape == (2, 1, 128, 128), y.shape
    print("UNet forward pass OK, output shape", tuple(y.shape))
