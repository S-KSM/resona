"""F = β / α arithmetic + EMA behavior."""
from __future__ import annotations

import numpy as np
import pytest

from nao.process.focus import FocusEMA, focus_coef


def test_focus_basic_ratio() -> None:
    assert focus_coef(1.0, 2.0) == pytest.approx(2.0)
    assert focus_coef(2.0, 1.0) == pytest.approx(0.5)


def test_focus_array_inputs_average() -> None:
    a = np.array([1.0, 1.0, 1.0, 1.0])
    b = np.array([2.0, 2.0, 2.0, 2.0])
    assert focus_coef(a, b) == pytest.approx(2.0)


def test_focus_zero_alpha_no_inf() -> None:
    # α near zero -> very large but finite (epsilon guard).
    f = focus_coef(0.0, 1.0)
    assert np.isfinite(f)
    assert f > 1e6


def test_ema_first_update_returns_input() -> None:
    ema = FocusEMA(alpha=0.3)
    assert ema.update(5.0) == 5.0


def test_ema_smooths_step() -> None:
    ema = FocusEMA(alpha=0.5)
    ema.update(0.0)
    v = ema.update(1.0)
    assert v == pytest.approx(0.5)
    v = ema.update(1.0)
    assert v == pytest.approx(0.75)
