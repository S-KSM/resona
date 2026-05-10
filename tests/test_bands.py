"""FFT correctness: a pure sinusoid at f Hz should dominate the band containing f."""
from __future__ import annotations

import numpy as np

from nao.config import BANDS_HZ, EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.process.bands import band_power


def _sinusoid(hz: float, n: int = SAMPLE_RATE_HZ, amp_uv: float = 30.0) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE_HZ
    sig = amp_uv * np.sin(2 * np.pi * hz * t)
    return np.tile(sig[:, None], (1, len(EEG_CHANNELS)))


def _expected_band(hz: float) -> str:
    for name, (lo, hi) in BANDS_HZ.items():
        if lo <= hz < hi:
            return name
    raise AssertionError(f"hz {hz} outside known bands")


def test_alpha_dominant_at_10hz() -> None:
    powers = band_power(_sinusoid(10.0))
    winner = max(powers, key=lambda b: float(np.mean(powers[b])))
    assert winner == "alpha", powers


def test_beta_dominant_at_20hz() -> None:
    powers = band_power(_sinusoid(20.0))
    winner = max(powers, key=lambda b: float(np.mean(powers[b])))
    assert winner == "beta", powers


def test_theta_dominant_at_6hz() -> None:
    powers = band_power(_sinusoid(6.0))
    winner = max(powers, key=lambda b: float(np.mean(powers[b])))
    assert winner == "theta", powers


def test_band_power_shape() -> None:
    powers = band_power(_sinusoid(10.0))
    for name, vals in powers.items():
        assert vals.shape == (len(EEG_CHANNELS),), f"{name}: {vals.shape}"


def test_silence_yields_low_power() -> None:
    silent = np.zeros((SAMPLE_RATE_HZ, len(EEG_CHANNELS)))
    powers = band_power(silent)
    for name, vals in powers.items():
        assert float(np.mean(vals)) < 1e-6, f"{name} non-zero on silence"


def test_expected_band_helper_consistent_with_config() -> None:
    # Sanity that test internals stay in sync with bands.
    assert _expected_band(10.0) == "alpha"
    assert _expected_band(20.0) == "beta"
