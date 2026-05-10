"""Voice-guided calibration that runs in a background thread.

Why a thread: Streamlit's render loop must stay responsive (live charts +
voice TTS run concurrently). Worker writes progress into a shared
`CalibrationProgress` dataclass that the page polls each rerun.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from nao.dash.voice import speak
from nao.process.frame import FocusFrame
from nao.process.pipeline import Pipeline
from nao.state import Calibration


@dataclass
class CalibrationProgress:
    """Mutable shared state. Worker writes; UI thread reads."""
    phase: str = "idle"  # idle | eyes_open | eyes_closed | saving | done | error
    seconds_remaining: float = 0.0
    seconds_total: float = 0.0
    eyes_open: list[FocusFrame] = field(default_factory=list)
    eyes_closed: list[FocusFrame] = field(default_factory=list)
    result: Optional[Calibration] = None
    error: Optional[str] = None
    cancel: bool = False
    artifact_counts: dict[str, int] = field(default_factory=dict)


def _count_artifacts(frames: list[FocusFrame]) -> dict[str, int]:
    counts: dict[str, int] = {"clean": 0, "total": len(frames)}
    for f in frames:
        if f.artifact_clean:
            counts["clean"] += 1
        for flag in f.artifact:
            counts[flag] = counts.get(flag, 0) + 1
    return counts


def _collect_phase(
    pipeline: Pipeline, progress: CalibrationProgress, label: str, seconds: float
) -> list[FocusFrame]:
    progress.phase = label
    progress.seconds_total = seconds
    frames: list[FocusFrame] = []
    pipeline.subscribe(frames.append)
    try:
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            if progress.cancel:
                return frames
            progress.seconds_remaining = max(0.0, t_end - time.monotonic())
            time.sleep(0.1)
    finally:
        pipeline.unsubscribe(frames.append)
    return frames


def run_calibration(
    pipeline: Pipeline,
    progress: CalibrationProgress,
    seconds_per_phase: float = 60.0,
    voice_name: str | None = None,
    voice_rate: int = 175,
) -> None:
    """Two-phase calibration with voice prompts. Designed to be the target of
    a daemon thread; updates `progress` in place."""

    def _say(text: str) -> None:
        if progress.cancel:
            return
        if voice_name is None:
            return  # Swift drives voice via AVSpeechSynthesizer; bypass macOS `say`.
        speak(text, voice=voice_name, rate_wpm=voice_rate, blocking=True)

    try:
        _say(
            "Calibration starting. Sit still and keep the headband centered. "
            "First phase, eyes open. Look at the screen and breathe normally. "
            "Beginning in three. Two. One. Begin."
        )
        if progress.cancel:
            progress.phase = "idle"
            return

        progress.eyes_open = _collect_phase(
            pipeline, progress, "eyes_open", seconds_per_phase
        )
        if progress.cancel:
            progress.phase = "idle"
            return

        _say(
            "Eyes open phase complete. Now close your eyes and relax. "
            "Beginning in three. Two. One. Eyes closed."
        )
        if progress.cancel:
            progress.phase = "idle"
            return

        progress.eyes_closed = _collect_phase(
            pipeline, progress, "eyes_closed", seconds_per_phase
        )
        if progress.cancel:
            progress.phase = "idle"
            return

        _say("Calibration complete. You may open your eyes. Saving baseline.")

        progress.phase = "saving"
        all_frames = progress.eyes_open + progress.eyes_closed
        progress.artifact_counts = _count_artifacts(all_frames)
        pool = [
            f.focus
            for f in all_frames
            if f.artifact_clean and np.isfinite(f.focus) and f.focus < 1e4
        ]
        if len(pool) < 10:
            counts = progress.artifact_counts
            breakdown = ", ".join(
                f"{k}={v}" for k, v in counts.items() if k not in ("clean", "total")
            ) or "no flags raised"
            raise RuntimeError(
                f"Only {len(pool)}/{counts.get('total', 0)} clean frames after "
                f"artifact filter ({breakdown}). Reseat headband (especially temporal "
                "TP9/TP10), don't clench jaw, hold still, then retry."
            )
        cal = Calibration(
            mean_f=float(np.mean(pool)),
            std_f=float(np.std(pool)),
            n_samples=len(pool),
            saved_at=time.time(),
        )
        cal.save()
        progress.result = cal
        progress.phase = "done"
    except Exception as e:  # noqa: BLE001 — surface any failure to the UI
        progress.error = str(e)
        progress.phase = "error"


def start_calibration_thread(
    pipeline: Pipeline,
    seconds_per_phase: float,
    voice_name: str | None,
    voice_rate: int,
) -> tuple[CalibrationProgress, threading.Thread]:
    progress = CalibrationProgress()
    t = threading.Thread(
        target=run_calibration,
        args=(pipeline, progress, seconds_per_phase, voice_name, voice_rate),
        name="calibrate",
        daemon=True,
    )
    t.start()
    return progress, t
