"""Focus Coefficient: F = β / α.

High β with low α -> engaged/focused cognition.
EMA smoother avoids dash jitter; α=0.3 default per PLAN.md.
"""
from __future__ import annotations

import numpy as np

from nao.config import FOCUS_EMA_ALPHA


def focus_coef(alpha_power: np.ndarray | float, beta_power: np.ndarray | float) -> float:
    """Per-window scalar F. Averages across channels if arrays passed.

    Guards divide-by-zero with a tiny epsilon — α≈0 means flat-line / bad contact
    rather than infinite focus.
    """
    a = float(np.mean(alpha_power))
    b = float(np.mean(beta_power))
    return b / (a + 1e-9)


class FocusEMA:
    """Exponential moving average over Focus values."""

    def __init__(self, alpha: float = FOCUS_EMA_ALPHA) -> None:
        self.alpha = alpha
        self._value: float | None = None

    def update(self, x: float) -> float:
        if self._value is None:
            self._value = x
        else:
            self._value = self.alpha * x + (1 - self.alpha) * self._value
        return self._value

    @property
    def value(self) -> float | None:
        return self._value
