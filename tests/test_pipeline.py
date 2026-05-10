"""End-to-end: synthetic stream -> Pipeline -> FocusFrame.

Uses non-realtime synthetic so the test runs in milliseconds."""
from __future__ import annotations

import threading

from nao.ingest.synthetic import SyntheticStream
from nao.process.pipeline import Pipeline


def _run_pipeline_for(pipeline: Pipeline, max_frames: int, timeout_s: float = 5.0) -> list:
    frames: list = []
    done = threading.Event()

    def collect(frame) -> None:
        frames.append(frame)
        if len(frames) >= max_frames:
            done.set()

    pipeline.subscribe(collect)
    pipeline.start()
    done.wait(timeout=timeout_s)
    pipeline.stop()
    return frames


def test_pipeline_emits_frames_with_alpha_injection() -> None:
    src = SyntheticStream(seed=7, inject_hz=10.0, inject_uv=80.0, realtime=False)
    pipeline = Pipeline(source=src, bandpass=False)
    frames = _run_pipeline_for(pipeline, max_frames=3, timeout_s=10.0)
    assert len(frames) >= 3, f"only got {len(frames)} frames"
    f = frames[-1]
    # 10 Hz tone -> alpha band should outweigh beta.
    assert f.alpha > f.beta, (f.alpha, f.beta)
    assert f.focus < 1.0  # beta/alpha should be small


def test_pipeline_emits_frames_with_beta_injection() -> None:
    src = SyntheticStream(seed=7, inject_hz=22.0, inject_uv=80.0, realtime=False)
    pipeline = Pipeline(source=src, bandpass=False)
    frames = _run_pipeline_for(pipeline, max_frames=3, timeout_s=10.0)
    assert len(frames) >= 3
    f = frames[-1]
    assert f.beta > f.alpha, (f.alpha, f.beta)
    assert f.focus > 1.0


def test_pipeline_latency_under_budget() -> None:
    src = SyntheticStream(seed=1, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src, bandpass=True)
    frames = _run_pipeline_for(pipeline, max_frames=3)
    # Per-frame compute time should be tiny — full sensor-to-dash budget is 500ms,
    # the compute slice alone must be a small fraction.
    for f in frames:
        assert f.latency_ms < 100, f.latency_ms


def test_focus_ema_present() -> None:
    src = SyntheticStream(seed=2, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src, bandpass=False)
    frames = _run_pipeline_for(pipeline, max_frames=4)
    # EMA after a few samples shouldn't equal raw (smoothing kicked in).
    diffs = [abs(f.focus_ema - f.focus) for f in frames]
    assert any(d > 1e-6 for d in diffs), "EMA looks identical to raw"


def test_pipeline_populates_frontal_focus_fields() -> None:
    """Pipeline should emit frontal_focus + frontal_focus_ema on every frame."""
    src = SyntheticStream(seed=3, inject_hz=10.0, realtime=False)
    pipeline = Pipeline(source=src, bandpass=False)
    frames = _run_pipeline_for(pipeline, max_frames=4)
    for f in frames:
        assert f.frontal_focus is not None, "expected frontal_focus on every emitted frame"
        assert f.frontal_focus_ema is not None
        assert f.frontal_focus > 0
    # EMA smoothing should differ from the raw at least once.
    diffs = [abs(f.frontal_focus_ema - f.frontal_focus) for f in frames]
    assert any(d > 1e-6 for d in diffs), "frontal EMA looks identical to raw"
