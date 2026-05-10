"""NAO MCP server — exposes brain-state to AI agents.

Tools:
  - get_user_cognitive_load() -> {label, focus, focus_ema, artifact, ts}
  - get_current_brain_state() -> full FocusFrame
  - get_focus_history(seconds) -> recent FocusFrames
  - get_calibration() -> personal baseline (or null if uncalibrated)
  - should_interrupt(urgency) -> Gatekeeper decision: allow / defer / reason
  - notify_queued(source, summary, urgency) -> queue a deferred ping
  - get_quiet_status() -> Gatekeeper state + queued count
  - get_queued_pings() -> read-only peek at currently-queued pings
  - get_appraisal_state() -> Skeptic reward-spike state + caution advice

Resource:
  - brain://state — same as get_current_brain_state, polled by clients

Privacy: SPECS §4 invariant. Raw µV NEVER returned. Per-channel band
powers exposed only on get_current_brain_state (still summary scalars,
not waveforms). Gatekeeper outputs only labels + booleans.

Source defaults to synthetic so the server can boot without hardware. Set
NAO_SOURCE=muse (and install [hardware] extras) to use the live Muse.
"""
from __future__ import annotations

import logging
import os
from collections import deque
from typing import Any, Deque, Literal

from mcp.server.fastmcp import FastMCP

from nao.agents.gatekeeper import GatekeeperFSM
from nao.agents.skeptic import SkepticFSM
from nao.ingest.stream import Stream
from nao.ingest.synthetic import SyntheticStream
from nao.process.frame import FocusFrame
from nao.process.pipeline import Pipeline
from nao.state import Calibration, label_frame

log = logging.getLogger(__name__)

HISTORY_MAX = 600  # ~2.5 min @ 4 Hz emit cadence

mcp = FastMCP("nao-brain")

_state: dict[str, Any] = {
    "pipeline": None,
    "history": deque(maxlen=HISTORY_MAX),
    "calibration": None,
    "gatekeeper": None,
    "skeptic": None,
}


def _build_source() -> Stream:
    # Lazy import so MCP doesn't pull streamlit just to read the JSON config.
    from nao.dash.app_config import NaoConfig

    cfg = NaoConfig.load()
    kind = os.environ.get("NAO_SOURCE", cfg.last_source).lower()
    if kind == "muse":
        from nao.ingest.muse import MuseStream  # lazy: needs [hardware] extras
        addr = cfg.effective_muse_address()
        log.info("MCP source: Muse (live BLE), address=%s", addr)
        return MuseStream(address=addr)
    log.info("MCP source: synthetic.")
    inject = os.environ.get("NAO_SYNTH_INJECT_HZ")
    return SyntheticStream(inject_hz=float(inject) if inject else None, realtime=True)


def _ensure_pipeline() -> Pipeline:
    if _state["pipeline"] is None:
        pipeline = Pipeline(source=_build_source())
        history: Deque[FocusFrame] = _state["history"]
        pipeline.subscribe(history.append)
        gatekeeper = GatekeeperFSM()
        pipeline.subscribe(gatekeeper.on_frame)
        skeptic = SkepticFSM()
        pipeline.subscribe(skeptic.on_frame)
        pipeline.start()
        _state["pipeline"] = pipeline
        _state["calibration"] = Calibration.load()
        _state["gatekeeper"] = gatekeeper
        _state["skeptic"] = skeptic
        log.info("Pipeline started. Calibration loaded: %s", bool(_state["calibration"]))
    return _state["pipeline"]


def _gatekeeper() -> GatekeeperFSM:
    _ensure_pipeline()
    return _state["gatekeeper"]


def _skeptic() -> SkepticFSM:
    _ensure_pipeline()
    return _state["skeptic"]


def _summary(frame: FocusFrame) -> dict[str, Any]:
    """Compact, agent-friendly view. No raw waveforms."""
    return {
        "label": label_frame(frame, _state["calibration"]),
        "focus": frame.focus_ema,
        "focus_raw": frame.focus,
        "ts": frame.ts,
        "artifact": frame.artifact,
        "artifact_clean": frame.artifact_clean,
        "latency_ms": frame.latency_ms,
    }


@mcp.tool()
def get_user_cognitive_load() -> dict[str, Any]:
    """Return the user's current cognitive load label + focus scalar.

    Labels: deeply_focused | engaged | neutral | resting | uncertain.
    "uncertain" means signal had artifacts (blink/jaw/motion/bad-contact);
    do not act on it. Use this tool BEFORE interrupting the user.
    """
    pipeline = _ensure_pipeline()
    frame = pipeline.latest
    if frame is None:
        return {
            "label": "uncertain",
            "focus": None,
            "ts": None,
            "artifact": ["pipeline_warmup"],
            "artifact_clean": False,
            "latency_ms": None,
        }
    return _summary(frame)


@mcp.tool()
def get_current_brain_state() -> dict[str, Any]:
    """Full FocusFrame: band powers (delta/theta/alpha/beta/gamma), per-channel
    alpha+beta, focus, EMA, latency, artifact flags. Summary scalars only — no
    raw EEG waveforms ever leave this server."""
    pipeline = _ensure_pipeline()
    frame = pipeline.latest
    if frame is None:
        return {"status": "warmup", "detail": "Pipeline has not emitted a frame yet."}
    return frame.model_dump()


@mcp.tool()
def get_focus_history(seconds: float = 30.0) -> list[dict[str, Any]]:
    """Recent labeled summaries, oldest first. Useful for trend questions
    ('has the user been focused for the last 5 minutes?')."""
    _ensure_pipeline()
    history: Deque[FocusFrame] = _state["history"]
    if not history:
        return []
    cutoff = history[-1].ts - seconds
    return [_summary(f) for f in history if f.ts >= cutoff]


@mcp.tool()
def get_calibration() -> dict[str, Any] | None:
    """Personal F baseline if `nao-calibrate` has been run, else null.

    Returns mean_f, std_f, n_samples plus optional drift fields:
      - saved_at: epoch seconds when the baseline was written.
      - age_days: days since save (None for legacy files).
      - is_stale: True if older than 7 days — consider re-calibrating.
    Without calibration, labels use SPECS-default thresholds and may not
    match this user's typical range."""
    cal: Calibration | None = _state["calibration"]
    if cal is None:
        return None
    return {
        "mean_f": cal.mean_f,
        "std_f": cal.std_f,
        "n_samples": cal.n_samples,
        "saved_at": cal.saved_at,
        "age_days": cal.age_days(),
        "is_stale": cal.is_stale(),
    }


@mcp.tool()
def should_interrupt(urgency: Literal["low", "medium", "high"] = "medium") -> dict[str, Any]:
    """Ask the Gatekeeper whether it is safe to interrupt the user right now.

    Cooperating agents (Claude, Cursor, custom CLIs) call this BEFORE speaking
    to the user. Returns:
      - allow (bool): true = speak now, false = defer.
      - defer_seconds (float|null): if allow=false, suggested wait.
      - reason (str): "deeply_focused", "signal_uncertain", "warmup", etc.
      - label (str): current cognitive-load label.
      - quiet (bool): whether the FSM is in QUIET state.

    macOS does not let third-party apps intercept other apps' notifications;
    this tool is advisory. Honor it.
    """
    gk = _gatekeeper()
    decision = gk.decide(urgency, calibration=_state["calibration"])
    status = gk.status()
    return {
        "allow": decision.allow,
        "defer_seconds": decision.defer_seconds,
        "reason": decision.reason,
        "label": decision.label,
        "quiet": status["quiet"],
    }


@mcp.tool()
def notify_queued(
    source: str,
    summary: str,
    urgency: Literal["low", "medium", "high"] = "medium",
) -> dict[str, Any]:
    """Queue a deferred notification for surfacing when the user becomes
    interruptible. Pass a one-line summary (no message bodies). Returns a
    queued_id; useful when an agent received allow=false from should_interrupt.
    """
    gk = _gatekeeper()
    queued_id = gk.queue(source=source, summary=summary, urgency=urgency)
    return {"queued_id": queued_id, "queued_count": gk.status()["queued_count"]}


@mcp.tool()
def get_quiet_status() -> dict[str, Any]:
    """Gatekeeper state snapshot: quiet flag, when QUIET began, queued count,
    last label observed, last decision reason. Use to render a 'do not disturb'
    indicator without polling should_interrupt."""
    return _gatekeeper().status()


@mcp.tool()
def get_appraisal_state() -> dict[str, Any]:
    """Skeptic snapshot: recent reward-spike flag + caution advice.

    Reward / "aha" / agreement bursts show up as transient frontal-gamma
    spikes. When `recent_spike=true`, the user's appraisal is biased toward
    whatever they just saw or heard — cooperating agents that are about to
    *affirm* the user's recent choice should soften, probe, or counter-cite
    instead of just agreeing. Returns:
      - recent_spike (bool): within ~30s of last detected spike.
      - since_spike_s (float|null): seconds since last spike.
      - baseline_n (int): clean samples in the running gamma baseline.
      - last_z (float|null): latest z-score over baseline.
      - caution (bool): policy verdict — should the agent soften?
      - cooldown_seconds (float): how long the caution still applies.
      - reason (str): policy tag.
    """
    sk = _skeptic()
    s = sk.state()
    a = sk.advise()
    return {
        **s,
        "caution": a.caution,
        "cooldown_seconds": a.cooldown_seconds,
        "reason": a.reason,
    }


@mcp.tool()
def get_queued_pings() -> list[dict[str, Any]]:
    """Read-only peek at pings currently held by the Gatekeeper. Order is FIFO
    (oldest first). Does not drain the queue — use notify_queued to add and
    `release` via the sidecar to drain."""
    return [
        {"id": p.id, "source": p.source, "summary": p.summary, "urgency": p.urgency}
        for p in _gatekeeper().peek_queued()
    ]


@mcp.resource("brain://state")
def brain_state_resource() -> str:
    """Pollable resource form of get_current_brain_state."""
    import json

    return json.dumps(get_current_brain_state(), default=float)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _ensure_pipeline()
    mcp.run()


if __name__ == "__main__":
    main()
