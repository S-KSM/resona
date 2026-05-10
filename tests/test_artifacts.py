"""Artifact detector flag logic."""
from __future__ import annotations

import numpy as np

from nao.config import EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.process.artifacts import Artifact, detect_artifacts, is_clean


def _quiet_window(noise_uv: float = 5.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((SAMPLE_RATE_HZ, len(EEG_CHANNELS))) * noise_uv


def _still_accel() -> np.ndarray:
    return np.tile([0.0, 0.0, 1.0], (SAMPLE_RATE_HZ, 1)).astype(float)


def test_clean_window_no_flags() -> None:
    flags = detect_artifacts(_quiet_window(), _still_accel())
    assert is_clean(flags), flags


def test_blink_flagged() -> None:
    w = _quiet_window()
    af7 = EEG_CHANNELS.index("AF7")
    w[100, af7] = 300.0  # spike beyond BLINK_UV_THRESH
    flags = detect_artifacts(w, _still_accel())
    assert Artifact.BLINK in flags


def test_motion_flagged() -> None:
    w = _quiet_window()
    accel = _still_accel()
    accel[50:60] += np.array([0.5, 0.5, 0.0])  # head jolt
    flags = detect_artifacts(w, accel)
    assert Artifact.MOTION in flags


def test_bad_contact_flat_line() -> None:
    w = _quiet_window()
    w[:, 0] = 0.0  # TP9 disconnected
    flags = detect_artifacts(w, _still_accel())
    assert Artifact.BAD_CONTACT in flags
