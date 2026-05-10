"""Affect axes: continuous valence + arousal proxies derived from band power.

Honest scope: 4 dry electrodes (TP9, AF7, AF8, TP10) cannot classify discrete
emotions. We surface two continuous axes that the literature treats as
robust on consumer EEG:

- frontal_asymmetry — Davidson's frontal alpha asymmetry. Greater LEFT-frontal
  alpha than RIGHT correlates with approach motivation / positive valence;
  greater right-frontal alpha with withdrawal / negative affect. Sign convention
  here:    `log(α_AF8) − log(α_AF7)`. Positive → more right alpha → more left
  cortex active → approach/positive valence. Range typically [-2, 2].

- arousal_index — `(β + γ) / α`. High β + high γ + low α is the activated /
  alert / aroused signature; high α with low β/γ is calm. Crude but defensible.

Both return None when inputs are missing or not finite; callers must treat
that as "no signal this window" not zero.

Channel order (matches `nao.config.EEG_CHANNELS` and FocusFrame's
*_per_channel lists): TP9 (0), AF7 (1), AF8 (2), TP10 (3).
"""
from __future__ import annotations

import math

from nao.config import EEG_CHANNELS

AF7_IDX = EEG_CHANNELS.index("AF7")
AF8_IDX = EEG_CHANNELS.index("AF8")


def frontal_asymmetry(alpha_per_channel: list[float] | None) -> float | None:
    """Davidson frontal alpha asymmetry. Positive = approach/positive valence.

    Returns None if AF7 or AF8 alpha power is missing or non-positive (log of
    zero/negative is undefined).
    """
    if alpha_per_channel is None:
        return None
    if len(alpha_per_channel) <= max(AF7_IDX, AF8_IDX):
        return None
    a_left = alpha_per_channel[AF7_IDX]
    a_right = alpha_per_channel[AF8_IDX]
    if not (a_left > 0 and a_right > 0):
        return None
    if not (math.isfinite(a_left) and math.isfinite(a_right)):
        return None
    return math.log(a_right) - math.log(a_left)


def arousal_index(alpha: float, beta: float, gamma: float) -> float | None:
    """Simple arousal proxy: (β + γ) / α, channel-averaged powers.

    Returns None if α is non-positive or any input is non-finite.
    """
    if not (math.isfinite(alpha) and math.isfinite(beta) and math.isfinite(gamma)):
        return None
    if alpha <= 0:
        return None
    return (beta + gamma) / alpha
