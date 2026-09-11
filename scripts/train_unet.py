"""
Train the U-Net on data/detection/{train,val}.

NOT RUN IN THIS SANDBOX (see varuna_core/unet_model.py header — no torch
here). On your own machine:

    pip install torch --index-url https://download.pytorch.org/whl/cpu
    python3 -m varuna_core.detection_data      # regenerate data if needed
    python3 scripts/train_unet.py --epochs 15

Trains on the *same* synthetic oil/clean/lookalike dataset the classical
baseline was scored on (varuna_core.baseline_detector), so IoU/FP numbers
are directly comparable — that comparison is the actual deliverable, not
the absolute IoU value.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from varuna_core.unet_model import UNet, combined_loss


class DetectionDataset(Dataset):
    def __init__(self, split_dir: str):
        self.scene_paths = sorted(glob.glob(os.path.join(split_dir, "*_scene.png")))

    def __len__(self):
        return len(self.scene_paths)

    def __getitem__(self, idx):
        sp = self.scene_paths[idx]
        base = sp[: -len("_scene.png")]
        scene = np.array(Image.open(sp), dtype=np.float32) / 255.0
        mask = (np.array(Image.open(base + "_mask.png"), dtype=np.float32) > 127).astype(np.float32)
        return torch.from_numpy(scene).unsqueeze(0), torch.from_numpy(mask).unsqueeze(0)


def iou_from_logits(logits: torch.Tensor, target: torch.Tensor, thresh: float = 0.5) -> float:
    pred = (torch.sigmoid(logits) > thresh).float()
    inter = (pred * target).sum().item()
    union = ((pred + target) > 0).float().sum().item()
    return inter / union if union > 0 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-dir", default="data/detection/train")
    ap.add_argument("--val-dir", default="data/detection/val")
    ap.add_argument("--checkpoint", default="data/detection/unet.pt")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    train_ds = DetectionDataset(args.train_dir)
    val_ds = DetectionDataset(args.val_dir)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    model = UNet(in_channels=1, out_channels=1, base=32).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = combined_loss(logits, y)
            loss.backward()
            opt.step()
            train_loss += loss.item() * x.size(0)
        train_loss /= len(train_ds)

        model.eval()
        val_ious = []
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                for i in range(x.size(0)):
                    val_ious.append(iou_from_logits(logits[i], y[i]))
        print(f"epoch {epoch+1}/{args.epochs}  train_loss={train_loss:.4f}  "
              f"val_iou={np.mean(val_ious):.4f}")

    torch.save(model.state_dict(), args.checkpoint)
    print(f"Saved checkpoint to {args.checkpoint}")


if __name__ == "__main__":
    main()
