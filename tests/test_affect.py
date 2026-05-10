"""Affect axes — frontal alpha asymmetry + arousal index."""
from __future__ import annotations

import math

import pytest

from nao.config import EEG_CHANNELS
from nao.process.affect import arousal_index, frontal_asymmetry


def _alpha_pc(tp9: float = 1.0, af7: float = 1.0, af8: float = 1.0, tp10: float = 1.0) -> list[float]:
    """Per-channel alpha matching nao.config.EEG_CHANNELS order."""
    assert EEG_CHANNELS == ("TP9", "AF7", "AF8", "TP10")
    return [tp9, af7, af8, tp10]


def test_asymmetry_zero_when_balanced() -> None:
    assert frontal_asymmetry(_alpha_pc(af7=2.0, af8=2.0)) == pytest.approx(0.0)


def test_asymmetry_positive_when_right_alpha_higher() -> None:
    # AF8 (right) higher → log(α_AF8) − log(α_AF7) > 0 → approach/positive valence.
    v = frontal_asymmetry(_alpha_pc(af7=1.0, af8=math.e))
    assert v == pytest.approx(1.0)


def test_asymmetry_negative_when_left_alpha_higher() -> None:
    v = frontal_asymmetry(_alpha_pc(af7=math.e, af8=1.0))
    assert v == pytest.approx(-1.0)


def test_asymmetry_none_on_missing_or_zero() -> None:
    assert frontal_asymmetry(None) is None
    assert frontal_asymmetry([]) is None
    assert frontal_asymmetry([1.0, 0.0, 1.0, 1.0]) is None  # AF7 zero
    assert frontal_asymmetry([1.0, 1.0, -0.5, 1.0]) is None  # AF8 negative


def test_asymmetry_handles_short_per_channel_list() -> None:
    # If the upstream changes channel count, don't crash — just return None.
    assert frontal_asymmetry([1.0]) is None


def test_arousal_index_basic() -> None:
    # alpha=1, beta=2, gamma=1 → (2+1)/1 = 3.
    assert arousal_index(alpha=1.0, beta=2.0, gamma=1.0) == pytest.approx(3.0)


def test_arousal_index_calm_low() -> None:
    # High alpha, low beta+gamma → low arousal.
    v = arousal_index(alpha=4.0, beta=0.5, gamma=0.5)
    assert v == pytest.approx(0.25)


def test_arousal_none_on_zero_alpha() -> None:
    assert arousal_index(alpha=0.0, beta=1.0, gamma=1.0) is None
    assert arousal_index(alpha=-0.1, beta=1.0, gamma=1.0) is None


def test_arousal_none_on_nonfinite() -> None:
    assert arousal_index(alpha=float("nan"), beta=1.0, gamma=1.0) is None
    assert arousal_index(alpha=1.0, beta=float("inf"), gamma=1.0) is None
