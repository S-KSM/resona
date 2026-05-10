"""Calibration worker — drive against the synthetic stream end-to-end.

Patches `speak` to a no-op so the test doesn't actually talk to the speaker.
"""
from __future__ import annotations

import time

import pytest

from nao.dash.calibration_worker import (
    CalibrationProgress,
    run_calibration,
)
from nao.ingest.synthetic import SyntheticStream
from nao.process.pipeline import Pipeline
from nao.state import CALIBRATION_PATH, Calibration


@pytest.fixture
def silent_speak(monkeypatch):
    monkeypatch.setattr("nao.dash.calibration_worker.speak", lambda *a, **kw: None)


@pytest.fixture
def isolated_calibration_path(monkeypatch, tmp_path):
    cal_path = tmp_path / "baseline.json"
    monkeypatch.setattr("nao.state.CALIBRATION_PATH", cal_path)
    # Calibration.save() default arg uses CALIBRATION_PATH at module load time;
    # patch the default by replacing the method at instance level. Cleanest:
    # bind a path explicitly via a wrapped save.
    real_save = Calibration.save

    def _save_to_tmp(self, path=cal_path):
        return real_save(self, path)

    monkeypatch.setattr(Calibration, "save", _save_to_tmp)
    return cal_path


def test_worker_runs_short_calibration_and_saves(silent_speak, isolated_calibration_path) -> None:
    src = SyntheticStream(seed=3, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src)
    pipeline.start()
    progress = CalibrationProgress()
    before = time.time()
    try:
        run_calibration(pipeline, progress, seconds_per_phase=2.0, voice_name=None, voice_rate=200)
    finally:
        pipeline.stop()

    assert progress.phase == "done", progress.error
    assert progress.result is not None
    assert progress.result.n_samples > 0
    assert progress.eyes_open and progress.eyes_closed
    assert isolated_calibration_path.exists()
    # Drift-tracking: worker stamps saved_at at construction. Newly-saved
    # baseline must report a fresh, non-stale age.
    assert progress.result.saved_at is not None
    assert progress.result.saved_at >= before
    assert progress.result.age_days() is not None
    assert progress.result.age_days() < 0.01  # well under a day
    assert not progress.result.is_stale()


def test_worker_cancellation(silent_speak, isolated_calibration_path) -> None:
    src = SyntheticStream(seed=4, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src)
    pipeline.start()
    progress = CalibrationProgress()
    progress.cancel = True  # set before thread sees first phase
    try:
        run_calibration(pipeline, progress, seconds_per_phase=2.0, voice_name=None, voice_rate=200)
    finally:
        pipeline.stop()
    assert progress.phase in ("idle", "error"), progress.phase
    assert progress.result is None


def test_progress_phase_transitions(silent_speak, isolated_calibration_path) -> None:
    """Sanity that progress.phase moves through expected states."""
    import threading

    src = SyntheticStream(seed=5, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src)
    pipeline.start()
    progress = CalibrationProgress()
    seen = set()

    def watcher() -> None:
        for _ in range(60):
            seen.add(progress.phase)
            if progress.phase in ("done", "error"):
                return
            time.sleep(0.1)

    t = threading.Thread(target=watcher, daemon=True)
    t.start()
    try:
        run_calibration(pipeline, progress, seconds_per_phase=1.5, voice_name=None, voice_rate=200)
    finally:
        pipeline.stop()
        t.join(timeout=1)

    assert "eyes_open" in seen
    assert "eyes_closed" in seen
    assert progress.phase == "done"
