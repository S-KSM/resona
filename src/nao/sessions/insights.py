"""SessionInsights — temporal digest of a finished session for Coach LLM.

Strategy mirrors the live `current_state_block` pattern: instead of giving the
model a tool to query the JSONL, we precompute a compact dict of
(timeline + summary + comparisons) and inject it as JSON in the system prompt.
The model reasons over the digest, not the raw frames.

Why a digest instead of dumping every frame:
- A 1-hour session = ~14k frames = ~3 MB of JSON. Useless context bloat.
- The interesting structure is in temporal aggregates (per-quarter means,
  drift slope, biggest dip), not individual 250 ms windows.
- The model can't compute trends reliably from raw arrays anyway.

Fields produced:
- summary: cached SessionSummary (mean focus, alpha, etc.)
- timeline: focus_ema + asymmetry binned to ~30 windows over the session
- quartiles: focus_mean per quarter (Q1..Q4) — answers "did focus decay?"
- biggest_drop: t_minute + value of the lowest 30 s window — "where did I lose it?"
- trend_slope_per_min: linear slope of focus_ema over session minutes
- vs_calibration: where session focus_mean sits in user's z-distribution
- vs_label_baseline: same vs sessions of the same label (when ≥1 prior exists)
"""
from __future__ import annotations

from typing import Any

import numpy as np

from nao.process.frame import FocusFrame
from nao.sessions.models import Session
from nao.sessions.store import SessionStore
from nao.state import Calibration

TIMELINE_BINS = 30  # → ~30 buckets per session, regardless of duration


def _bin_frames(frames: list[FocusFrame], bins: int) -> list[dict[str, Any]]:
    """Split frames into `bins` equal-time buckets, return per-bin stats.

    Buckets are by index, not by ts — protects against ts gaps from artifact
    drops and avoids needing a uniform stride. For >30s sessions the user
    wouldn't notice index vs time bucketing.
    """
    if not frames:
        return []
    n = len(frames)
    bins = max(1, min(bins, n))
    edges = np.linspace(0, n, bins + 1, dtype=int)
    out: list[dict[str, Any]] = []
    t0 = frames[0].ts
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        chunk = frames[lo:hi]
        clean = [f for f in chunk if f.artifact_clean]
        focuses = [f.focus_ema for f in clean]
        asyms = [f.frontal_asymmetry for f in clean if f.frontal_asymmetry is not None]
        arousal = [f.arousal_index for f in clean if f.arousal_index is not None]
        bin_dict = {
            "t_minute": round((chunk[len(chunk) // 2].ts - t0) / 60.0, 2),
            "n": len(chunk),
            "n_clean": len(clean),
            "focus_mean": round(float(np.mean(focuses)), 3) if focuses else None,
            "asymmetry_mean": round(float(np.mean(asyms)), 3) if asyms else None,
            "arousal_mean": round(float(np.mean(arousal)), 3) if arousal else None,
            "artifact_rate": round(
                (len(chunk) - len(clean)) / len(chunk), 3
            ) if chunk else 0.0,
        }
        out.append(bin_dict)
    return out


def _quartile_focus(frames: list[FocusFrame]) -> dict[str, float | None]:
    """Mean focus_ema in each of the 4 even-time quarters. Trend at a glance."""
    if len(frames) < 4:
        return {"q1": None, "q2": None, "q3": None, "q4": None}
    edges = np.linspace(0, len(frames), 5, dtype=int)
    out: dict[str, float | None] = {}
    for idx, key in enumerate(("q1", "q2", "q3", "q4")):
        chunk = [
            f for f in frames[edges[idx]:edges[idx + 1]] if f.artifact_clean
        ]
        out[key] = round(float(np.mean([f.focus_ema for f in chunk])), 3) if chunk else None
    return out


def _biggest_drop(timeline: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Lowest-focus bin, with delta vs the session's overall mean."""
    valid = [b for b in timeline if b.get("focus_mean") is not None]
    if len(valid) < 2:
        return None
    overall = float(np.mean([b["focus_mean"] for b in valid]))
    lowest = min(valid, key=lambda b: b["focus_mean"])
    return {
        "t_minute": lowest["t_minute"],
        "focus_mean": lowest["focus_mean"],
        "delta_vs_session_mean": round(lowest["focus_mean"] - overall, 3),
    }


def _trend_slope(frames: list[FocusFrame]) -> float | None:
    """Linear slope of focus_ema over session minutes. >0 = warming up,
    <0 = decay. Returns None if not enough clean frames."""
    clean = [f for f in frames if f.artifact_clean]
    if len(clean) < 10:
        return None
    t0 = clean[0].ts
    xs = np.array([(f.ts - t0) / 60.0 for f in clean])
    ys = np.array([f.focus_ema for f in clean])
    if xs[-1] - xs[0] < 0.1:  # too short to fit a slope
        return None
    slope, _ = np.polyfit(xs, ys, 1)
    return round(float(slope), 4)


def _vs_calibration(focus_mean: float | None) -> dict[str, Any] | None:
    if focus_mean is None:
        return None
    cal = Calibration.load()
    if cal is None:
        return None
    return {
        "z_score": round(cal.zscore(focus_mean), 2),
        "user_mean_f": round(cal.mean_f, 3),
        "user_std_f": round(cal.std_f, 3),
    }


def _vs_label_baseline(
    session: Session, store: SessionStore
) -> dict[str, Any] | None:
    """Compare focus_mean to mean of past finalized sessions with same label."""
    others = [
        s for s in store.list_sessions()
        if s.label == session.label
        and s.id != session.id
        and not s.is_active
        and s.summary.focus_mean is not None
    ]
    if not others:
        return None
    means = [s.summary.focus_mean for s in others]
    baseline = float(np.mean(means))  # type: ignore[arg-type]
    delta = (
        round(session.summary.focus_mean - baseline, 3)
        if session.summary.focus_mean is not None
        else None
    )
    return {
        "label": session.label,
        "n_prior": len(others),
        "label_focus_mean": round(baseline, 3),
        "delta": delta,
    }


def build_insights(session: Session, store: SessionStore) -> dict[str, Any]:
    """Top-level. Reads jsonl once, returns a Coach-ready digest."""
    frames = store.read_frames(session.id)
    timeline = _bin_frames(frames, TIMELINE_BINS)
    return {
        "id": session.id,
        "label": session.label,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "notes": session.notes,
        "summary": session.summary.model_dump(),
        "timeline": timeline,
        "quartiles": _quartile_focus(frames),
        "biggest_drop": _biggest_drop(timeline),
        "trend_slope_per_min": _trend_slope(frames),
        "vs_calibration": _vs_calibration(session.summary.focus_mean),
        "vs_label_baseline": _vs_label_baseline(session, store),
    }
