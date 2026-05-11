"""Process-wide singletons — Pipeline + active CalibrationProgress.

Both the MCP server and the HTTP API consume the same Pipeline so we never
open two BLE connections to the headband.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import deque
from typing import Optional

from nao.agents.gatekeeper import GatekeeperFSM
from nao.agents.skeptic import SkepticFSM
from nao.dash.app_config import NaoConfig
from nao.dash.calibration_worker import CalibrationProgress
from nao.ingest.stream import Stream
from nao.ingest.synthetic import SyntheticStream
from nao.process.frame import FocusFrame
from nao.process.pipeline import Pipeline
from nao.sessions import SessionRecorder

log = logging.getLogger(__name__)

_lock = threading.RLock()
_pipeline: Optional[Pipeline] = None
_history: deque[FocusFrame] = deque(maxlen=600)  # ~2.5 min @ 4 Hz
_gatekeeper: Optional[GatekeeperFSM] = None
_skeptic: Optional[SkepticFSM] = None
_recorder: Optional[SessionRecorder] = None
_calibration: Optional[CalibrationProgress] = None
_calibration_thread: Optional[threading.Thread] = None


def _build_source() -> Stream:
    cfg = NaoConfig.load()
    kind = os.environ.get("NAO_SOURCE", cfg.last_source).lower()
    if kind == "muse":
        from nao.ingest.muse import MuseStream
        addr = cfg.effective_muse_address()
        log.info("Source: Muse (live BLE), address=%s", addr)
        return MuseStream(address=addr)
    inject = os.environ.get("NAO_SYNTH_INJECT_HZ")
    log.info("Source: synthetic.")
    return SyntheticStream(inject_hz=float(inject) if inject else None, realtime=True)


def get_pipeline() -> Pipeline:
    global _pipeline, _gatekeeper, _skeptic, _recorder
    with _lock:
        if _pipeline is None:
            _pipeline = Pipeline(source=_build_source())
            _pipeline.subscribe(_history.append)
            _gatekeeper = GatekeeperFSM()
            _pipeline.subscribe(_gatekeeper.on_frame)
            _skeptic = SkepticFSM()
            _pipeline.subscribe(_skeptic.on_frame)
            # Recorder persists across pipeline restarts conceptually but the
            # subscriber list is rebuilt per Pipeline, so re-subscribe here.
            if _recorder is None:
                _recorder = SessionRecorder()
            _pipeline.subscribe(_recorder.on_frame)
            _pipeline.start()
        return _pipeline


def get_gatekeeper() -> GatekeeperFSM:
    """Return the singleton Gatekeeper FSM, ensuring the Pipeline is alive."""
    get_pipeline()
    assert _gatekeeper is not None
    return _gatekeeper


def get_skeptic() -> SkepticFSM:
    """Return the singleton Skeptic FSM, ensuring the Pipeline is alive."""
    get_pipeline()
    assert _skeptic is not None
    return _skeptic


def get_recorder() -> SessionRecorder:
    """Return the singleton SessionRecorder. Survives pipeline restarts."""
    get_pipeline()
    assert _recorder is not None
    return _recorder


def stream_health() -> dict:
    """Return a small diagnostic dict for the UI. Live-BLE sources surface
    `unstable=True` when the headband has dropped 3+ times in 30 s;
    synthetic and other sources are always stable."""
    if _pipeline is None:
        return {"unstable": False, "recent_drops": 0, "last_drop_age_s": None}
    src = getattr(_pipeline, "source", None)
    fn = getattr(src, "stream_health", None)
    if callable(fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            pass
    return {"unstable": False, "recent_drops": 0, "last_drop_age_s": None}


def restart_pipeline() -> Pipeline:
    """Tear down + rebuild. Used after source change in /config or /pipeline/restart.

    The active session (if any) is force-stopped — restarting the source
    constitutes a meaningful boundary and dropping it would leak an
    unfinishable session into the index.
    """
    global _pipeline, _gatekeeper, _skeptic
    with _lock:
        if _recorder is not None and _recorder.active is not None:
            log.info("restart_pipeline: auto-stopping active session %s", _recorder.active.id)
            _recorder.stop()
        if _pipeline is not None:
            _pipeline.stop()
            _pipeline = None
        _history.clear()
        _gatekeeper = None
        _skeptic = None
    return get_pipeline()


def latest_frame() -> Optional[FocusFrame]:
    return get_pipeline().latest


def recent_frames(seconds: float) -> list[FocusFrame]:
    if not _history:
        return []
    cutoff = _history[-1].ts - seconds
    return [f for f in _history if f.ts >= cutoff]


def calibration_progress() -> Optional[CalibrationProgress]:
    return _calibration


def start_calibration(
    seconds_per_phase: float, voice_name: Optional[str], voice_rate: int
) -> CalibrationProgress:
    """Run calibration with no Python-side TTS — Swift handles voice. The
    voice_name/rate args are ignored here (kept for API symmetry); Python's
    `say` is bypassed by passing voice_name=None to the worker."""
    global _calibration, _calibration_thread
    with _lock:
        if _calibration is not None and _calibration.phase not in (
            "idle", "done", "error"
        ):
            return _calibration
        from nao.dash.calibration_worker import start_calibration_thread

        # voice_name=None disables the Python `say` calls inside the worker;
        # Swift drives prompts via AVSpeechSynthesizer based on phase polls.
        _calibration, _calibration_thread = start_calibration_thread(
            pipeline=get_pipeline(),
            seconds_per_phase=seconds_per_phase,
            voice_name=None,
            voice_rate=voice_rate,
        )
        return _calibration


def cancel_calibration() -> None:
    if _calibration is not None:
        _calibration.cancel = True


def reset_calibration_state() -> None:
    global _calibration
    _calibration = None
