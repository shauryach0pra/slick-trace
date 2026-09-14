"""Tversky loss direction.

The asymmetry is easy to invert, and a widely-copied implementation in this
problem statement's public field does invert it - documenting alpha=0.7,
beta=0.3 as recall optimisation when those values buy precision. These tests
pin the direction down with a numpy mirror, so they run whether or not torch is
installed on the machine checking them.
"""
import numpy as np
import pytest


def tversky_np(pred, truth, alpha, beta, eps=1e-6):
    """Mirror of tversky_loss for probabilities already in [0, 1]."""
    tp = (pred * truth).sum()
    fp = (pred * (1 - truth)).sum()
    fn = ((1 - pred) * truth).sum()
    return 1.0 - (tp + eps) / (tp + alpha * fp + beta * fn + eps)


def _masks():
    truth = np.zeros((32, 32)); truth[8:24, 8:24] = 1.0
    over = truth.copy(); over[6:26, 6:26] = 1.0        # false-positive heavy
    under = np.zeros((32, 32)); under[10:22, 10:22] = 1.0   # false-negative heavy
    return truth, over, under


def test_beta_greater_than_alpha_penalises_misses():
    """The configuration this project uses. Under-prediction must cost more."""
    truth, over, under = _masks()
    assert tversky_np(under, truth, 0.3, 0.7) > tversky_np(over, truth, 0.3, 0.7)


def test_alpha_greater_than_beta_penalises_false_alarms():
    """The inverted configuration, shown to do the opposite of what the
    widely-copied docstring claims."""
    truth, over, under = _masks()
    assert tversky_np(over, truth, 0.7, 0.3) > tversky_np(under, truth, 0.7, 0.3)


def test_equal_weights_reduce_to_dice_behaviour():
    truth, over, under = _masks()
    a = tversky_np(over, truth, 0.5, 0.5)
    b = tversky_np(under, truth, 0.5, 0.5)
    assert 0 < a < 1 and 0 < b < 1


def test_perfect_prediction_has_near_zero_loss():
    truth, _, _ = _masks()
    assert tversky_np(truth, truth, 0.3, 0.7) < 1e-5


def test_torch_implementation_matches_the_mirror():
    torch = pytest.importorskip("torch")
    from slicktrace_core.unet_model import tversky_loss
    truth, over, _ = _masks()
    logits = torch.logit(torch.tensor(over * 0.98 + 0.01), eps=1e-6)[None, None]
    t = torch.tensor(truth)[None, None]
    got = float(tversky_loss(logits, t, 0.3, 0.7))
    want = tversky_np(over * 0.98 + 0.01, truth, 0.3, 0.7)
    assert abs(got - want) < 1e-4


def test_project_default_is_recall_weighted():
    torch = pytest.importorskip("torch")
    import inspect
    from slicktrace_core.unet_model import tversky_loss
    sig = inspect.signature(tversky_loss)
    alpha = sig.parameters["alpha"].default
    beta = sig.parameters["beta"].default
    assert beta > alpha, "defaults must favour recall, not precision"
