"""Session insights digest — temporal binning + summary derivation."""
from __future__ import annotations

import time

import pytest

from nao.process.frame import FocusFrame
from nao.sessions.insights import build_insights
from nao.sessions.recorder import SessionRecorder
from nao.sessions.store import SessionStore


def _frame(focus: float, ts: float, *, clean: bool = True, asym: float = 0.0) -> FocusFrame:
    return FocusFrame(
        ts=ts,
        alpha=1.0,
        beta=focus,
        theta=0.0,
        delta=0.0,
        gamma=0.0,
        focus=focus,
        focus_ema=focus,
        artifact=[] if clean else ["BLINK"],
        artifact_clean=clean,
        latency_ms=1.0,
        frontal_asymmetry=asym,
        arousal_index=2.0,
    )


def _record_session(
    tmp_path, label: str, focus_curve: list[float]
) -> tuple[SessionStore, str]:
    """Helper: build a session of len(focus_curve) clean frames at 1-sec spacing."""
    store = SessionStore(root=tmp_path)
    rec = SessionRecorder(store=store)
    rec.start(label=label)
    t0 = time.time()
    for i, f in enumerate(focus_curve):
        rec.on_frame(_frame(focus=f, ts=t0 + i))
    s = rec.stop()
    assert s is not None
    return store, s.id


def test_insights_basic_shape(tmp_path) -> None:
    store, sid = _record_session(tmp_path, "deep_work", [1.0] * 100)
    s = store.get(sid)
    assert s is not None
    digest = build_insights(s, store)
    assert digest["id"] == sid
    assert digest["label"] == "deep_work"
    assert isinstance(digest["timeline"], list)
    assert len(digest["timeline"]) <= 30
    assert digest["timeline"][0]["focus_mean"] == 1.0
    assert digest["quartiles"]["q1"] == 1.0
    assert digest["quartiles"]["q4"] == 1.0
    assert digest["trend_slope_per_min"] is not None


def test_insights_detects_decay(tmp_path) -> None:
    # Linear decay 2.0 → 0.5 over 200 frames.
    curve = list(2.0 - (1.5 * i / 199.0) for i in range(200))
    store, sid = _record_session(tmp_path, "coding", curve)
    s = store.get(sid)
    digest = build_insights(s, store)  # type: ignore[arg-type]
    assert digest["quartiles"]["q1"] > digest["quartiles"]["q4"]
    assert digest["trend_slope_per_min"] is not None
    assert digest["trend_slope_per_min"] < 0  # decay
    drop = digest["biggest_drop"]
    assert drop is not None
    # Lowest bin near end of session.
    assert drop["t_minute"] >= 2.0  # ≥ 2 min into a 200-second session


def test_insights_biggest_drop_vs_session_mean(tmp_path) -> None:
    # Steady high focus with one deep dip in the middle.
    curve = [2.0] * 90 + [0.2] * 20 + [2.0] * 90
    store, sid = _record_session(tmp_path, "reading", curve)
    s = store.get(sid)
    digest = build_insights(s, store)  # type: ignore[arg-type]
    drop = digest["biggest_drop"]
    assert drop is not None
    assert drop["delta_vs_session_mean"] < -0.5
    # The dip is in the middle (~50%) of a 200-second session.
    assert 1.0 < drop["t_minute"] < 2.5


def test_insights_label_baseline_compares_against_prior(tmp_path) -> None:
    # First reading session: focus=1.0
    store, _ = _record_session(tmp_path, "reading", [1.0] * 60)
    # Second reading session: focus=2.0 — expect delta=+1.0
    rec = SessionRecorder(store=store)
    rec.start(label="reading")
    t0 = time.time()
    for i in range(60):
        rec.on_frame(_frame(focus=2.0, ts=t0 + i))
    s = rec.stop()
    digest = build_insights(s, store)  # type: ignore[arg-type]
    vs = digest["vs_label_baseline"]
    assert vs is not None
    assert vs["n_prior"] == 1
    assert vs["delta"] == pytest.approx(1.0, abs=0.05)


def test_insights_no_label_baseline_when_first_of_kind(tmp_path) -> None:
    store, sid = _record_session(tmp_path, "meeting", [1.0] * 40)
    s = store.get(sid)
    digest = build_insights(s, store)  # type: ignore[arg-type]
    assert digest["vs_label_baseline"] is None


def test_insights_handles_short_session(tmp_path) -> None:
    # Below 10 clean frames → trend_slope is None.
    store, sid = _record_session(tmp_path, "rest", [1.0, 1.1, 0.9])
    s = store.get(sid)
    digest = build_insights(s, store)  # type: ignore[arg-type]
    assert digest["trend_slope_per_min"] is None
    assert digest["timeline"]  # still produces 3 bins


def test_insights_artifact_rate_per_bin(tmp_path) -> None:
    # 50% dirty frames evenly distributed.
    store = SessionStore(root=tmp_path)
    rec = SessionRecorder(store=store)
    rec.start(label="other")
    t0 = time.time()
    for i in range(60):
        rec.on_frame(_frame(focus=1.0, ts=t0 + i, clean=(i % 2 == 0)))
    s = rec.stop()
    digest = build_insights(s, store)  # type: ignore[arg-type]
    rates = [b["artifact_rate"] for b in digest["timeline"]]
    assert all(0.3 <= r <= 0.7 for r in rates)
