"""Band-power feature extraction using Welch's method.

Welch (averaged periodograms over overlapping segments) gives lower-variance
power estimates than a raw FFT — preferred for jittery EEG. Numerics in
SciPy/NumPy keep us off MNE's hot path; MNE is reserved for filtering.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import welch

from nao.config import BANDS_HZ, SAMPLE_RATE_HZ


def band_power(
    window: np.ndarray,
    fs: int = SAMPLE_RATE_HZ,
    bands: dict[str, tuple[float, float]] | None = None,
) -> dict[str, np.ndarray]:
    """Per-channel power per band.

    Args:
        window: shape (n_samples, n_channels), float µV.
        fs: sample rate.
        bands: name -> (low, high) Hz. Defaults to config.BANDS_HZ.

    Returns:
        dict band_name -> np.ndarray shape (n_channels,) of mean PSD in band.
    """
    if bands is None:
        bands = BANDS_HZ
    if window.ndim != 2:
        raise ValueError(f"window must be 2D, got shape {window.shape}")
    nperseg = min(len(window), fs)  # 1s segment if available
    freqs, psd = welch(window, fs=fs, nperseg=nperseg, axis=0)
    out: dict[str, np.ndarray] = {}
    for name, (lo, hi) in bands.items():
        mask = (freqs >= lo) & (freqs < hi)
        out[name] = psd[mask].mean(axis=0) if mask.any() else np.zeros(window.shape[1])
    return out
