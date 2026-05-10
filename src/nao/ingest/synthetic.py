"""Synthetic EEG stream — pink noise + injectable band sinusoids. Seedable.

Lets us build/test the rest of the pipeline without the headband paired.
Inject a pure 10 Hz tone -> alpha power should dominate. 20 Hz -> beta. Etc.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from nao.config import ACCEL_AXES, EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.ingest.stream import Sample


def _pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """1/f noise via Voss-McCartney-ish FFT shaping. Cheap, good enough for dev."""
    white = rng.standard_normal(n)
    f = np.fft.rfftfreq(n, d=1.0 / SAMPLE_RATE_HZ)
    f[0] = 1.0
    spec = np.fft.rfft(white) / np.sqrt(f)
    out = np.fft.irfft(spec, n=n).real
    return out / (np.std(out) + 1e-9)


@dataclass
class SyntheticStream:
    """Yields fake Samples in real time.

    Args:
        seed: deterministic randomness for tests.
        inject_hz: optional sinusoid injected into all 4 EEG channels.
        inject_uv: amplitude (µV) of injected sinusoid.
        noise_uv: amplitude of pink-noise floor (µV).
        realtime: if True, sleep between samples to match SAMPLE_RATE_HZ.
                  Set False in tests for fast iteration.
    """
    seed: int = 0
    inject_hz: float | None = None
    inject_uv: float = 30.0
    noise_uv: float = 15.0
    realtime: bool = True

    _rng: np.random.Generator = field(init=False)
    _running: bool = field(default=False, init=False)
    _t0: float = field(default=0.0, init=False)
    _i: int = field(default=0, init=False)
    _noise_buf: np.ndarray = field(init=False, default=None)  # type: ignore
    _buf_idx: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        # Pre-generate 4s of pink noise per channel; cycle through it.
        n = SAMPLE_RATE_HZ * 4
        self._noise_buf = np.stack(
            [_pink_noise(n, self._rng) for _ in EEG_CHANNELS], axis=1
        )

    def start(self) -> None:
        self._t0 = time.monotonic()
        self._i = 0
        self._running = True

    def stop(self) -> None:
        self._running = False

    def __iter__(self) -> Iterator[Sample]:
        if not self._running:
            self.start()
        dt = 1.0 / SAMPLE_RATE_HZ
        while self._running:
            t = self._i * dt
            noise = self._noise_buf[self._buf_idx % len(self._noise_buf)] * self.noise_uv
            self._buf_idx += 1
            eeg = noise.copy()
            if self.inject_hz is not None:
                eeg += self.inject_uv * np.sin(2 * np.pi * self.inject_hz * t)
            accel = np.array(
                [0.0, 0.0, 1.0]
            ) + self._rng.standard_normal(len(ACCEL_AXES)) * 0.005
            sample = Sample(ts=self._t0 + t, eeg=eeg, accel=accel)
            self._i += 1
            if self.realtime:
                target = self._t0 + self._i * dt
                slack = target - time.monotonic()
                if slack > 0:
                    time.sleep(slack)
            yield sample
