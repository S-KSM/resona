"""Cognitive-state labeling thresholds + artifact gating."""
from __future__ import annotations

import pytest

from nao.process.frame import FocusFrame
from nao.state import Calibration, label_focus, label_frame


def _frame(focus: float, clean: bool = True, artifact: list[str] | None = None) -> FocusFrame:
    return FocusFrame(
        ts=0.0,
        alpha=1.0,
        beta=focus,
        theta=0.0,
        delta=0.0,
        gamma=0.0,
        focus=focus,
        focus_ema=focus,
        artifact=artifact or [],
        artifact_clean=clean,
        latency_ms=1.0,
    )


def test_label_focus_thresholds() -> None:
    assert label_focus(3.0) == "deeply_focused"
    assert label_focus(2.5) == "deeply_focused"
    assert label_focus(2.0) == "engaged"
    assert label_focus(1.0) == "neutral"
    assert label_focus(0.3) == "resting"


def test_artifact_forces_uncertain() -> None:
    f = _frame(focus=3.0, clean=False, artifact=["BLINK"])
    assert label_frame(f) == "uncertain"


def test_clean_focus_label() -> None:
    assert label_frame(_frame(focus=3.0)) == "deeply_focused"
    assert label_frame(_frame(focus=0.5)) == "resting"


def test_calibration_zscore_shifts_label() -> None:
    # User's personal mean=2.5 (high focus typical), std=0.5.
    cal = Calibration(mean_f=2.5, std_f=0.5, n_samples=1000)
    # Their raw F=2.5 -> z=0 -> shift+1.5 -> 1.5 -> "engaged" (relative neutral).
    assert label_frame(_frame(focus=2.5), cal) == "engaged"
    # F=3.5 -> z=2 -> 3.5 -> "deeply_focused".
    assert label_frame(_frame(focus=3.5), cal) == "deeply_focused"


def test_calibration_save_load_roundtrip(tmp_path) -> None:
    p = tmp_path / "baseline.json"
    cal = Calibration(mean_f=1.7, std_f=0.4, n_samples=240)
    cal.save(p)
    loaded = Calibration.load(p)
    assert loaded == cal


def test_calibration_age_and_stale() -> None:
    now = 1_700_000_000.0  # arbitrary fixed epoch
    fresh = Calibration(mean_f=1.0, std_f=0.5, n_samples=10, saved_at=now - 86400.0)  # 1 day
    stale = Calibration(mean_f=1.0, std_f=0.5, n_samples=10, saved_at=now - 8 * 86400.0)
    legacy = Calibration(mean_f=1.0, std_f=0.5, n_samples=10, saved_at=None)
    assert fresh.age_days(now=now) == pytest.approx(1.0)
    assert stale.age_days(now=now) == pytest.approx(8.0)
    assert legacy.age_days(now=now) is None
    assert not fresh.is_stale(now=now)
    assert stale.is_stale(now=now)
    assert not legacy.is_stale(now=now)  # unknown age -> don't nag


def test_calibration_loads_legacy_file_without_saved_at(tmp_path) -> None:
    """A baseline.json written by an older nao-calibrate has no saved_at key.
    Must load cleanly with saved_at=None and report unknown age."""
    p = tmp_path / "baseline.json"
    p.write_text('{"mean_f": 1.7, "std_f": 0.4, "n_samples": 240}')
    cal = Calibration.load(p)
    assert cal is not None
    assert cal.saved_at is None
    assert cal.age_days() is None
    assert not cal.is_stale()
