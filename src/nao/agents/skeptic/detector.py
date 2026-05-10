"""Frontal-gamma extraction.

Reward / "aha" signals show up most clearly in frontal gamma (30–45 Hz over
AF7/AF8). Mirrors `agents.gatekeeper.frontal` — pure functions, no I/O.
"""
from __future__ import annotations

from typing import Sequence

from nao.config import EEG_CHANNELS
from nao.process.frame import FocusFrame

_AF7 = EEG_CHANNELS.index("AF7")  # 1
_AF8 = EEG_CHANNELS.index("AF8")  # 2


def frontal_gamma_from_powers(gamma_per_channel: Sequence[float] | None) -> float | None:
    """Mean of AF7 + AF8 gamma power, or None if data missing."""
    if gamma_per_channel is None or len(gamma_per_channel) <= _AF8:
        return None
    return (float(gamma_per_channel[_AF7]) + float(gamma_per_channel[_AF8])) / 2.0


def frontal_gamma(frame: FocusFrame) -> float | None:
    """Frontal gamma power for a FocusFrame.

    Falls back to the channel-averaged `frame.gamma` when per-channel data is
    absent — that loses spatial specificity but lets the detector still run on
    older/synthetic frames.
    """
    if frame.gamma_per_channel is not None:
        v = frontal_gamma_from_powers(frame.gamma_per_channel)
        if v is not None:
            return v
    return float(frame.gamma)
