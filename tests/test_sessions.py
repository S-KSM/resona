"""SessionRecorder + SessionStore — disk layout, lifecycle, summary."""
from __future__ import annotations

import json
import time

import pytest

from nao.process.frame import FocusFrame
from nao.sessions.recorder import SessionRecorder
from nao.sessions.store import SessionStore


def _frame(
    focus: float = 1.0,
    *,
    ts: float = 0.0,
    clean: bool = True,
    asym: float | None = 0.1,
    arousal: float | None = 2.0,
) -> FocusFrame:
    return FocusFrame(
        ts=ts,
        alpha=1.0,
        beta=focus,
        theta=0.5,
        delta=0.2,
        gamma=0.3,
        focus=focus,
        focus_ema=focus,
        artifact=[] if clean else ["BLINK"],
        artifact_clean=clean,
        latency_ms=1.0,
        frontal_asymmetry=asym,
        arousal_index=arousal,
    )


def test_idle_recorder_drops_frames(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    rec.on_frame(_frame())  # no session active — must be a no-op, no jsonl.
    assert list(tmp_path.glob("*.jsonl")) == []
    assert rec.store.list_sessions() == []


def test_start_records_frames_and_stop_finalizes(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    s = rec.start(label="meditate", notes="post-lunch")
    assert s.is_active
    assert rec.active is not None and rec.active.id == s.id

    for i in range(10):
        rec.on_frame(_frame(focus=0.5 + i * 0.1, ts=float(i)))
    # one dirty frame
    rec.on_frame(_frame(focus=99.0, ts=11.0, clean=False))

    finished = rec.stop()
    assert finished is not None
    assert finished.id == s.id
    assert not finished.is_active
    assert finished.summary.frame_count == 11
    assert finished.summary.clean_frame_count == 10
    assert finished.summary.artifact_rate == pytest.approx(1 / 11)
    assert finished.summary.focus_mean is not None
    assert finished.summary.focus_std is not None
    # Index has the finalized session.
    assert [x.id for x in rec.store.list_sessions()] == [s.id]
    # JSONL has 11 lines.
    jsonl = tmp_path / f"{s.id}.jsonl"
    assert jsonl.exists()
    lines = [ln for ln in jsonl.read_text().splitlines() if ln.strip()]
    assert len(lines) == 11
    # Round-trip into FocusFrame.
    frames = rec.store.read_frames(s.id)
    assert len(frames) == 11


def test_double_start_raises(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    rec.start(label="coding")
    with pytest.raises(RuntimeError):
        rec.start(label="meditate")
    rec.stop()


def test_stop_when_idle_returns_none(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    assert rec.stop() is None


def test_summary_skips_dirty_frames_for_means(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    rec.start(label="rest")
    # 1 clean focus=2 (asymmetry=0.5, arousal=4), 1 dirty focus=99 (ignored).
    rec.on_frame(_frame(focus=2.0, asym=0.5, arousal=4.0))
    rec.on_frame(_frame(focus=99.0, clean=False, asym=999.0, arousal=999.0))
    finished = rec.stop()
    assert finished is not None
    assert finished.summary.focus_mean == pytest.approx(2.0)
    assert finished.summary.asymmetry_mean == pytest.approx(0.5)
    assert finished.summary.arousal_mean == pytest.approx(4.0)
    assert finished.summary.frame_count == 2
    assert finished.summary.clean_frame_count == 1


def test_summary_handles_null_affect_fields(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    rec.start(label="meditate")
    rec.on_frame(_frame(focus=1.0, asym=None, arousal=None))
    finished = rec.stop()
    assert finished is not None
    assert finished.summary.asymmetry_mean is None
    assert finished.summary.arousal_mean is None


def test_index_persists_across_store_instances(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    s = rec.start(label="deep_work")
    rec.on_frame(_frame())
    rec.stop()

    fresh = SessionStore(root=tmp_path)
    listed = fresh.list_sessions()
    assert len(listed) == 1
    assert listed[0].id == s.id
    assert listed[0].label == "deep_work"
    assert listed[0].ended_at is not None


def test_delete_removes_index_and_jsonl(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    s = rec.start(label="reading")
    rec.on_frame(_frame())
    rec.stop()
    jsonl = tmp_path / f"{s.id}.jsonl"
    assert jsonl.exists()
    assert rec.store.delete(s.id) is True
    assert not jsonl.exists()
    assert rec.store.list_sessions() == []
    # Idempotent: second delete returns False.
    assert rec.store.delete(s.id) is False


def test_index_json_is_valid_json(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    rec.start(label="meeting")
    rec.stop()
    raw = (tmp_path / "index.json").read_text()
    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["label"] == "meeting"


def test_started_at_is_unix_epoch(tmp_path) -> None:
    rec = SessionRecorder(store=SessionStore(root=tmp_path))
    before = time.time()
    s = rec.start(label="coding")
    after = time.time()
    assert before <= s.started_at <= after
