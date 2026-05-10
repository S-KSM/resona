"""Pipeline — glues ingest → buffer → features → subscribers.

Designed for fan-out: dash subscribes today, MCP server subscribes in Phase 2,
without changing the producer.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from nao.config import (
    BANDPASS_HZ,
    DISPLAY_SECONDS,
    NOTCH_HZ,
    SAMPLE_RATE_HZ,
    STRIDE_SAMPLES,
    WINDOW_SAMPLES,
)
from nao.ingest.stream import Stream
from nao.process.affect import arousal_index, frontal_asymmetry
from nao.process.artifacts import Artifact, detect_artifacts, is_clean
from nao.process.bands import band_power
from nao.process.buffer import RingBuffer
from nao.process.focus import FocusEMA, focus_coef
from nao.process.frame import FocusFrame
from nao.process.hrv import gyro_max as gyro_max_fn
from nao.process.hrv import heart_rate_bpm, rmssd_ms

log = logging.getLogger(__name__)

Subscriber = Callable[[FocusFrame], None]


def _bandpass_notch(window: np.ndarray) -> np.ndarray:
    """Remove DC drift + line noise. Light-touch; full MNE filtering deferred.

    Uses a simple 4th-order Butterworth via scipy (cheaper than full MNE Raw)
    so we stay well inside the latency budget.
    """
    from scipy.signal import butter, iirnotch, sosfiltfilt, tf2sos

    lo, hi = BANDPASS_HZ
    sos_bp = butter(4, [lo, hi], btype="band", fs=SAMPLE_RATE_HZ, output="sos")
    out = sosfiltfilt(sos_bp, window, axis=0)
    b_n, a_n = iirnotch(NOTCH_HZ, Q=30.0, fs=SAMPLE_RATE_HZ)
    sos_n = tf2sos(b_n, a_n)
    return sosfiltfilt(sos_n, out, axis=0)


class Pipeline:
    """Ingest → window → features → emit FocusFrames.

    Args:
        source: any Stream (Synthetic/Muse/etc.).
        window_samples: FFT window length.
        stride_samples: emit cadence.
        bandpass: if True, apply notch+bandpass before features.
    """

    def __init__(
        self,
        source: Stream,
        window_samples: int = WINDOW_SAMPLES,
        stride_samples: int = STRIDE_SAMPLES,
        bandpass: bool = True,
        display_seconds: float = DISPLAY_SECONDS,
    ) -> None:
        self.source = source
        self.window_samples = window_samples
        self.stride_samples = stride_samples
        self.bandpass = bandpass
        # Buffer holds at least the FFT window, plus extra history so the
        # dash can plot recent raw waves without a separate buffer.
        capacity = max(window_samples, int(SAMPLE_RATE_HZ * display_seconds))
        self.buffer = RingBuffer(capacity=capacity)
        self.focus_ema = FocusEMA()
        self.frontal_focus_ema = FocusEMA()
        self._subscribers: list[Subscriber] = []
        self._thread: threading.Thread | None = None
        self._running = False
        self._latest: FocusFrame | None = None

    def latest_window(
        self, n_samples: int | None = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Return (eeg, accel, ts) for the most-recent `n_samples`, or None
        if the buffer hasn't filled yet. Local-only consumer (the dash) —
        do NOT plumb raw samples through the MCP boundary."""
        n = n_samples or self.window_samples
        if len(self.buffer) < n:
            return None
        return self.buffer.latest(n)

    def subscribe(self, fn: Subscriber) -> None:
        self._subscribers.append(fn)

    def unsubscribe(self, fn: Subscriber) -> None:
        try:
            self._subscribers.remove(fn)
        except ValueError:
            pass

    @property
    def latest(self) -> FocusFrame | None:
        return self._latest

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="Pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self.source.stop()
        if self._thread:
            self._thread.join(timeout=2.0)

    # --- internals ---

    def _run(self) -> None:
        self.source.start()
        since_emit = 0
        for sample in self.source:
            if not self._running:
                break
            self.buffer.push(
                sample.eeg, sample.accel, sample.ts,
                gyro=getattr(sample, "gyro", None),
                ppg=getattr(sample, "ppg", None),
            )
            since_emit += 1
            if len(self.buffer) >= self.window_samples and since_emit >= self.stride_samples:
                self._emit_frame(arrival_ts=sample.ts)
                since_emit = 0

    def _emit_frame(self, arrival_ts: float) -> None:
        # Lazy-import to avoid an import cycle: gatekeeper.frontal imports
        # nao.process.frame; pulling that in at module-load time on this side
        # would deadlock the agent package's first import.
        from nao.agents.gatekeeper.frontal import frontal_focus_from_powers

        t_start = time.monotonic()
        eeg, accel, _ts = self.buffer.latest(self.window_samples)
        gyro_window, _ppg_window_short = self.buffer.latest_aux(self.window_samples)

        flags = detect_artifacts(eeg, accel, gyro_window=gyro_window)

        eeg_proc = _bandpass_notch(eeg) if self.bandpass else eeg
        powers = band_power(eeg_proc)

        # HRV uses a longer PPG window (10 s) than the EEG window (1 s) so we
        # have enough peaks to detect. RingBuffer capacity = DISPLAY_SECONDS s
        # of samples (default 4 s) — pull whatever's available, capped.
        hrv_window_n = min(SAMPLE_RATE_HZ * 10, len(self.buffer))
        if hrv_window_n >= SAMPLE_RATE_HZ * 3:
            _gw_long, ppg_long = self.buffer.latest_aux(hrv_window_n)
            ppg_signal = ppg_long[:, 0] if ppg_long.ndim == 2 else ppg_long
            hr = heart_rate_bpm(ppg_signal, fs=SAMPLE_RATE_HZ)
            rmssd = rmssd_ms(ppg_signal, fs=SAMPLE_RATE_HZ)
        else:
            hr = None
            rmssd = None
        gyro_peak = gyro_max_fn(gyro_window) if gyro_window.size else None

        f_raw = focus_coef(powers["alpha"], powers["beta"])
        f_ema = self.focus_ema.update(f_raw)

        alpha_pc = powers["alpha"].tolist()
        beta_pc = powers["beta"].tolist()
        gamma_pc = powers["gamma"].tolist()
        frontal_raw = frontal_focus_from_powers(alpha_pc, beta_pc)
        frontal_ema = (
            self.frontal_focus_ema.update(frontal_raw) if frontal_raw is not None else None
        )

        alpha_mean = float(np.mean(powers["alpha"]))
        beta_mean = float(np.mean(powers["beta"]))
        gamma_mean = float(np.mean(powers["gamma"]))
        delta_mean = float(np.mean(powers["delta"]))
        theta_mean = float(np.mean(powers["theta"]))
        asymmetry = frontal_asymmetry(alpha_pc)
        arousal = arousal_index(alpha_mean, beta_mean, gamma_mean)

        # Relative power: each band as a fraction of total. Bounded 0-1 so
        # the UI can show a meaningful bar without per-user calibration.
        total = delta_mean + theta_mean + alpha_mean + beta_mean + gamma_mean
        if total > 1e-9:
            delta_rel = delta_mean / total
            theta_rel = theta_mean / total
            alpha_rel = alpha_mean / total
            beta_rel = beta_mean / total
            gamma_rel = gamma_mean / total
        else:
            delta_rel = theta_rel = alpha_rel = beta_rel = gamma_rel = None

        frame = FocusFrame(
            ts=arrival_ts,
            alpha=alpha_mean,
            beta=beta_mean,
            theta=theta_mean,
            delta=delta_mean,
            gamma=gamma_mean,
            delta_rel=delta_rel,
            theta_rel=theta_rel,
            alpha_rel=alpha_rel,
            beta_rel=beta_rel,
            gamma_rel=gamma_rel,
            focus=f_raw,
            focus_ema=f_ema,
            artifact=[a.name for a in Artifact if a in flags and a is not Artifact.NONE],
            artifact_clean=is_clean(flags),
            latency_ms=(time.monotonic() - t_start) * 1000.0,
            alpha_per_channel=alpha_pc,
            beta_per_channel=beta_pc,
            gamma_per_channel=gamma_pc,
            frontal_focus=frontal_raw,
            frontal_focus_ema=frontal_ema,
            frontal_asymmetry=asymmetry,
            arousal_index=arousal,
            heart_rate_bpm=hr,
            hrv_rmssd=rmssd,
            gyro_max=gyro_peak,
        )
        self._latest = frame
        for sub in self._subscribers:
            try:
                sub(frame)
            except Exception as e:  # noqa: BLE001
                log.warning("subscriber %s raised: %s", sub, e)
