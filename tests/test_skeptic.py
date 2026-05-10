"""Skeptic agent — pure logic + FSM behavior.

Mirrors the Gatekeeper test layout. Covers:
  - frontal_gamma helper (per-channel preferred; channel-averaged fallback)
  - Welford running stats (smoke)
  - Spike detection vs baseline z
  - Warmup gate (no spikes before baseline_n samples)
  - Refractory window
  - Artifact gating (clean frames only fold into baseline; dirty frames yield None)
  - Recent-window math + policy.advise integration
"""
from __future__ import annotations

import pytest

from nao.agents.skeptic import (
    AppraisalAdvice,
    SkepticFSM,
    advise,
    frontal_gamma,
    frontal_gamma_from_powers,
)
from nao.process.frame import FocusFrame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame(
    *,
    ts: float = 0.0,
    gamma: float = 1.0,
    gamma_per_channel: list[float] | None = None,
    clean: bool = True,
    artifact: list[str] | None = None,
) -> FocusFrame:
    arts = artifact or []
    return FocusFrame(
        ts=ts,
        alpha=1.0,
        beta=1.0,
        theta=1.0,
        delta=1.0,
        gamma=gamma,
        focus=1.0,
        focus_ema=1.0,
        artifact=arts,
        artifact_clean=clean,
        latency_ms=1.0,
        gamma_per_channel=gamma_per_channel,
    )


# ---------------------------------------------------------------------------
# detector.frontal_gamma
# ---------------------------------------------------------------------------


def test_frontal_gamma_uses_af7_af8_mean() -> None:
    f = _frame(gamma=99.0, gamma_per_channel=[0.0, 4.0, 6.0, 0.0])
    # AF7=4, AF8=6 -> mean 5. Channel-averaged frame.gamma=99 must be ignored.
    assert frontal_gamma(f) == 5.0


def test_frontal_gamma_falls_back_to_channel_avg() -> None:
    f = _frame(gamma=3.5)
    assert f.gamma_per_channel is None
    assert frontal_gamma(f) == 3.5


def test_frontal_gamma_from_powers_short_array_returns_none() -> None:
    assert frontal_gamma_from_powers([1.0, 2.0]) is None  # length <= AF8 idx
    assert frontal_gamma_from_powers(None) is None


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------


def test_no_spike_before_warmup_threshold() -> None:
    fsm = SkepticFSM(warmup_n=10, z_threshold=2.0)
    # Send 5 clean baseline frames at gamma=1.0 plus one huge gamma=100.
    for i in range(5):
        assert fsm.on_frame(_frame(ts=float(i), gamma=1.0)) is None
    # Even a wildly elevated gamma should not produce a spike before warmup.
    assert fsm.on_frame(_frame(ts=5.0, gamma=100.0)) is None
    assert fsm.state()["baseline_n"] == 6
    assert fsm.state()["recent_spike"] is False


# ---------------------------------------------------------------------------
# Spike detection
# ---------------------------------------------------------------------------


def test_detects_spike_above_z_threshold() -> None:
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0, refractory_s=2.0)
    # Build a baseline around 1.0 with small jitter.
    for i in range(40):
        jitter = 0.05 if (i % 2 == 0) else -0.05
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0 + jitter))
    # Now inject a clear outlier.
    spike = fsm.on_frame(_frame(ts=20.0, gamma=10.0))
    assert spike is not None
    assert spike.z > 2.0
    s = fsm.state()
    assert s["recent_spike"] is True
    assert s["since_spike_s"] == 0.0


def test_spike_does_not_pull_baseline_up_to_meet_itself() -> None:
    """A real spike must not be folded into the baseline mean."""
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0, refractory_s=0.0)
    for i in range(40):
        jitter = 0.05 if (i % 2 == 0) else -0.05
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0 + jitter))
    pre_mean = fsm.state()["baseline_mean"]
    spike = fsm.on_frame(_frame(ts=20.0, gamma=20.0))  # huge outlier
    assert spike is not None  # sanity
    post_mean = fsm.state()["baseline_mean"]
    assert pre_mean == post_mean


# ---------------------------------------------------------------------------
# Refractory
# ---------------------------------------------------------------------------


def test_refractory_window_suppresses_immediate_repeat() -> None:
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0, refractory_s=2.0)
    for i in range(40):
        jitter = 0.05 if (i % 2 == 0) else -0.05
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0 + jitter))
    assert fsm.on_frame(_frame(ts=20.0, gamma=10.0)) is not None
    # Same-ts and within-2s repeats must be suppressed.
    assert fsm.on_frame(_frame(ts=20.5, gamma=10.0)) is None
    assert fsm.on_frame(_frame(ts=21.0, gamma=10.0)) is None
    # After refractory expires, a new spike is allowed.
    assert fsm.on_frame(_frame(ts=23.0, gamma=10.0)) is not None


# ---------------------------------------------------------------------------
# Artifact gating
# ---------------------------------------------------------------------------


def test_dirty_frame_returns_none_and_does_not_extend_baseline() -> None:
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0)
    for i in range(20):
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0))
    pre = fsm.state()["baseline_n"]
    # Jaw clench would normally explode gamma — must not fold or trigger.
    spike = fsm.on_frame(
        _frame(ts=10.0, gamma=50.0, clean=False, artifact=["JAW_CLENCH"])
    )
    assert spike is None
    assert fsm.state()["baseline_n"] == pre


# ---------------------------------------------------------------------------
# state() snapshot
# ---------------------------------------------------------------------------


def _build_baseline(fsm: SkepticFSM, n: int = 40) -> None:
    """Fill baseline with small alternating jitter so std > 0."""
    for i in range(n):
        jitter = 0.05 if (i % 2 == 0) else -0.05
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0 + jitter))


def test_state_reports_since_spike_seconds() -> None:
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0, refractory_s=0.0)
    _build_baseline(fsm)
    spike = fsm.on_frame(_frame(ts=20.0, gamma=10.0))  # spike at t=20
    assert spike is not None
    fsm.on_frame(_frame(ts=25.0, gamma=1.0))   # 5s later, clean
    s = fsm.state()
    assert s["since_spike_s"] == pytest.approx(5.0)
    assert s["recent_spike"] is True


def test_state_recent_spike_window_expires() -> None:
    fsm = SkepticFSM(warmup_n=20, z_threshold=2.0, refractory_s=0.0, recent_window_s=10.0)
    _build_baseline(fsm)
    spike = fsm.on_frame(_frame(ts=20.0, gamma=10.0))  # spike
    assert spike is not None
    # Way past the recent window.
    fsm.on_frame(_frame(ts=40.0, gamma=1.0))
    s = fsm.state()
    assert s["recent_spike"] is False
    assert s["since_spike_s"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# policy.advise
# ---------------------------------------------------------------------------


def test_advise_no_spike_returns_no_caution() -> None:
    a = advise(recent_spike=False, since_spike_s=None)
    assert a == AppraisalAdvice(caution=False, cooldown_seconds=0.0, reason="no_recent_spike")


def test_advise_recent_spike_flags_caution_with_remaining_cooldown() -> None:
    a = advise(recent_spike=True, since_spike_s=5.0)
    assert a.caution is True
    assert a.reason == "recent_reward_spike"
    assert a.cooldown_seconds == pytest.approx(25.0)  # 30s window - 5s elapsed


def test_fsm_advise_integrates_with_policy() -> None:
    fsm = SkepticFSM(warmup_n=10, z_threshold=2.0)
    for i in range(20):
        jitter = 0.05 if (i % 2 == 0) else -0.05
        fsm.on_frame(_frame(ts=float(i) * 0.25, gamma=1.0 + jitter))
    spike = fsm.on_frame(_frame(ts=10.0, gamma=10.0))
    assert spike is not None
    a = fsm.advise()
    assert a.caution is True
    assert a.reason == "recent_reward_spike"
