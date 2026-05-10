"""MuseStream — OpenMuse wrapper behind the Stream protocol.

Falls back to muselsl if OpenMuse import fails. Both libs target the same
hardware; behind our Stream iface upstream code does not care which.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from nao.config import (
    ACCEL_AXES,
    EEG_CHANNELS,
    GYRO_AXES,
    PPG_CHANNELS,
    SAMPLE_RATE_HZ,
)
from nao.ingest.stream import Sample

log = logging.getLogger(__name__)


@dataclass
class MuseStream:
    """Live BLE stream from a Muse-14B3.

    Args:
        address: BLE address or device name. Default scans for "Muse-*".
        retries: connection retry count.
        backoff_s: initial backoff; doubles each retry.
    """
    address: str | None = None
    retries: int = 3
    backoff_s: float = 1.0

    _q: queue.Queue[Sample] = field(default_factory=queue.Queue, init=False)
    _running: bool = field(default=False, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _last_accel: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0]), init=False
    )
    _last_gyro: np.ndarray = field(
        default_factory=lambda: np.zeros(len(GYRO_AXES)), init=False
    )
    _last_ppg: np.ndarray = field(
        default_factory=lambda: np.zeros(len(PPG_CHANNELS)), init=False
    )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="MuseStream", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def __iter__(self) -> Iterator[Sample]:
        if not self._running:
            self.start()
        while self._running:
            try:
                yield self._q.get(timeout=1.0)
            except queue.Empty:
                continue

    # --- internals ---

    def _run(self) -> None:
        backoff = self.backoff_s
        for attempt in range(1, self.retries + 1):
            try:
                self._stream_loop()
                return
            except Exception as e:  # noqa: BLE001 — BLE libs raise broadly
                log.warning("MuseStream attempt %d failed: %s", attempt, e)
                if attempt == self.retries:
                    log.error("MuseStream giving up.")
                    self._running = False
                    return
                time.sleep(backoff)
                backoff *= 2

    def _stream_loop(self) -> None:
        """Try OpenMuse; fall back to muselsl if missing."""
        try:
            import OpenMuse  # type: ignore
            self._stream_openmuse(OpenMuse)
        except ImportError:
            log.info("OpenMuse not available, falling back to muselsl.")
            self._stream_muselsl()

    def _stream_openmuse(self, OpenMuse) -> None:  # type: ignore[no-untyped-def]
        """Bridge OpenMuse callback API into our queue. API likely surface:
        OpenMuse.connect(address) -> ctx with on_eeg / on_accel callbacks.

        OpenMuse is young; if its API differs at runtime we'll catch the
        AttributeError and surface a clear error to the dash.
        """
        addr = self.address or "Muse-14B3"
        log.info("Connecting via OpenMuse to %s", addr)

        def on_eeg(packet) -> None:  # type: ignore[no-untyped-def]
            # OpenMuse packets typically: .timestamp + .data shape (n, 4)
            ts = float(getattr(packet, "timestamp", time.monotonic()))
            data = np.asarray(packet.data, dtype=float)
            for i, row in enumerate(data):
                self._q.put(
                    Sample(
                        ts=ts + i / SAMPLE_RATE_HZ,
                        eeg=row[: len(EEG_CHANNELS)],
                        accel=self._last_accel.copy(),
                        gyro=self._last_gyro.copy(),
                        ppg=self._last_ppg.copy(),
                    )
                )

        def on_accel(packet) -> None:  # type: ignore[no-untyped-def]
            data = np.asarray(packet.data, dtype=float)
            self._last_accel = data[-1, : len(ACCEL_AXES)]

        def on_gyro(packet) -> None:  # type: ignore[no-untyped-def]
            data = np.asarray(packet.data, dtype=float)
            self._last_gyro = data[-1, : len(GYRO_AXES)]

        def on_ppg(packet) -> None:  # type: ignore[no-untyped-def]
            data = np.asarray(packet.data, dtype=float)
            self._last_ppg = data[-1, : len(PPG_CHANNELS)]

        ctx = OpenMuse.connect(addr)
        ctx.on_eeg = on_eeg
        ctx.on_accel = on_accel
        # OpenMuse may not publish gyro/ppg in older versions; tolerate missing.
        for cb_name, cb in (("on_gyro", on_gyro), ("on_ppg", on_ppg)):
            try:
                setattr(ctx, cb_name, cb)
            except AttributeError:
                log.info("OpenMuse: %s not supported by this build", cb_name)
        ctx.start()
        try:
            while self._running:
                time.sleep(0.1)
        finally:
            ctx.stop()

    def _stream_muselsl(self) -> None:
        """Fallback: use muselsl + pylsl. muselsl.stream() pushes to LSL.

        muselsl's bleak backend calls asyncio.get_event_loop(), which on
        Python 3.13 raises in non-main threads unless a loop is set first.
        We pre-install one in the spawned thread.

        muselsl publishes 4 LSL outlets: EEG (mandatory) + Accelerometer +
        Gyroscope + PPG (optional, may be absent on older muselsl/firmware).
        We resolve them all but only EEG is required.
        """
        import asyncio

        from muselsl import stream as muselsl_stream  # type: ignore
        from pylsl import StreamInlet, resolve_byprop  # type: ignore

        def _muselsl_runner() -> None:
            asyncio.set_event_loop(asyncio.new_event_loop())
            # ppg=True + acc=True + gyro=True asks muselsl to publish all 4.
            try:
                muselsl_stream(
                    address=self.address, ppg_enabled=True, acc_enabled=True, gyro_enabled=True
                )
            except TypeError:
                # Older muselsl signatures lack the per-stream flags.
                muselsl_stream(address=self.address)

        threading.Thread(target=_muselsl_runner, name="muselsl", daemon=True).start()
        time.sleep(2.0)  # allow LSL outlets to come up
        streams = resolve_byprop("type", "EEG", timeout=10.0)
        if not streams:
            raise RuntimeError("No LSL EEG stream resolved")
        inlet = StreamInlet(streams[0])

        # Optional outlets — best-effort. Bring them up on background threads
        # so we never block EEG on a missing PPG outlet. muselsl 2.3 publishes
        # type names "ACC" and "GYRO" (not "Accelerometer" / "Gyroscope") —
        # mismatched type strings made the outlets silently drop earlier.
        self._spawn_aux_inlet("ACC", self._on_accel_chunk)
        self._spawn_aux_inlet("GYRO", self._on_gyro_chunk)
        self._spawn_aux_inlet("PPG", self._on_ppg_chunk)

        while self._running:
            chunk, ts = inlet.pull_chunk(timeout=0.1, max_samples=32)
            for row, t in zip(chunk, ts):
                arr = np.asarray(row, dtype=float)[: len(EEG_CHANNELS)]
                self._q.put(
                    Sample(
                        ts=float(t),
                        eeg=arr,
                        accel=self._last_accel.copy(),
                        gyro=self._last_gyro.copy(),
                        ppg=self._last_ppg.copy(),
                    )
                )

    def _spawn_aux_inlet(
        self, lsl_type: str, on_chunk
    ) -> None:
        """Resolve an LSL outlet by type, pull chunks, hand to `on_chunk`.
        Best-effort: silent no-op if the outlet never appears."""
        from pylsl import StreamInlet, resolve_byprop  # type: ignore

        def _runner() -> None:
            streams = resolve_byprop("type", lsl_type, timeout=8.0)
            if not streams:
                log.info("%s LSL outlet not present; skipping.", lsl_type)
                return
            inlet = StreamInlet(streams[0])
            while self._running:
                chunk, _ts = inlet.pull_chunk(timeout=0.1, max_samples=32)
                if chunk:
                    on_chunk(np.asarray(chunk, dtype=float))

        threading.Thread(target=_runner, name=f"muselsl-{lsl_type}", daemon=True).start()

    def _on_accel_chunk(self, chunk: np.ndarray) -> None:
        self._last_accel = chunk[-1, : len(ACCEL_AXES)]

    def _on_gyro_chunk(self, chunk: np.ndarray) -> None:
        self._last_gyro = chunk[-1, : len(GYRO_AXES)]

    def _on_ppg_chunk(self, chunk: np.ndarray) -> None:
        # Muse PPG packs 3 channels; some firmware sends fewer. Pad zeros.
        last = chunk[-1]
        n_have = min(len(last), len(PPG_CHANNELS))
        out = np.zeros(len(PPG_CHANNELS))
        out[:n_have] = last[:n_have]
        self._last_ppg = out
