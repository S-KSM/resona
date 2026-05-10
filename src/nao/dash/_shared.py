"""Cross-page state for the Streamlit dash.

Pipeline lives in st.session_state so navigation between Live/Setup/Calibrate
doesn't kill the BLE link or restart calibration.
"""
from __future__ import annotations

import streamlit as st

from nao.dash.app_config import NaoConfig
from nao.ingest.stream import Stream
from nao.ingest.synthetic import SyntheticStream
from nao.process.pipeline import Pipeline


def get_config() -> NaoConfig:
    """Per-session config. Loaded from disk once, persisted on save."""
    if "config" not in st.session_state:
        st.session_state.config = NaoConfig.load()
    return st.session_state.config


def save_config(cfg: NaoConfig) -> None:
    cfg.save()
    st.session_state.config = cfg


def _build_source(kind: str, inject_hz: float | None, address: str | None) -> Stream:
    if kind == "muse":
        from nao.ingest.muse import MuseStream  # lazy: needs [hardware]
        return MuseStream(address=address)
    return SyntheticStream(inject_hz=inject_hz, realtime=True)


def get_pipeline() -> Pipeline:
    """Singleton pipeline pinned to st.session_state. Survives page nav."""
    if "pipeline" in st.session_state and st.session_state.pipeline is not None:
        return st.session_state.pipeline
    cfg = get_config()
    kind = st.session_state.get("source_kind", cfg.last_source)
    inject_hz = st.session_state.get("inject_hz", 10.0)
    pipeline = Pipeline(
        source=_build_source(kind, inject_hz, cfg.effective_muse_address())
    )
    pipeline.start()
    st.session_state.pipeline = pipeline
    return pipeline


def restart_pipeline() -> None:
    """Stop + drop the current pipeline so the next get_pipeline() rebuilds it."""
    p = st.session_state.get("pipeline")
    if p is not None:
        p.stop()
    st.session_state.pipeline = None
