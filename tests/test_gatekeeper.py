"""Gatekeeper agent — pure logic + FSM behavior.

Covers the SPECS Phase-2 advisory `should_interrupt(urgency)` decision:
- policy table for every (label x urgency)
- fail-open guards (artifact / signal_uncertain)
- frontal_focus helper (AF7/AF8 mean)
- FSM hysteresis (enter / exit / single-frame ignored)
- BAD_CONTACT streak forces OPEN
- queue / release semantics
- manual override stickiness
- decide() latency budget
"""
from __future__ import annotations

import time
from typing import Iterable
from unittest.mock import patch

import pytest

from nao.agents.gatekeeper import (
    Decision,
    GatekeeperFSM,
    decide,
    frontal_focus,
)
from nao.config import EEG_CHANNELS
from nao.process.frame import FocusFrame
from nao.state import CognitiveLoad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame(
    *,
    ts: float = 0.0,
    focus: float = 1.0,
    artifact: list[str] | None = None,
    clean: bool | None = None,
    alpha_per_channel: list[float] | None = None,
    beta_per_channel: list[float] | None = None,
) -> FocusFrame:
    """Build a minimal FocusFrame for tests."""
    arts = artifact or []
    if clean is None:
        clean = len(arts) == 0
    return FocusFrame(
        ts=ts,
        alpha=1.0,
        beta=focus,
        theta=0.0,
        delta=0.0,
        gamma=0.0,
        focus=focus,
        focus_ema=focus,
        artifact=arts,
        artifact_clean=clean,
        latency_ms=1.0,
        alpha_per_channel=alpha_per_channel,
        beta_per_channel=beta_per_channel,
    )


def _stream(
    fsm: GatekeeperFSM,
    *,
    start_ts: float,
    duration_s: float,
    step_s: float = 0.25,
    focus: float = 3.0,
    artifact: Iterable[str] | None = None,
) -> float:
    """Push a sequence of frames at fixed cadence; return the last ts emitted."""
    arts = list(artifact) if artifact is not None else []
    ts = start_ts
    end = start_ts + duration_s
    last = start_ts
    while ts <= end + 1e-9:
        fsm.on_frame(_frame(ts=ts, focus=focus, artifact=arts))
        last = ts
        ts += step_s
    return last


# ---------------------------------------------------------------------------
# policy.decide — table-driven for every (label, urgency)
# ---------------------------------------------------------------------------

LABELS: list[CognitiveLoad] = [
    "deeply_focused",
    "engaged",
    "neutral",
    "resting",
    "uncertain",
]
URGENCIES = ["low", "medium", "high"]

# Expected (allow, defer_seconds) per (label, urgency). None for defer
# means "no defer requested".
_EXPECTED: dict[tuple[str, str], tuple[bool, float | None]] = {
    ("deeply_focused", "high"): (True, None),
    ("deeply_focused", "medium"): (False, 60.0),
    ("deeply_focused", "low"): (False, 300.0),
    ("engaged", "high"): (True, None),
    ("engaged", "medium"): (False, 30.0),
    ("engaged", "low"): (False, 180.0),
    ("neutral", "high"): (True, None),
    ("neutral", "medium"): (True, None),
    ("neutral", "low"): (True, None),
    ("resting", "high"): (True, None),
    ("resting", "medium"): (True, None),
    ("resting", "low"): (True, None),
    ("uncertain", "high"): (True, None),
    ("uncertain", "medium"): (True, None),
    ("uncertain", "low"): (True, None),
}


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("urgency", URGENCIES)
def test_decide_policy_table(label: CognitiveLoad, urgency: str) -> None:
    expect_allow, expect_defer = _EXPECTED[(label, urgency)]
    d = decide(label, urgency, artifact_clean=True, signal_uncertain=False)  # type: ignore[arg-type]
    assert isinstance(d, Decision)
    assert d.allow is expect_allow, (label, urgency, d)
    assert d.defer_seconds == expect_defer, (label, urgency, d)
    assert d.label == label


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("urgency", URGENCIES)
def test_decide_artifact_forces_failopen(label: CognitiveLoad, urgency: str) -> None:
    d = decide(label, urgency, artifact_clean=False, signal_uncertain=False)  # type: ignore[arg-type]
    assert d.allow is True
    assert d.reason == "signal_uncertain"
    assert d.defer_seconds is None


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("urgency", URGENCIES)
def test_decide_signal_uncertain_forces_failopen(label: CognitiveLoad, urgency: str) -> None:
    d = decide(label, urgency, artifact_clean=True, signal_uncertain=True)  # type: ignore[arg-type]
    assert d.allow is True
    assert d.reason == "signal_uncertain"


# ---------------------------------------------------------------------------
# frontal_focus
# ---------------------------------------------------------------------------


def test_frontal_focus_returns_none_without_per_channel() -> None:
    f = _frame(focus=1.5)
    assert f.alpha_per_channel is None
    assert frontal_focus(f) is None


def test_frontal_focus_returns_none_when_only_alpha_present() -> None:
    f = _frame(focus=1.5, alpha_per_channel=[1.0, 1.0, 1.0, 1.0])
    assert frontal_focus(f) is None


def test_frontal_focus_uses_af7_af8_mean() -> None:
    # Channels: TP9, AF7, AF8, TP10. Frontal beta avg=2, alpha avg=1 -> 2.0.
    # If the function mistakenly averaged all 4, alpha=(1+1+9+9)/4=5,
    # beta=(0+2+2+0)/4=1, ratio=0.2 — clearly distinguishable.
    f = _frame(
        alpha_per_channel=[1.0, 1.0, 1.0, 9.0],  # AF7=1, AF8=1
        beta_per_channel=[0.0, 2.0, 2.0, 0.0],  # AF7=2, AF8=2
    )
    ff = frontal_focus(f)
    assert ff is not None
    assert ff == pytest.approx(2.0)
    assert EEG_CHANNELS.index("AF7") == 1
    assert EEG_CHANNELS.index("AF8") == 2


def test_frontal_focus_handles_zero_alpha_without_div0() -> None:
    f = _frame(
        alpha_per_channel=[0.0, 0.0, 0.0, 0.0],
        beta_per_channel=[0.0, 1.0, 1.0, 0.0],
    )
    ff = frontal_focus(f)
    assert ff is not None
    assert ff > 0.0  # eps clamp -> very large but finite


def test_frontal_focus_prefers_precomputed_field() -> None:
    """When Pipeline populates frame.frontal_focus, the helper should read
    it directly instead of recomputing from per_channel arrays."""
    f = _frame(
        alpha_per_channel=[1.0, 1.0, 1.0, 1.0],
        beta_per_channel=[1.0, 1.0, 1.0, 1.0],
    )
    # Simulate Pipeline pre-write — value distinct from what per_channel would yield.
    f = f.model_copy(update={"frontal_focus": 42.0, "frontal_focus_ema": 41.0})
    assert frontal_focus(f) == 42.0


# ---------------------------------------------------------------------------
# FSM hysteresis
# ---------------------------------------------------------------------------


def test_fsm_starts_open() -> None:
    fsm = GatekeeperFSM()
    assert fsm.state == "OPEN"
    assert fsm.quiet is False


def test_fsm_does_not_enter_quiet_on_single_focused_frame() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0)
    fsm.on_frame(_frame(ts=0.0, focus=3.0))
    assert fsm.state == "OPEN"


def test_fsm_enters_quiet_after_sustained_focused_stream() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0)
    # 13s of deeply-focused frames at 4 Hz cadence — comfortably past threshold.
    _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET", fsm.status()
    assert fsm.status()["since_ts"] is not None


def test_fsm_does_not_enter_quiet_just_before_threshold() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0)
    # Stop a hair before 12s of streak: streak measures (last_ts - first_ts).
    _stream(fsm, start_ts=0.0, duration_s=10.0, step_s=0.25, focus=3.0)
    assert fsm.state == "OPEN"


def test_fsm_exits_quiet_after_sustained_sub_engaged_stream() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0, exit_seconds=8.0)
    last = _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET"
    # Now feed sub-engaged (low focus -> "resting") for 9s.
    _stream(fsm, start_ts=last + 0.25, duration_s=9.0, step_s=0.25, focus=0.3)
    assert fsm.state == "OPEN", fsm.status()


def test_fsm_focus_dip_does_not_immediately_exit_quiet() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0, exit_seconds=8.0)
    last = _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET"
    # One sub-engaged frame mid-flight should not flip us back.
    fsm.on_frame(_frame(ts=last + 0.25, focus=0.3))
    assert fsm.state == "QUIET"


def test_fsm_bad_contact_streak_forces_open_and_signal_uncertain() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0, bad_contact_streak_s=5.0)
    # Get to QUIET first.
    last = _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET"
    # Now stream BAD_CONTACT for >= 5s.
    last = _stream(
        fsm,
        start_ts=last + 0.25,
        duration_s=6.0,
        step_s=0.25,
        focus=3.0,
        artifact=["BAD_CONTACT"],
    )
    assert fsm.state == "OPEN", fsm.status()
    # And decide() should fail-open with reason signal_uncertain.
    d = fsm.decide("low")
    assert d.allow is True
    assert d.reason == "signal_uncertain"


def test_fsm_brief_bad_contact_does_not_force_open() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0, bad_contact_streak_s=5.0)
    last = _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET"
    # 1s blip of BAD_CONTACT — under threshold.
    _stream(
        fsm,
        start_ts=last + 0.25,
        duration_s=1.0,
        step_s=0.25,
        focus=3.0,
        artifact=["BAD_CONTACT"],
    )
    assert fsm.state == "QUIET", fsm.status()


# ---------------------------------------------------------------------------
# Queueing
# ---------------------------------------------------------------------------


def test_queue_release_returns_pings_in_order_and_clears() -> None:
    fsm = GatekeeperFSM()
    ids = [
        fsm.queue("slack", "msg 1", "low"),
        fsm.queue("mail", "msg 2", "medium"),
        fsm.queue("calendar", "msg 3", "low"),
    ]
    # Simulate transition to OPEN; in real code the runtime calls release_queued
    # on QUIET->OPEN. We're testing the method itself.
    released = fsm.release_queued()
    assert [p.id for p in released] == ids
    assert [p.source for p in released] == ["slack", "mail", "calendar"]
    assert fsm.release_queued() == []
    assert fsm.status()["queued_count"] == 0


def test_peek_queued_returns_fifo_without_draining() -> None:
    fsm = GatekeeperFSM()
    fsm.queue("slack", "msg 1", "low")
    fsm.queue("mail", "msg 2", "medium")
    peeked = fsm.peek_queued()
    assert [p.source for p in peeked] == ["slack", "mail"]
    # Peek must not mutate the queue.
    assert fsm.status()["queued_count"] == 2
    assert [p.source for p in fsm.peek_queued()] == ["slack", "mail"]
    # Returned list is a copy — mutations don't bleed back.
    peeked.clear()
    assert fsm.status()["queued_count"] == 2


def test_queue_drops_oldest_when_full() -> None:
    fsm = GatekeeperFSM()
    # Push more than the bounded maxlen (50) and confirm we never explode and
    # only retain the most-recent 50.
    for i in range(60):
        fsm.queue(f"src-{i}", f"msg-{i}", "low")
    released = fsm.release_queued()
    assert len(released) == 50
    # Oldest 10 should have been dropped.
    sources = [p.source for p in released]
    assert sources[0] == "src-10"
    assert sources[-1] == "src-59"


# ---------------------------------------------------------------------------
# Manual override
# ---------------------------------------------------------------------------


def test_manual_override_open_sticks_for_60s() -> None:
    fsm = GatekeeperFSM(enter_seconds=12.0)
    # Drive FSM into QUIET via frames.
    _stream(fsm, start_ts=0.0, duration_s=13.0, step_s=0.25, focus=3.0)
    assert fsm.state == "QUIET"

    # User says OPEN — for 60s monotonic seconds.
    t0 = time.monotonic()
    with patch("nao.agents.gatekeeper.fsm.time.monotonic", return_value=t0):
        fsm.manual_override("OPEN")
    # Just before 60s — still overridden.
    with patch("nao.agents.gatekeeper.fsm.time.monotonic", return_value=t0 + 59.0):
        assert fsm.state == "OPEN"
        d = fsm.decide("low")
        assert d.allow is True
        assert d.reason == "manual_override_open"
    # After 60s — override expires, FSM resumes (still QUIET underneath).
    with patch("nao.agents.gatekeeper.fsm.time.monotonic", return_value=t0 + 61.0):
        assert fsm.state == "QUIET"


def test_manual_override_quiet_blocks_low_but_failopens_high() -> None:
    fsm = GatekeeperFSM()
    t0 = time.monotonic()
    with patch("nao.agents.gatekeeper.fsm.time.monotonic", return_value=t0):
        fsm.manual_override("QUIET")
    with patch("nao.agents.gatekeeper.fsm.time.monotonic", return_value=t0 + 5.0):
        assert fsm.state == "QUIET"
        assert fsm.decide("low").allow is False
        assert fsm.decide("high").allow is True


# ---------------------------------------------------------------------------
# Latency budget
# ---------------------------------------------------------------------------


def test_decide_latency_under_50us_avg() -> None:
    fsm = GatekeeperFSM()
    # Warmup: prime the label by feeding one frame.
    fsm.on_frame(_frame(ts=0.0, focus=1.0))
    # 1000 calls.
    t0 = time.perf_counter()
    for _ in range(1000):
        fsm.decide("low")
    elapsed = time.perf_counter() - t0
    # Budget: <50ms total => <50us average.
    assert elapsed < 0.050, f"decide() too slow: {elapsed * 1000:.2f}ms / 1000 calls"


# ---------------------------------------------------------------------------
# Status snapshot
# ---------------------------------------------------------------------------


def test_status_shape() -> None:
    fsm = GatekeeperFSM()
    s = fsm.status()
    assert set(s.keys()) >= {
        "quiet",
        "since_ts",
        "queued_count",
        "last_label",
        "last_decision_reason",
    }
    assert s["quiet"] is False
    assert s["queued_count"] == 0
