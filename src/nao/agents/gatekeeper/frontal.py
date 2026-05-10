"""Frontal-channel focus coefficient.

The headline F = β/α is a 4-channel mean (TP9, AF7, AF8, TP10). For
attention-gating the *frontal* pair (AF7, AF8) is more diagnostic:
prefrontal beta tracks executive engagement closely, whereas the temporal
pair picks up auditory / motor activity.

Pipeline now precomputes frontal F and writes it to `FocusFrame.frontal_focus`
(plus an EMA-smoothed `frontal_focus_ema`); `frontal_focus(frame)` simply
returns that field, falling back to a per-channel re-computation for old
frames that don't carry it. Pure functions — no I/O, no globals.
"""
from __future__ import annotations

import logging
from typing import Sequence

from nao.config import EEG_CHANNELS
from nao.process.frame import FocusFrame

log = logging.getLogger(__name__)

_AF7 = EEG_CHANNELS.index("AF7")  # 1
_AF8 = EEG_CHANNELS.index("AF8")  # 2

# Match focus.focus_coef's eps so frontal_focus is consistent with the headline F.
_EPS = 1e-6


def frontal_focus_from_powers(
    alpha_per_channel: Sequence[float] | None,
    beta_per_channel: Sequence[float] | None,
) -> float | None:
    """Pure math: mean frontal β/α from per-channel band powers."""
    if alpha_per_channel is None or beta_per_channel is None:
        return None
    if len(alpha_per_channel) <= _AF8 or len(beta_per_channel) <= _AF8:
        return None
    fa = (float(alpha_per_channel[_AF7]) + float(alpha_per_channel[_AF8])) / 2.0
    fb = (float(beta_per_channel[_AF7]) + float(beta_per_channel[_AF8])) / 2.0
    return fb / max(fa, _EPS)


def frontal_focus(frame: FocusFrame) -> float | None:
    """Return mean frontal β/α from a FocusFrame, or None if data is absent.

    Prefers the precomputed `frame.frontal_focus` field (set by Pipeline);
    falls back to recomputing from `alpha_per_channel` / `beta_per_channel`
    so old serialized frames and synthetic test frames still work.
    """
    if frame.frontal_focus is not None:
        return frame.frontal_focus
    return frontal_focus_from_powers(frame.alpha_per_channel, frame.beta_per_channel)
