"""Stream protocol — uniform iface for live BLE + synthetic + recorded sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol, runtime_checkable

import numpy as np

from nao.config import ACCEL_AXES, EEG_CHANNELS, GYRO_AXES, PPG_CHANNELS


def _zero_gyro() -> np.ndarray:
    return np.zeros(len(GYRO_AXES))


def _zero_ppg() -> np.ndarray:
    return np.zeros(len(PPG_CHANNELS))


@dataclass(frozen=True, slots=True)
class Sample:
    """One sample tick. EEG in µV, accel in g, gyro in deg/s, PPG in raw counts.

    `gyro` and `ppg` default to zeros so SyntheticStream and pre-M4.2 callers
    don't need to know they exist. Live MuseStream fills both from the
    Gyroscope + PPG LSL outlets that `muselsl` already publishes.
    """
    ts: float
    eeg: np.ndarray              # shape (4,) — TP9, AF7, AF8, TP10
    accel: np.ndarray            # shape (3,) — X, Y, Z
    gyro: np.ndarray = field(default_factory=_zero_gyro)   # shape (3,) — X, Y, Z deg/s
    ppg: np.ndarray = field(default_factory=_zero_ppg)     # shape (3,) — IR1, IR2, ambient

    def __post_init__(self) -> None:
        assert self.eeg.shape == (len(EEG_CHANNELS),), f"eeg shape {self.eeg.shape}"
        assert self.accel.shape == (len(ACCEL_AXES),), f"accel shape {self.accel.shape}"
        assert self.gyro.shape == (len(GYRO_AXES),), f"gyro shape {self.gyro.shape}"
        assert self.ppg.shape == (len(PPG_CHANNELS),), f"ppg shape {self.ppg.shape}"


@runtime_checkable
class Stream(Protocol):
    """Pull-style iterator. Implementations must yield at SAMPLE_RATE_HZ."""

    def __iter__(self) -> Iterator[Sample]: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...
