"""HRV + gyro_max — peak detection on synthetic PPG sinusoid."""
from __future__ import annotations

import numpy as np
import pytest

from nao.process.hrv import gyro_max, heart_rate_bpm, rmssd_ms


def _synthetic_ppg(bpm: float, seconds: float = 12.0, fs: float = 256.0) -> np.ndarray:
    """Sinusoid + noise approximating a clean PPG. Period = 60/bpm."""
    t = np.arange(int(seconds * fs)) / fs
    rate_hz = bpm / 60.0
    rng = np.random.default_rng(0)
    return np.sin(2 * np.pi * rate_hz * t) + 0.05 * rng.standard_normal(t.size)


def test_bpm_recovers_resting_rate() -> None:
    sig = _synthetic_ppg(bpm=72)
    bpm = heart_rate_bpm(sig, fs=256.0)
    assert bpm is not None
    assert 70 <= bpm <= 74


def test_bpm_recovers_higher_rate() -> None:
    sig = _synthetic_ppg(bpm=110)
    bpm = heart_rate_bpm(sig, fs=256.0)
    assert bpm is not None
    assert 107 <= bpm <= 113


def test_bpm_returns_none_on_flat_signal() -> None:
    sig = np.zeros(int(256 * 12))
    assert heart_rate_bpm(sig, fs=256.0) is None


def test_bpm_returns_none_on_short_signal() -> None:
    sig = _synthetic_ppg(bpm=72, seconds=0.5)
    assert heart_rate_bpm(sig, fs=256.0) is None


def test_bpm_rejects_out_of_range() -> None:
    # 5 Hz tone → would imply 300 bpm. Reject as noise.
    t = np.arange(int(12 * 256)) / 256.0
    sig = np.sin(2 * np.pi * 5.0 * t)
    bpm = heart_rate_bpm(sig, fs=256.0)
    # Either None (filtered out) or clamped within sanity.
    assert bpm is None or (35.0 <= bpm <= 200.0)


def test_rmssd_constant_ibis_is_near_zero() -> None:
    # Pure 72 bpm sinusoid → IBIs near constant → RMSSD tiny.
    sig = _synthetic_ppg(bpm=72)
    rmssd = rmssd_ms(sig, fs=256.0)
    assert rmssd is not None
    assert rmssd < 30.0  # ms


def test_rmssd_none_when_too_short() -> None:
    sig = _synthetic_ppg(bpm=72, seconds=2.0)
    assert rmssd_ms(sig, fs=256.0) is None


def test_gyro_max_basic() -> None:
    g = np.zeros((100, 3))
    g[42, 1] = -75.0  # one big y-axis spike
    assert gyro_max(g) == pytest.approx(75.0)


def test_gyro_max_empty_window() -> None:
    assert gyro_max(np.array([])) == 0.0
