"""The shipped U-Net checkpoint loads and still performs.

Only five of the forty-two public repositories on this problem statement ship
trained weights, and a checkpoint nobody can load is worse than none: it implies
a capability that does not survive a clone. These tests fail the build if the
file goes missing, stops matching the architecture, or quietly degrades.

They skip rather than fail where torch is absent, because torch is deliberately
not in `requirements.lock` - the runtime image runs the classical detector and
does not need a deep learning framework. CI installs it separately.
"""
import json
import os

import pytest

CKPT = "data/detection/unet.pt"
EVAL = "data/detection/unet_eval.json"


def test_checkpoint_is_present():
    """Fails loudly if the file is dropped from a commit, rather than letting
    the pipeline fall back to the classical detector unannounced."""
    assert os.path.exists(CKPT), f"{CKPT} missing from the repository"


def test_recorded_evaluation_is_present_and_complete():
    assert os.path.exists(EVAL)
    d = json.load(open(EVAL))
    for split in ("val", "test"):
        m = d[split]
        for k in ("iou_on_oil", "recall_on_oil", "precision_on_oil",
                  "false_positive_rate_lookalike", "false_positive_rate_clean"):
            assert m.get(k) is not None, f"{split}.{k} missing"


def test_recorded_test_performance_has_not_silently_regressed():
    """Guards the claim in the validation report. If a retrain lands with worse
    numbers, that is a decision to make deliberately, not to discover later."""
    m = json.load(open(EVAL))["test"]
    assert m["iou_on_oil"] >= 0.90, f"test IoU fell to {m['iou_on_oil']}"
    assert m["recall_on_oil"] >= 0.90, f"test recall fell to {m['recall_on_oil']}"
    assert m["false_positive_rate_lookalike"] == 0.0
    assert m["false_positive_rate_clean"] == 0.0


def test_recall_exceeds_precision_as_the_loss_intends():
    """Tversky at alpha=0.3, beta=0.7 penalises a missed pixel more than a false
    one. If precision ever overtakes recall, the loss weighting has been changed
    or inverted."""
    m = json.load(open(EVAL))["test"]
    assert m["recall_on_oil"] > m["precision_on_oil"]


def test_checkpoint_loads_into_the_architecture():
    torch = pytest.importorskip("torch")
    from slicktrace_core.unet_model import UNet
    state = torch.load(CKPT, map_location="cpu")
    base = int(state["enc1.0.weight"].shape[0])
    model = UNet(in_channels=1, out_channels=1, base=base)
    model.load_state_dict(state)
    model.eval()
    out = model(torch.zeros(1, 1, 128, 128))
    assert out.shape == (1, 1, 128, 128)


def test_checkpoint_width_matches_the_recorded_evaluation():
    """The evaluation must have been produced by this checkpoint, not an
    earlier one left behind."""
    torch = pytest.importorskip("torch")
    state = torch.load(CKPT, map_location="cpu")
    assert json.load(open(EVAL))["checkpoint"].endswith("unet.pt")
    assert int(state["enc1.0.weight"].shape[0]) in (16, 32, 64)
