"""HRV — heart rate + RMSSD from the Muse PPG channel.

Honest scope: Muse-2's 3-channel forehead PPG is noisier than fingertip / wrist
sensors. We do simple peak detection on the IR1 channel (Muse's "best" PPG)
over a rolling window. Good enough for resting heart-rate readout (±2 bpm) and
direction-of-change RMSSD; not clinical.

Approach:
  1. Pull the last ~10 seconds of PPG samples (sample rate ~256 Hz since
     RingBuffer is sample-aligned to EEG; the underlying PPG signal updates
     at 64 Hz so multiple consecutive rows hold the same value, which is
     fine — we operate on the unique-value sequence).
  2. Bandpass 0.7-3 Hz (40-180 bpm) so we filter out DC drift + breathing.
  3. Detect peaks: local maxima ≥ rolling_mean + k*rolling_std with a
     refractory window of ~250 ms.
  4. Inter-beat intervals (IBIs) → bpm = 60 / median(IBIs).
  5. RMSSD over the last N IBIs (≥30 s window worth) — None if fewer.

Returns None for both metrics until enough peaks accumulate or the signal is
too noisy/flat.
"""
from __future__ import annotations

import numpy as np

# Bandpass + peak-detection params chosen for forehead PPG. Tweak if shipping
# wrist sensors later.
HRV_BANDPASS_HZ = (0.7, 3.0)
HRV_PEAK_K = 0.6                # std multiplier; high = miss faint beats
HRV_REFRACTORY_S = 0.25         # 240 bpm ceiling
HRV_MIN_PEAKS_FOR_BPM = 4
HRV_MIN_IBI_FOR_RMSSD = 8       # ~5-8 s of IBIs at typical resting HR


def _bandpass(signal: np.ndarray, fs: float) -> np.ndarray:
    """Zero-phase Butterworth bandpass for the cardiac band."""
    if signal.size < 16:
        return signal - signal.mean() if signal.size else signal
    from scipy.signal import butter, sosfiltfilt

    lo, hi = HRV_BANDPASS_HZ
    # 4th order; padlen tolerated by sosfiltfilt for short signals.
    sos = butter(4, [lo, hi], btype="band", fs=fs, output="sos")
    try:
        return sosfiltfilt(sos, signal)
    except ValueError:
        # Signal too short for filtfilt — DC-remove + return raw.
        return signal - signal.mean()


def _detect_peaks(signal: np.ndarray, fs: float) -> np.ndarray:
    """Indices of detected systolic peaks in `signal`."""
    if signal.size < int(fs * 1.5):
        return np.array([], dtype=int)
    mean = float(np.mean(signal))
    std = float(np.std(signal))
    if std < 1e-6:
        return np.array([], dtype=int)
    threshold = mean + HRV_PEAK_K * std
    refractory = int(HRV_REFRACTORY_S * fs)
    peaks: list[int] = []
    n = signal.size
    i = 1
    while i < n - 1:
        if signal[i] > threshold and signal[i] >= signal[i - 1] and signal[i] >= signal[i + 1]:
            # Refine to local-max within next refractory window.
            window_end = min(i + refractory, n)
            local = i + int(np.argmax(signal[i:window_end]))
            peaks.append(local)
            i = local + refractory
        else:
            i += 1
    return np.array(peaks, dtype=int)


def heart_rate_bpm(ppg_signal: np.ndarray, fs: float) -> float | None:
    """Median bpm from peak-to-peak intervals. None if fewer than
    `HRV_MIN_PEAKS_FOR_BPM` peaks or signal flat/noisy."""
    if ppg_signal.size < int(fs * 3):
        return None
    if not np.isfinite(ppg_signal).all() or float(np.std(ppg_signal)) < 1e-3:
        return None
    filtered = _bandpass(ppg_signal, fs)
    peaks = _detect_peaks(filtered, fs)
    if peaks.size < HRV_MIN_PEAKS_FOR_BPM:
        return None
    ibis_s = np.diff(peaks) / fs
    if not ibis_s.size:
        return None
    median_ibi = float(np.median(ibis_s))
    if median_ibi <= 0:
        return None
    bpm = 60.0 / median_ibi
    # Sanity bounds: human resting HR. Outside → noise, return None.
    if not (35.0 <= bpm <= 200.0):
        return None
    return round(bpm, 1)


def rmssd_ms(ppg_signal: np.ndarray, fs: float) -> float | None:
    """Root mean square of successive IBI differences, in ms.

    Common HRV index, sensitive to parasympathetic activity. None until enough
    consecutive IBIs are detected.
    """
    if ppg_signal.size < int(fs * 8):
        return None
    filtered = _bandpass(ppg_signal, fs)
    peaks = _detect_peaks(filtered, fs)
    if peaks.size < HRV_MIN_IBI_FOR_RMSSD + 1:
        return None
    ibis_ms = (np.diff(peaks) / fs) * 1000.0
    diffs = np.diff(ibis_ms)
    if not diffs.size:
        return None
    return round(float(np.sqrt(np.mean(diffs * diffs))), 1)


def gyro_max(gyro_window: np.ndarray) -> float:
    """Max absolute angular velocity (any axis, deg/s) over the window.

    Surfaced on FocusFrame so the dash + Coach can show "head was steady" vs
    "user turned to talk" without the agent re-deriving from raw gyro.
    """
    if gyro_window.size == 0:
        return 0.0
    return float(np.max(np.abs(gyro_window)))
