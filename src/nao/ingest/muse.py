"""MuseStream — OpenMuse wrapper behind the Stream protocol.

Falls back to muselsl if OpenMuse import fails. Both libs target the same
hardware; behind our Stream iface upstream code does not care which.
"""
from __future__ import annotations

import collections
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
    retries: int = 8
    backoff_s: float = 1.0
    # 8 s (was 5 s) — gives BLE a touch more grace on a transient stutter
    # so the watchdog doesn't false-positive every minor packet gap into a
    # full reconnect storm.
    silent_timeout_s: float = 8.0

    _q: queue.Queue[Sample] = field(default_factory=queue.Queue, init=False)
    _running: bool = field(default=False, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _muselsl_proc: object | None = field(default=None, init=False)
    # Timestamps (monotonic seconds) of recent muse_runner subprocess exits.
    # Used by `stream_health()` to decide whether the BLE link is unstable
    # enough to warrant a user-facing diagnostic. Bounded — only the last
    # few seconds matter.
    _recent_drops: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=20), init=False
    )
    _last_accel: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0]), init=False
    )
    _last_gyro: np.ndarray = field(
        default_factory=lambda: np.zeros(len(GYRO_AXES)), init=False
    )
    _last_ppg: np.ndarray = field(
        default_factory=lambda: np.zeros(len(PPG_CHANNELS)), init=False
    )
    _last_battery_pct: float | None = field(default=None, init=False)
    _last_battery_ts: float | None = field(default=None, init=False)

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
        self._terminate_muselsl_proc()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _terminate_muselsl_proc(self) -> None:
        """Kill the muselsl subprocess (if any). Required because muselsl's
        stream() blocks in a daemon thread and holds BLE — only a real OS
        signal frees the headband on pipeline restart."""
        proc = self._muselsl_proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except Exception:  # noqa: BLE001
                    proc.kill()
                    proc.wait(timeout=2.0)
        except Exception as e:  # noqa: BLE001
            log.warning("muselsl subprocess shutdown raised: %s", e)
        finally:
            self._muselsl_proc = None

    def __iter__(self) -> Iterator[Sample]:
        if not self._running:
            self.start()
        while self._running:
            try:
                yield self._q.get(timeout=1.0)
            except queue.Empty:
                continue

    def stream_health(self) -> dict:
        """Snapshot for the UI: are we in a flapping-BLE state?

        `unstable` = True when 3+ subprocess drops have happened in the
        last 30 s. Three is the threshold where it stops looking like a
        transient and starts looking like a sustained problem (low Muse
        battery, kernel BLE state, headband held by another paired
        device, etc.) the user should act on.
        """
        now = time.monotonic()
        window = 30.0
        recent = [t for t in self._recent_drops if (now - t) <= window]
        last_drop_age = (now - self._recent_drops[-1]) if self._recent_drops else None
        return {
            "unstable": len(recent) >= 3,
            "recent_drops": len(recent),
            "last_drop_age_s": last_drop_age,
        }

    # --- internals ---

    def _run(self) -> None:
        backoff = self.backoff_s
        attempt = 0
        while self._running and attempt < self.retries:
            attempt += 1
            try:
                self._stream_loop()
                if not self._running:
                    return
                # Stream returned without exception but we're still running →
                # treat as a soft drop, retry with reset backoff.
                log.info("MuseStream loop exited; reconnecting (attempt %d)", attempt)
                attempt = 0
                backoff = self.backoff_s
                continue
            except Exception as e:  # noqa: BLE001 — BLE libs raise broadly
                log.warning("MuseStream attempt %d failed: %s", attempt, e)
                self._recent_drops.append(time.monotonic())
                self._terminate_muselsl_proc()
                if not self._running:
                    return
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
        if self._running:
            log.error("MuseStream giving up after %d attempts.", self.retries)
        self._running = False

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
        """Fallback: spawn `muselsl stream` as a subprocess so we can kill it
        on pipeline restart. The previous in-process daemon-thread approach
        leaked: muselsl_stream() blocks in C-level BLE code that doesn't
        observe our `_running` flag, so two parallel muselsl instances ended
        up fighting the same headband across restarts.

        muselsl publishes 4 LSL outlets: EEG (mandatory) + ACC + GYRO + PPG.
        Only EEG is required; aux outlets are best-effort.
        """
        import subprocess
        import sys

        from pylsl import StreamInlet, resolve_byprop  # type: ignore

        # Use our custom runner instead of `muselsl stream`. Same 4 standard
        # outlets plus a Battery outlet that muselsl doesn't expose.
        cmd = [sys.executable, "-m", "nao.scripts.muse_runner"]
        if self.address:
            cmd += ["-a", self.address]
        log.info("Spawning muse runner: %s", " ".join(cmd))
        self._muselsl_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        time.sleep(2.0)  # let outlet appear
        streams = resolve_byprop("type", "EEG", timeout=10.0)
        if not streams:
            raise RuntimeError("No LSL EEG stream resolved")
        inlet = StreamInlet(streams[0])

        # muselsl 2.3 publishes "ACC" and "GYRO" type strings (not
        # "Accelerometer" / "Gyroscope") — mismatched names dropped the aux
        # outlets silently in earlier versions of this code.
        self._spawn_aux_inlet("ACC", self._on_accel_chunk)
        self._spawn_aux_inlet("GYRO", self._on_gyro_chunk)
        self._spawn_aux_inlet("PPG", self._on_ppg_chunk)
        self._spawn_aux_inlet("Battery", self._on_battery_chunk)

        last_chunk_ts = time.monotonic()
        try:
            while self._running:
                if self._muselsl_proc.poll() is not None:
                    raise RuntimeError(
                        f"muselsl subprocess exited rc={self._muselsl_proc.returncode}"
                    )
                chunk, ts = inlet.pull_chunk(timeout=0.1, max_samples=32)
                if chunk:
                    last_chunk_ts = time.monotonic()
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
                elif time.monotonic() - last_chunk_ts > self.silent_timeout_s:
                    raise RuntimeError(
                        f"muselsl silent for {self.silent_timeout_s:.0f}s; "
                        "BLE likely dropped — triggering reconnect"
                    )
        finally:
            self._terminate_muselsl_proc()

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

    def _on_battery_chunk(self, chunk: np.ndarray) -> None:
        """Telemetry outlet: [battery_pct, fuel_gauge, adc_volt, temperature].

        Muse pushes telemetry every few seconds — we just keep the latest
        value and timestamp so the API can report charge level on demand.
        """
        last = chunk[-1]
        if last.size >= 1:
            self._last_battery_pct = float(last[0])
            self._last_battery_ts = time.time()

    @property
    def battery_pct(self) -> float | None:
        """Latest reported battery percentage (0–100), or None if not yet seen."""
        return self._last_battery_pct

    @property
    def battery_age_s(self) -> float | None:
        if self._last_battery_ts is None:
            return None
        return time.time() - self._last_battery_ts
