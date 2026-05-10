"""Domain-knowledge system prompt + live-state injection for the Coach LLM.

Strategy: instead of giving the small local model real tool-calling (which
3B-class models do unreliably), we inject a current-state JSON block into
the system message before each turn. The model reads it and answers.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np

from nao import runtime
from nao.config import EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.process.frame import FocusFrame
from nao.state import Calibration, label_frame

DOMAIN_PRIMER = """\
You are NaoCoach, an assistant integrated with a live Muse-14B3 EEG pipeline \
running on the user's Mac. Be concise and pragmatic.

Domain knowledge:
- 4 EEG channels: TP9 (left ear), AF7 (left forehead), AF8 (right forehead), \
TP10 (right ear). Sampled at 256 Hz.
- Bands: delta (1-4 Hz, deep sleep / heavy artifact), theta (4-8 Hz, drowsy / \
mind-wandering), alpha (8-13 Hz, relaxed wakefulness, rises with eyes closed), \
beta (13-30 Hz, active concentration / anxiety), gamma (30-45 Hz, transient \
binding / reward bursts).
- Focus Coefficient F = beta / alpha. Higher F = more engaged. Lower F = more \
relaxed / internal. Eyes closed reliably drops F because alpha rises.
- Personal calibration is critical: raw F values vary 10x between individuals. \
A baseline of mean=0.30 std=0.29 is normal for one user; means and standard \
deviations are z-scored when labeling.
- Labels: deeply_focused (F z >= 1.0), engaged, neutral, resting, uncertain \
(any artifact flagged).
- Artifact flags: BLINK (sharp >150 uV deflection in AF7/AF8), JAW (high-frequency \
static across at least 3 channels), MOTION (head accel deviates >0.15g from gravity), \
BAD_CONTACT (any channel std <0.5 uV = flat-line, or >500 uV = saturated).
- Common fixes: flat AF7/AF8 -> reseat band 1cm higher onto bare forehead; flat \
TP9/TP10 -> push hair clear, press earpiece against mastoid bone; persistent JAW \
-> ask user to unclench; persistent MOTION -> sit still.

Style: factual, brief, no emojis, no preamble like "Sure!". When the user asks \
about their state, refer specifically to numbers in the current-state block.
"""


def _channel_quality(eeg: np.ndarray) -> list[dict[str, Any]]:
    """Per-channel std + simple verdict. eeg shape (n_samples, n_channels)."""
    out = []
    for i, name in enumerate(EEG_CHANNELS):
        std = float(np.std(eeg[:, i]))
        if std < 1.0:
            verdict = "FLAT"
        elif std < 5.0:
            verdict = "weak"
        elif std > 200.0:
            verdict = "noisy"
        else:
            verdict = "ok"
        out.append({"channel": name, "std_uv": round(std, 2), "verdict": verdict})
    return out


def current_state_block(history_seconds: float = 10.0) -> dict[str, Any]:
    """Snapshot for injection into LLM context."""
    frame: FocusFrame | None = runtime.latest_frame()
    cal = Calibration.load()
    block: dict[str, Any] = {
        "calibration": (
            {"mean_f": cal.mean_f, "std_f": cal.std_f, "n_samples": cal.n_samples}
            if cal else None
        ),
    }
    if frame is None:
        block["status"] = "pipeline_warmup"
        return block

    block["status"] = "live"
    block["current"] = {
        "focus_ema": round(frame.focus_ema, 3),
        "focus_raw": round(frame.focus, 3),
        "alpha": round(frame.alpha, 3),
        "beta": round(frame.beta, 3),
        "theta": round(frame.theta, 3),
        "delta": round(frame.delta, 3),
        "gamma": round(frame.gamma, 3),
        "label": label_frame(frame, cal),
        "artifact_flags": frame.artifact,
        "artifact_clean": frame.artifact_clean,
        "latency_ms": round(frame.latency_ms, 2),
    }

    recent = runtime.recent_frames(history_seconds)
    if recent:
        focuses = [f.focus_ema for f in recent]
        block["recent"] = {
            "window_s": history_seconds,
            "frames": len(recent),
            "focus_mean": round(float(np.mean(focuses)), 3),
            "focus_min": round(float(np.min(focuses)), 3),
            "focus_max": round(float(np.max(focuses)), 3),
            "artifact_rate": round(
                sum(0 if f.artifact_clean else 1 for f in recent) / len(recent), 3
            ),
        }

    pipeline = runtime.get_pipeline()
    win = pipeline.latest_window(SAMPLE_RATE_HZ)
    if win is not None:
        eeg, _accel, _ts = win
        block["signal_quality"] = _channel_quality(eeg)

    return block


def build_system_prompt(history_seconds: float = 10.0) -> str:
    state = current_state_block(history_seconds)
    return (
        DOMAIN_PRIMER
        + "\n\n# Current EEG state (refreshes per turn):\n```json\n"
        + json.dumps(state, indent=2)
        + "\n```"
    )


SESSION_PRIMER_ADDENDUM = """\

You are reviewing a *finished* recording session, not the live stream. Use ONLY \
the digest below to answer. Don't speculate about timestamps, durations, or \
events that aren't present in the digest.

Reading the digest:
- summary: aggregate stats over the whole session.
- timeline: ~30 evenly-spaced bins; t_minute is minutes since session start.
- quartiles: focus_mean per quarter (q1..q4) — fast read on whether focus held \
or decayed.
- biggest_drop: lowest-focus bin and its delta vs the session mean.
- trend_slope_per_min: linear slope of focus_ema (>0 warming up, <0 fading).
- vs_calibration: where session focus_mean sits in the user's personal \
z-distribution.
- vs_label_baseline: comparison to past sessions of the same label, if any.

Answer pattern: cite specific numbers from the digest ("around 38 minutes \
your focus dropped to 0.4, your session-low") and tie them to the user's \
question. Suggest concrete tactics the user can act on. Don't invent advice \
that the data doesn't support.
"""


def build_session_system_prompt(session_digest: dict[str, Any]) -> str:
    """System prompt for Coach turns scoped to a specific past session."""
    return (
        DOMAIN_PRIMER
        + SESSION_PRIMER_ADDENDUM
        + "\n\n# Session digest:\n```json\n"
        + json.dumps(session_digest, indent=2, default=float)
        + "\n```"
    )
