"""Verdict — a 1-sentence natural-language read of the current FocusFrame.

The Now tab and menu-bar render this directly. Rule-based on purpose: the
LLM is reserved for Coach Q&A. A deterministic verdict means the user always
gets the same read for the same state — predictable, debuggable, free.

Decision order (first match wins):
    1. Bad contact → fix the band
    2. Transient artifacts (BLINK / JAW) → wait
    3. Trending down with prior calm-focus → fading, suggest break
    4. High arousal + negative asymmetry → alert-but-stressed, suggest breath
    5. Label-based default with optional trend qualifier
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nao.process.frame import FocusFrame
from nao.state import Calibration, label_frame

Tone = Literal["focused", "ok", "fading", "noisy", "alert", "calm"]


@dataclass(frozen=True, slots=True)
class Verdict:
    headline: str        # one short sentence — the answer
    detail: str          # one sentence — why I think this
    action: str          # one sentence — what to do (may be empty)
    tone: Tone           # drives UI color


_TREND_WINDOW = 12   # ~3 s at 4 Hz emit cadence
_TREND_DROP = 0.25   # focus_ema drop vs trailing median to flag fading


def _trend(history: list[FocusFrame]) -> float:
    """Recent change in focus_ema. Positive = rising, negative = falling.

    Uses median of the prior half vs latest sample so single-frame spikes
    don't flip the verdict.
    """
    clean = [f for f in history[-_TREND_WINDOW:] if f.artifact_clean]
    if len(clean) < 4:
        return 0.0
    half = max(2, len(clean) // 2)
    prior = sorted(f.focus_ema for f in clean[:half])
    prior_med = prior[len(prior) // 2]
    return clean[-1].focus_ema - prior_med


def verdict(
    frame: FocusFrame,
    calibration: Calibration | None = None,
    history: list[FocusFrame] | None = None,
) -> Verdict:
    """Return a one-line verdict for the given frame.

    `history` is the recent FocusFrame buffer (~last 30 s). Without it we
    skip the trend qualifier but still produce a coherent read.
    """
    history = history or []

    # 1. Bad contact — fix the band first; nothing else matters.
    if "BAD_CONTACT" in frame.artifact:
        return Verdict(
            headline="Bad sensor contact.",
            detail="One or more electrodes are flat or noisy.",
            action="Reseat the band — the per-channel panel below shows which to fix.",
            tone="noisy",
        )

    # 2. Transient artifacts — short wait, not a real reading.
    if any(a in frame.artifact for a in ("BLINK", "JAW", "MOTION")):
        which = next(a for a in ("BLINK", "JAW", "MOTION") if a in frame.artifact)
        return Verdict(
            headline="Wait a few seconds.",
            detail=f"{which.lower()} artifacts in the last window.",
            action="Hold still and unclench — the read will settle.",
            tone="noisy",
        )

    label = label_frame(frame, calibration)
    trend_delta = _trend(history)
    fading = trend_delta < -_TREND_DROP

    # 3. Fading from prior focus → suggest break before crash.
    if fading and label in ("engaged", "neutral"):
        return Verdict(
            headline="Focus fading.",
            detail="Frontal β/α has drifted down over the last few seconds.",
            action="Stand up, look out a window, 90 seconds. Then re-engage.",
            tone="fading",
        )

    # 4. Alert-but-stressed: high arousal + leftward asymmetry (withdrawal).
    arousal = frame.arousal_index or 0.0
    asym = frame.frontal_asymmetry or 0.0
    if arousal > 1.6 and asym < -0.05:
        return Verdict(
            headline="Alert but tense.",
            detail="High arousal with leftward frontal α (withdrawal axis).",
            action="One slow exhale, twice as long as the inhale.",
            tone="alert",
        )

    # 5. Label-based defaults — the steady-state read.
    if label == "deeply_focused":
        return Verdict(
            headline="In flow. Don't context-switch.",
            detail="β/α well above your baseline, signal clean.",
            action="Notifications are held. Ride it out.",
            tone="focused",
        )
    if label == "engaged":
        return Verdict(
            headline="Working well.",
            detail="Engaged but not maxed — sustainable for a while.",
            action="Keep going; check in again in 15 min.",
            tone="ok",
        )
    if label == "neutral":
        return Verdict(
            headline="Coasting.",
            detail="Mid-range β/α — neither focused nor resting.",
            action="Pick a clearer task or take a real break — the middle is the worst place to stay.",
            tone="ok",
        )
    if label == "resting":
        return Verdict(
            headline="Resting.",
            detail="Low β/α, dominant α — relaxed wakeful state.",
            action="Good for reading, planning, or stepping away.",
            tone="calm",
        )
    return Verdict(
        headline="Reading uncertain.",
        detail="Signal mixed; can't classify confidently.",
        action="Give it a few seconds, or recalibrate.",
        tone="noisy",
    )
