"""Artifact detection — blinks, jaw clenches, motion, bad sensor contact.

Per CLAUDE.md: artifacts must be flagged not silently swallowed. Dash surfaces
them so the user knows when F is unreliable.
"""
from __future__ import annotations

from enum import Flag, auto

import numpy as np

from nao.config import (
    BLINK_UV_THRESH,
    EEG_CHANNELS,
    JAW_HF_PER_CHANNEL_UV,
    JAW_MIN_CHANNELS,
    MOTION_ACCEL_G_THRESH,
    MOTION_GYRO_DPS_THRESH,
)


class Artifact(Flag):
    NONE = 0
    BLINK = auto()
    JAW = auto()
    MOTION = auto()
    BAD_CONTACT = auto()


_AF7 = EEG_CHANNELS.index("AF7")
_AF8 = EEG_CHANNELS.index("AF8")


def detect_artifacts(
    window: np.ndarray,
    accel_window: np.ndarray,
    gyro_window: np.ndarray | None = None,
) -> Artifact:
    """Examine a window and return flags.

    Args:
        window: shape (n_samples, n_channels) µV.
        accel_window: shape (n_samples, 3) g.
        gyro_window: shape (n_samples, 3) deg/s. Optional for callers that
            still emit Sample without gyro; when present, large angular
            velocity also raises MOTION (catches head turns where accel
            barely deviates from 1g).
    """
    flags = Artifact.NONE

    # Blink: sharp >150 µV deflection in frontal channels.
    frontal = window[:, [_AF7, _AF8]]
    if np.max(np.abs(frontal)) > BLINK_UV_THRESH:
        flags |= Artifact.BLINK

    # Jaw clench: HF static across ALL channels. Per-channel std-of-diff;
    # require >= JAW_MIN_CHANNELS channels above threshold so a single hot
    # sensor doesn't false-trip.
    per_chan_hf = np.std(np.diff(window, axis=0), axis=0)
    if (per_chan_hf > JAW_HF_PER_CHANNEL_UV).sum() >= JAW_MIN_CHANNELS:
        flags |= Artifact.JAW

    # Motion: accel magnitude departs from 1g (gravity).
    mag = np.linalg.norm(accel_window, axis=1)
    if float(np.max(np.abs(mag - 1.0))) > MOTION_ACCEL_G_THRESH:
        flags |= Artifact.MOTION

    # Motion (gyro path): large angular velocity in any axis = head turn.
    if gyro_window is not None and gyro_window.size:
        if float(np.max(np.abs(gyro_window))) > MOTION_GYRO_DPS_THRESH:
            flags |= Artifact.MOTION

    # Bad contact: flat line (near-zero variance) on any channel.
    chan_std = window.std(axis=0)
    if (chan_std < 0.5).any():
        flags |= Artifact.BAD_CONTACT

    # Or wild oscillation only on specific channels suggesting impedance issues.
    if (chan_std > 500).any():
        flags |= Artifact.BAD_CONTACT

    return flags


def is_clean(flags: Artifact) -> bool:
    """True if window is usable for downstream features."""
    return flags == Artifact.NONE
