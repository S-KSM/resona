"""Lock-free-ish ring buffer for streaming EEG samples.

Single-writer (ingest thread), single-reader (pipeline). NumPy backed for fast
windowed slicing.
"""
from __future__ import annotations

import numpy as np

from nao.config import EEG_CHANNELS, GYRO_AXES, PPG_CHANNELS


class RingBuffer:
    """Fixed-capacity 2D ring: rows = samples, cols = channels.

    Tracks EEG, accel, gyro, PPG and timestamps in parallel arrays — all
    aligned by index (same sample = same row across all aux arrays). The
    aux arrays default to zeros for callers that don't push gyro/ppg
    (synthetic stream pre-M4.2, tests).
    """

    def __init__(self, capacity: int, n_channels: int = len(EEG_CHANNELS)) -> None:
        self.capacity = capacity
        self.n_channels = n_channels
        self._eeg = np.zeros((capacity, n_channels), dtype=np.float32)
        self._accel = np.zeros((capacity, 3), dtype=np.float32)
        self._gyro = np.zeros((capacity, len(GYRO_AXES)), dtype=np.float32)
        self._ppg = np.zeros((capacity, len(PPG_CHANNELS)), dtype=np.float32)
        self._ts = np.zeros(capacity, dtype=np.float64)
        self._write = 0
        self._n = 0

    def push(
        self,
        eeg: np.ndarray,
        accel: np.ndarray,
        ts: float,
        gyro: np.ndarray | None = None,
        ppg: np.ndarray | None = None,
    ) -> None:
        i = self._write
        self._eeg[i] = eeg
        self._accel[i] = accel
        if gyro is not None:
            self._gyro[i] = gyro
        else:
            self._gyro[i] = 0.0
        if ppg is not None:
            self._ppg[i] = ppg
        else:
            self._ppg[i] = 0.0
        self._ts[i] = ts
        self._write = (i + 1) % self.capacity
        if self._n < self.capacity:
            self._n += 1

    def __len__(self) -> int:
        return self._n

    def is_full(self) -> bool:
        return self._n == self.capacity

    def latest(self, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return last n samples as (eeg, accel, ts), oldest first.

        Raises ValueError if n > current size.
        """
        if n > self._n:
            raise ValueError(f"requested {n} but only {self._n} samples buffered")
        end = self._write
        start = (end - n) % self.capacity
        if start < end:
            return self._eeg[start:end], self._accel[start:end], self._ts[start:end]
        return (
            np.concatenate([self._eeg[start:], self._eeg[:end]]),
            np.concatenate([self._accel[start:], self._accel[:end]]),
            np.concatenate([self._ts[start:], self._ts[:end]]),
        )

    def latest_aux(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Return last n samples of (gyro, ppg). Same indexing as `latest`.

        Kept separate to avoid breaking the (eeg, accel, ts) tuple shape that
        many callers destructure; HRV/motion code that needs the aux pulls it
        explicitly.
        """
        if n > self._n:
            raise ValueError(f"requested {n} but only {self._n} samples buffered")
        end = self._write
        start = (end - n) % self.capacity
        if start < end:
            return self._gyro[start:end], self._ppg[start:end]
        return (
            np.concatenate([self._gyro[start:], self._gyro[:end]]),
            np.concatenate([self._ppg[start:], self._ppg[:end]]),
        )
