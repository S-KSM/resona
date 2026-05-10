"""Setup — pair Muse, pick a voice, view calibration status."""
from __future__ import annotations

import asyncio
import datetime as dt

import streamlit as st

from nao.dash._shared import get_config, restart_pipeline, save_config
from nao.dash.voice import list_voices, say_available, speak
from nao.state import CALIBRATION_PATH, Calibration


def _scan_muse(timeout: float = 8.0) -> list[tuple[str, str]]:
    try:
        from bleak import BleakScanner
    except ImportError:
        st.error(
            "BLE stack not installed. Run `uv sync --extra hardware` then restart the dash."
        )
        return []

    async def _go() -> list[tuple[str, str]]:
        devices = await BleakScanner.discover(timeout=timeout)
        return [
            (d.address, d.name or "(unnamed)")
            for d in devices
            if d.name and d.name.startswith("Muse")
        ]

    return asyncio.run(_go())


def render() -> None:
    st.title("Setup")
    cfg = get_config()

    # ---- Muse pairing ----
    st.header("Muse-14B3")
    st.caption(
        "Power on the headband and hold the button ~6s until lights cascade, then scan."
    )
    st.write(
        f"Currently saved: `{cfg.muse_address or '(none)'}`"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        scan_clicked = st.button("Scan (8 s)")
    with col2:
        typed_addr = st.text_input(
            "Override address (CoreBluetooth UUID on macOS)",
            value="",
            key="muse_addr_text",
            help="Type an address and press Save, or click a scan result below.",
        )

    if scan_clicked:
        with st.spinner("Scanning…"):
            results = _scan_muse()
        if not results:
            st.error("No Muse devices found. Is the headband in pairing mode?")
        else:
            st.session_state.scan_results = results

    if "scan_results" in st.session_state and st.session_state.scan_results:
        st.write("Found:")
        for addr, name in st.session_state.scan_results:
            cols = st.columns([3, 4, 2])
            cols[0].code(name, language=None)
            cols[1].code(addr, language=None)
            if cols[2].button("Use", key=f"use-{addr}"):
                cfg.muse_address = addr
                save_config(cfg)
                restart_pipeline()
                st.rerun()

    if st.button("Save typed address"):
        addr = (typed_addr or "").strip() or None
        cfg.muse_address = addr
        save_config(cfg)
        restart_pipeline()
        st.rerun()

    st.divider()

    # ---- Voice ----
    st.header("Voice guide")
    if not say_available():
        st.warning("`say` not available — TTS disabled. macOS only.")
    else:
        voices = list_voices()
        names = [v.name for v in voices]
        if names:
            try:
                idx = names.index(cfg.voice_name)
            except ValueError:
                idx = 0
            picked = st.selectbox(
                "Voice",
                names,
                index=idx,
                help="Premium / Neural voices sound markedly better. "
                "Install via System Settings → Accessibility → Spoken Content → "
                "System Voice → Manage Voices.",
            )
            rate = st.slider("Rate (wpm)", 120, 240, value=cfg.voice_rate, step=5)
            colA, colB = st.columns(2)
            if colA.button("Test voice"):
                speak(
                    "This is the voice that will guide your calibration.",
                    voice=picked,
                    rate_wpm=rate,
                )
            if colB.button("Save voice"):
                cfg.voice_name = picked
                cfg.voice_rate = rate
                save_config(cfg)
                st.success("Saved.")
            premium = [v.name for v in voices if v.is_premium]
            if not premium:
                st.info(
                    "No Premium/Neural English voices installed. Standard voices "
                    "still work — just less natural."
                )
        else:
            st.warning("No English voices found.")

    st.divider()

    # ---- Calibration status ----
    st.header("Calibration status")
    cal = Calibration.load()
    if cal is None:
        st.warning(
            "No baseline saved. Visit **Calibrate** to record one — "
            "without it, MCP labels use generic SPECS thresholds and may always read 'resting'."
        )
    else:
        mtime = dt.datetime.fromtimestamp(CALIBRATION_PATH.stat().st_mtime)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("mean F", f"{cal.mean_f:.3f}")
        c2.metric("std F", f"{cal.std_f:.3f}")
        c3.metric("samples", cal.n_samples)
        c4.metric("recorded", mtime.strftime("%Y-%m-%d %H:%M"))
        age_days = (dt.datetime.now() - mtime).days
        if age_days > 14:
            st.warning(f"Baseline is {age_days} days old — consider re-calibrating.")


if __name__ == "__main__":
    render()
