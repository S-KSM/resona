"""Live Brain Load — real-time F, band powers, raw EEG, artifact flags.

Uses st.fragment(run_every) so only the live panel re-renders. Without it
the whole script polls in-place and Streamlit re-mounts charts each tick,
which yanks the scroll position to the top.
"""
from __future__ import annotations

from collections import deque

import altair as alt
import pandas as pd
import streamlit as st

from nao.config import (
    DISPLAY_SECONDS,
    EEG_CHANNELS,
    LATENCY_BUDGET_MS,
    SAMPLE_RATE_HZ,
)
from nao.dash._shared import get_config, get_pipeline, restart_pipeline, save_config

POLL_HZ = 4
HISTORY_S = 30


def _waves_chart(eeg, ts) -> alt.Chart:
    wave_df = pd.DataFrame(eeg, columns=list(EEG_CHANNELS))
    wave_df["t"] = ts - ts[0]
    long = wave_df.melt(id_vars="t", var_name="channel", value_name="uV")
    return (
        alt.Chart(long)
        .mark_line(strokeWidth=1)
        .encode(
            x=alt.X("t:Q", title="seconds"),
            y=alt.Y("uV:Q", title="µV", scale=alt.Scale(zero=False)),
            color=alt.Color("channel:N", legend=None, sort=list(EEG_CHANNELS)),
        )
        .properties(height=80, width="container")
        .facet(
            row=alt.Row(
                "channel:N",
                sort=list(EEG_CHANNELS),
                header=alt.Header(labelAngle=0, labelAlign="left", title=None),
            )
        )
        .resolve_scale(y="independent")
    )


def render() -> None:
    st.title("Live Brain Load")
    st.caption("Muse-14B3 → FFT → Focus Coefficient F = β / α")

    cfg = get_config()

    with st.sidebar:
        st.header("Source")
        kind = st.radio(
            "Stream",
            options=["synthetic", "muse"],
            index=0 if cfg.last_source == "synthetic" else 1,
            key="source_kind",
        )
        if kind != cfg.last_source:
            cfg.last_source = kind
            save_config(cfg)
            restart_pipeline()
            st.rerun()
        if kind == "synthetic":
            st.slider(
                "Injected sinusoid (Hz)",
                min_value=0.0,
                max_value=40.0,
                value=10.0,
                step=0.5,
                key="inject_hz",
                on_change=restart_pipeline,
            )
            st.caption("10 Hz → α dominant, low F. 20 Hz → β dominant, high F.")
        elif not cfg.effective_muse_address():
            st.warning("No Muse address saved. Visit **Setup** first.")
        if st.button("Restart pipeline"):
            restart_pipeline()
            st.rerun()
        st.divider()
        st.header("Display")
        show_waves = st.checkbox("Show raw EEG waves", value=True, key="show_waves")
        st.slider(
            "Wave history (s)",
            min_value=1.0,
            max_value=DISPLAY_SECONDS,
            value=DISPLAY_SECONDS,
            step=0.5,
            disabled=not show_waves,
            key="wave_seconds",
        )

    # init session-scoped history once
    if "history" not in st.session_state:
        st.session_state.history = deque(maxlen=HISTORY_S * POLL_HZ)

    @st.fragment(run_every=1.0 / POLL_HZ)
    def live_panel() -> None:
        pipeline = get_pipeline()
        frame = pipeline.latest
        if frame is None:
            st.info("Pipeline warming up…")
            return

        history: deque = st.session_state.history
        history.append(frame.model_dump())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Focus (EMA)", f"{frame.focus_ema:.2f}")
        c2.metric("Focus (raw)", f"{frame.focus:.2f}")
        c3.metric(
            "Latency (ms)",
            f"{frame.latency_ms:.1f}",
            delta=None if frame.latency_ms < LATENCY_BUDGET_MS else "OVER BUDGET",
            delta_color="inverse",
        )
        c4.metric("Clean?", "yes" if frame.artifact_clean else "no")

        df = pd.DataFrame(history)
        st.subheader("Focus Coefficient over time")
        st.line_chart(df.set_index("ts")[["focus", "focus_ema"]], height=240)

        if st.session_state.get("show_waves", True):
            wave_seconds = st.session_state.get("wave_seconds", DISPLAY_SECONDS)
            st.subheader(f"Raw EEG (last {wave_seconds:.1f}s)")
            win = pipeline.latest_window(int(SAMPLE_RATE_HZ * wave_seconds))
            if win is None:
                st.info("Buffer warming up…")
            else:
                eeg, _accel, ts = win
                st.altair_chart(_waves_chart(eeg, ts), use_container_width=True)

        st.subheader("Band power (latest window)")
        bands_df = pd.DataFrame(
            {
                "band": ["delta", "theta", "alpha", "beta", "gamma"],
                "power": [
                    frame.delta,
                    frame.theta,
                    frame.alpha,
                    frame.beta,
                    frame.gamma,
                ],
            }
        )
        st.bar_chart(bands_df.set_index("band"), height=200)

        if frame.artifact:
            st.warning("Artifacts: " + ", ".join(frame.artifact))
        else:
            st.success("Signal clean")

    live_panel()


if __name__ == "__main__":
    render()
