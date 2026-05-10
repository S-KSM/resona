"""Calibrate — voice-guided 2-phase wizard, runs in a worker thread."""
from __future__ import annotations

import time
from collections import deque

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from nao.config import EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.dash._shared import get_config, get_pipeline
from nao.dash.calibration_worker import (
    CalibrationProgress,
    start_calibration_thread,
)


def _focus_chart(progress: CalibrationProgress) -> alt.Chart:
    rows = []
    for f in progress.eyes_open:
        rows.append({"ts": f.ts, "focus": f.focus, "phase": "eyes_open"})
    for f in progress.eyes_closed:
        rows.append({"ts": f.ts, "focus": f.focus, "phase": "eyes_closed"})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["t"] = df["ts"] - df["ts"].iloc[0]
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X("t:Q", title="seconds"),
            y=alt.Y("focus:Q", title="F = β/α"),
            color=alt.Color("phase:N", scale=alt.Scale(scheme="tableau10")),
        )
        .properties(height=240)
    )


def _phase_label(phase: str) -> str:
    return {
        "idle": "Ready",
        "eyes_open": "Eyes OPEN — look at screen",
        "eyes_closed": "Eyes CLOSED — relax",
        "saving": "Saving baseline…",
        "done": "Done",
        "error": "Error",
    }.get(phase, phase)


def render() -> None:
    st.title("Calibrate")
    st.caption(
        "Records ~2 minutes of EEG (eyes open + eyes closed) and z-scores future "
        "labels against your personal F. Voice guidance is on-device (macOS `say`)."
    )

    cfg = get_config()

    with st.sidebar:
        st.header("Calibration settings")
        seconds_per_phase = st.slider("Seconds per phase", 30, 120, 60, step=10)
        st.caption(f"Voice: **{cfg.voice_name}** @ {cfg.voice_rate} wpm. Change in Setup.")

    pipeline = get_pipeline()
    if cfg.last_source == "muse" and not cfg.effective_muse_address():
        st.error("Source is set to muse but no address saved. Visit **Setup**.")
        return

    progress: CalibrationProgress | None = st.session_state.get("calib_progress")

    cols = st.columns([1, 1, 1])
    if cols[0].button("Start calibration", type="primary",
                       disabled=progress is not None and progress.phase not in ("idle", "done", "error")):
        progress, _ = start_calibration_thread(
            pipeline=pipeline,
            seconds_per_phase=float(seconds_per_phase),
            voice_name=cfg.voice_name,
            voice_rate=cfg.voice_rate,
        )
        st.session_state.calib_progress = progress
        st.session_state.calib_focus_buffer = deque(maxlen=240)

    if cols[1].button("Cancel",
                       disabled=progress is None or progress.phase in ("idle", "done", "error")):
        if progress is not None:
            progress.cancel = True

    if cols[2].button("Reset state"):
        st.session_state.pop("calib_progress", None)
        st.rerun()

    if progress is None:
        st.info("Press **Start calibration**. Make sure you're seated, headband on, no jaw clench.")
        _signal_quality_preview(pipeline)
        return

    # ---- Live status ----
    phase = progress.phase
    st.subheader(_phase_label(phase))

    if phase in ("eyes_open", "eyes_closed"):
        st.progress(
            1.0 - (progress.seconds_remaining / max(progress.seconds_total, 0.01)),
            text=f"{progress.seconds_remaining:0.1f}s remaining",
        )
    elif phase == "done":
        st.success("Calibration saved.")
    elif phase == "error":
        st.error(progress.error or "Unknown error.")
        if progress.artifact_counts:
            st.write("**Artifact breakdown:**")
            st.json(progress.artifact_counts)

    # Live F chart from frames so far.
    chart = _focus_chart(progress)
    if chart is not None:
        st.altair_chart(chart, use_container_width=True)

    # ---- Result panel ----
    if phase == "done" and progress.result is not None:
        cal = progress.result
        c1, c2, c3 = st.columns(3)
        c1.metric("mean F", f"{cal.mean_f:.3f}")
        c2.metric("std F", f"{cal.std_f:.3f}")
        c3.metric("clean samples", cal.n_samples)
        if progress.eyes_open and progress.eyes_closed:
            open_mean = sum(f.focus for f in progress.eyes_open if f.artifact_clean) / max(
                1, sum(1 for f in progress.eyes_open if f.artifact_clean)
            )
            closed_mean = sum(f.focus for f in progress.eyes_closed if f.artifact_clean) / max(
                1, sum(1 for f in progress.eyes_closed if f.artifact_clean)
            )
            d1, d2 = st.columns(2)
            d1.metric("Eyes-open mean F", f"{open_mean:.3f}")
            d2.metric("Eyes-closed mean F", f"{closed_mean:.3f}",
                       delta=f"{closed_mean - open_mean:+.3f}",
                       delta_color="inverse" if closed_mean < open_mean else "normal")
            if closed_mean >= open_mean:
                st.warning(
                    "Eyes-closed F not lower than eyes-open. Expected α to rise "
                    "(F to drop) when eyes close. Reseat headband (esp. TP9/TP10) and re-run."
                )
            else:
                st.success("Eyes-closed lower than eyes-open — α rose, biologically plausible.")
        st.code(cal.to_json(), language="json")
        return

    # While running: rerun every 0.5s so progress + voice-driven phase changes show.
    if phase not in ("done", "error", "idle"):
        time.sleep(0.5)
        st.rerun()


@st.fragment(run_every=0.5)
def _signal_quality_preview(pipeline) -> None:
    """Live readout so user can verify good contact BEFORE starting.

    Shows the latest FocusFrame's artifact flags + per-channel std on the
    most recent 1s of raw EEG. Updates twice a second via fragment so the
    rest of the page does not flicker.
    """
    st.subheader("Signal quality — preview before starting")
    frame = pipeline.latest
    win = pipeline.latest_window(SAMPLE_RATE_HZ)
    if frame is None or win is None:
        st.caption("Buffer warming up…")
        return

    eeg, _accel, _ts = win
    cols = st.columns(len(EEG_CHANNELS))
    for col, ch_name, ch_data in zip(cols, EEG_CHANNELS, eeg.T):
        std = float(np.std(ch_data))
        # Heuristic per-channel quality: 5-100 µV is healthy contact.
        if std < 1.0:
            quality = "FLAT"
        elif std < 5.0:
            quality = "weak"
        elif std > 200.0:
            quality = "noisy"
        else:
            quality = "ok"
        col.metric(ch_name, f"{std:.1f} µV", delta=quality, delta_color="off")

    if frame.artifact:
        st.warning("Currently flagged: " + ", ".join(frame.artifact))
        st.caption(
            "Common fixes — BLINK: blink less; JAW: unclench; "
            "MOTION: hold head still; BAD_CONTACT: reseat headband, push hair away."
        )
    else:
        st.success("Signal looks clean. Safe to start.")


if __name__ == "__main__":
    render()
