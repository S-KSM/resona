"""HTTP/SSE sidecar API consumed by the SwiftUI app.

Endpoints
---------
GET  /health                    Liveness.
GET  /state                     Latest FocusFrame.
GET  /events                    SSE stream of FocusFrames.
GET  /history?seconds=30        Recent labeled summaries.
GET  /signal/quality            Per-channel std + flags + current artifact.
GET  /config                    NaoConfig.
POST /config                    Update + persist NaoConfig.
GET  /sources/scan?timeout=8    BLE scan for Muse devices.
POST /pipeline/restart          Tear down + rebuild pipeline.
GET  /calibration               Saved Calibration baseline.
GET  /calibrate/progress        Live CalibrationProgress.
POST /calibrate/start           Start calibration (Swift drives the voice).
POST /calibrate/cancel          Cancel running calibration.
POST /calibrate/reset           Drop the current progress object.
GET  /llm/health                Ollama reachable?
GET  /llm/models                Installed Ollama models.
POST /llm/prose                 Neutral prose for eyes-open phase.
POST /llm/chat                  Coach Q&A (state auto-injected).
GET  /gatekeeper/status         Gatekeeper FSM snapshot.
GET  /gatekeeper/queued         Read-only peek at queued pings.
POST /gatekeeper/queue          Append a ping to the queue.
POST /gatekeeper/override       Force OPEN | QUIET | release queued.
GET  /appraisal/status          Skeptic reward-spike state + caution advice.
POST /session/start             Begin a labeled recording.
POST /session/stop              End the active recording, finalize summary.
GET  /session/active            Currently-recording session, or null.
GET  /sessions                  Index of all past sessions.
GET  /session/{id}              Full session metadata + summary.
DELETE /session/{id}            Drop a session (index + jsonl).
GET  /session/{id}/frames       Downsampled FocusFrames for charting.
GET  /session/{id}/insights     Coach-ready digest (timeline, quartiles, baselines).
POST /session/{id}/chat         LLM chat with the session digest as context.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from nao import runtime
from nao.dash.app_config import NaoConfig
from nao.llm.client import OllamaClient, llm_available
from nao.llm.prose import calibration_prose
from nao.llm.skills import (
    build_session_system_prompt,
    build_system_prompt,
    current_state_block,
)
from nao.process.verdict import verdict as build_verdict
from nao.sessions.insights import build_insights
from nao.state import Calibration, label_frame

log = logging.getLogger(__name__)

app = FastAPI(title="nao-sidecar", version="0.3.1")


# ---- Pydantic request/response models (kept thin; Swift mirrors them) ----


class ConfigUpdate(BaseModel):
    muse_address: str | None = None
    voice_name: str | None = None
    voice_rate: int | None = None
    last_source: str | None = None


class CalibrateStart(BaseModel):
    seconds_per_phase: float = 60.0
    voice_name: str | None = None  # ignored: Swift drives voice
    voice_rate: int = 175


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float = 0.4
    model: str | None = None


class ProseRequest(BaseModel):
    seed: int | None = None
    model: str | None = None


class GatekeeperQueue(BaseModel):
    source: str
    summary: str
    urgency: str = "medium"


class GatekeeperOverride(BaseModel):
    target: str  # "OPEN" | "QUIET" | "release"


class SessionStart(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    notes: str = Field(default="", max_length=2000)


# ---- Health + state ----


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": app.version}


@app.get("/state")
def state() -> dict[str, Any]:
    frame = runtime.latest_frame()
    if frame is None:
        return {"status": "warmup"}
    cal = Calibration.load()
    d = frame.model_dump()
    d["label"] = label_frame(frame, cal)
    d["status"] = "live"
    return d


@app.get("/history")
def history(seconds: float = 30.0) -> list[dict[str, Any]]:
    cal = Calibration.load()
    frames = runtime.recent_frames(seconds)
    return [
        {
            "ts": f.ts,
            "focus": f.focus_ema,
            "focus_raw": f.focus,
            "alpha": f.alpha,
            "beta": f.beta,
            "label": label_frame(f, cal),
            "artifact": f.artifact,
        }
        for f in frames
    ]


@app.get("/signal/quality")
def signal_quality() -> dict[str, Any]:
    return current_state_block(history_seconds=2.0)


@app.get("/verdict")
def verdict_now() -> dict[str, Any]:
    """One-sentence natural-language read of the current FocusFrame.

    Drives the Now tab and menu-bar — rule-based so the same state always
    produces the same read (LLM is reserved for Coach Q&A)."""
    frame = runtime.latest_frame()
    if frame is None:
        return {
            "headline": "Warming up.",
            "detail": "Waiting for the first window of clean signal.",
            "action": "Sit still for a moment.",
            "tone": "noisy",
        }
    cal = Calibration.load()
    hist = runtime.recent_frames(8.0)
    v = build_verdict(frame, calibration=cal, history=hist)
    return {
        "headline": v.headline,
        "detail": v.detail,
        "action": v.action,
        "tone": v.tone,
    }


# ---- SSE event stream ----


@app.get("/events")
async def events():
    """One JSON-encoded FocusFrame per SSE event, ~4 Hz."""
    cal = Calibration.load()

    async def gen():
        last_ts: float | None = None
        while True:
            frame = runtime.latest_frame()
            if frame is not None and frame.ts != last_ts:
                last_ts = frame.ts
                payload = frame.model_dump()
                payload["label"] = label_frame(frame, cal)
                payload["quiet"] = runtime.get_gatekeeper().status()["quiet"]
                yield {"event": "frame", "data": json.dumps(payload, default=float)}
            await asyncio.sleep(0.1)

    return EventSourceResponse(gen())


# ---- Gatekeeper ----


@app.get("/gatekeeper/status")
def gatekeeper_status() -> dict[str, Any]:
    return runtime.get_gatekeeper().status()


@app.get("/gatekeeper/queued")
def gatekeeper_queued() -> list[dict[str, Any]]:
    """Read-only peek at currently-queued pings. Order = FIFO."""
    return [
        {"id": p.id, "source": p.source, "summary": p.summary, "urgency": p.urgency}
        for p in runtime.get_gatekeeper().peek_queued()
    ]


# ---- Skeptic ----


@app.get("/appraisal/status")
def appraisal_status() -> dict[str, Any]:
    """Skeptic reward-spike state + caution advice. Mirrors the MCP tool."""
    sk = runtime.get_skeptic()
    s = sk.state()
    a = sk.advise()
    return {
        **s,
        "caution": a.caution,
        "cooldown_seconds": a.cooldown_seconds,
        "reason": a.reason,
    }


@app.post("/gatekeeper/queue")
def gatekeeper_queue(req: GatekeeperQueue) -> dict[str, Any]:
    if req.urgency not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="urgency must be low|medium|high")
    qid = runtime.get_gatekeeper().queue(
        source=req.source, summary=req.summary, urgency=req.urgency
    )
    return {"queued_id": qid, "queued_count": runtime.get_gatekeeper().status()["queued_count"]}


@app.post("/gatekeeper/override")
def gatekeeper_override(req: GatekeeperOverride) -> dict[str, Any]:
    gk = runtime.get_gatekeeper()
    target = req.target.upper()
    if target == "RELEASE":
        released = gk.release_queued()
        return {
            "status": "released",
            "released_count": len(released),
            "items": [
                {"id": p.id, "source": p.source, "summary": p.summary, "urgency": p.urgency}
                for p in released
            ],
        }
    if target not in ("OPEN", "QUIET"):
        raise HTTPException(status_code=400, detail="target must be OPEN | QUIET | release")
    gk.manual_override(target)
    return gk.status()


# ---- Config ----


@app.get("/config")
def get_config() -> dict[str, Any]:
    cfg = NaoConfig.load()
    return {
        "muse_address": cfg.muse_address,
        "voice_name": cfg.voice_name,
        "voice_rate": cfg.voice_rate,
        "last_source": cfg.last_source,
    }


@app.post("/config")
def update_config(patch: ConfigUpdate) -> dict[str, Any]:
    cfg = NaoConfig.load()
    changed = False
    for field, value in patch.model_dump(exclude_unset=True).items():
        if value is not None and getattr(cfg, field) != value:
            setattr(cfg, field, value)
            changed = True
    if changed:
        cfg.save()
        if "last_source" in patch.model_dump(exclude_unset=True) or \
                "muse_address" in patch.model_dump(exclude_unset=True):
            runtime.restart_pipeline()
    return get_config()


# ---- Sources / pairing ----


@app.get("/sources/scan")
async def scan(timeout: float = 8.0) -> list[dict[str, str]]:
    try:
        from bleak import BleakScanner
    except ImportError:
        raise HTTPException(
            status_code=501, detail="BLE stack not installed. uv sync --extra hardware."
        )
    devices = await BleakScanner.discover(timeout=timeout)
    return [
        {"address": d.address, "name": d.name or ""}
        for d in devices
        if d.name and d.name.startswith("Muse")
    ]


@app.post("/pipeline/restart")
def pipeline_restart() -> dict[str, str]:
    runtime.restart_pipeline()
    return {"status": "restarted"}


# ---- Calibration ----


@app.get("/calibration")
def calibration() -> dict[str, Any] | None:
    cal = Calibration.load()
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


def _serialize_progress(p) -> dict[str, Any]:
    return {
        "phase": p.phase,
        "seconds_remaining": p.seconds_remaining,
        "seconds_total": p.seconds_total,
        "n_eyes_open": len(p.eyes_open),
        "n_eyes_closed": len(p.eyes_closed),
        "result": (
            {"mean_f": p.result.mean_f, "std_f": p.result.std_f, "n_samples": p.result.n_samples}
            if p.result else None
        ),
        "error": p.error,
        "artifact_counts": p.artifact_counts,
    }


@app.get("/calibrate/progress")
def calibrate_progress() -> dict[str, Any]:
    p = runtime.calibration_progress()
    if p is None:
        return {"phase": "idle"}
    return _serialize_progress(p)


@app.post("/calibrate/start")
def calibrate_start(req: CalibrateStart) -> dict[str, Any]:
    p = runtime.start_calibration(
        seconds_per_phase=req.seconds_per_phase,
        voice_name=None,  # Swift handles voice
        voice_rate=req.voice_rate,
    )
    return _serialize_progress(p)


@app.post("/calibrate/cancel")
def calibrate_cancel() -> dict[str, str]:
    runtime.cancel_calibration()
    return {"status": "cancelling"}


@app.post("/calibrate/reset")
def calibrate_reset() -> dict[str, str]:
    runtime.reset_calibration_state()
    return {"status": "reset"}


# ---- LLM ----


@app.get("/llm/health")
def llm_health() -> dict[str, Any]:
    return {"available": llm_available()}


@app.get("/llm/models")
def llm_models() -> list[str]:
    if not llm_available():
        return []
    return OllamaClient().list_models()


@app.post("/llm/prose")
def llm_prose(req: ProseRequest) -> dict[str, str]:
    return {"text": calibration_prose(seed=req.seed, model=req.model)}


# ---- Sessions ----


@app.post("/session/start")
def session_start(req: SessionStart) -> dict[str, Any]:
    rec = runtime.get_recorder()
    if rec.active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"session already active: {rec.active.id} ({rec.active.label})",
        )
    s = rec.start(label=req.label, notes=req.notes)
    return s.model_dump()


@app.post("/session/stop")
def session_stop() -> dict[str, Any]:
    rec = runtime.get_recorder()
    s = rec.stop()
    if s is None:
        raise HTTPException(status_code=409, detail="no active session")
    return s.model_dump()


@app.get("/session/active")
def session_active() -> dict[str, Any] | None:
    s = runtime.get_recorder().active
    return s.model_dump() if s is not None else None


@app.get("/sessions")
def sessions_list() -> list[dict[str, Any]]:
    return [s.model_dump() for s in runtime.get_recorder().store.list_sessions()]


@app.get("/session/{session_id}")
def session_get(session_id: str) -> dict[str, Any]:
    s = runtime.get_recorder().store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return s.model_dump()


@app.delete("/session/{session_id}")
def session_delete(session_id: str) -> dict[str, Any]:
    rec = runtime.get_recorder()
    if rec.active is not None and rec.active.id == session_id:
        raise HTTPException(status_code=409, detail="cannot delete active session")
    deleted = rec.store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "deleted", "id": session_id}


@app.get("/session/{session_id}/frames")
def session_frames(session_id: str, step: int = 1) -> list[dict[str, Any]]:
    """Downsampled per-frame data for charting. step=1 returns every frame;
    step=4 returns every 4th, etc. Capped to 4000 frames per response."""
    rec = runtime.get_recorder()
    s = rec.store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    step = max(1, step)
    frames = rec.store.read_frames(session_id)
    sliced = frames[::step]
    if len(sliced) > 4000:
        sliced = sliced[:: len(sliced) // 4000 + 1]
    return [
        {
            "ts": f.ts,
            "focus_ema": f.focus_ema,
            "focus": f.focus,
            "alpha": f.alpha,
            "beta": f.beta,
            "frontal_asymmetry": f.frontal_asymmetry,
            "arousal_index": f.arousal_index,
            "artifact_clean": f.artifact_clean,
        }
        for f in sliced
    ]


@app.get("/session/{session_id}/insights")
def session_insights(session_id: str) -> dict[str, Any]:
    rec = runtime.get_recorder()
    s = rec.store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return build_insights(s, rec.store)


@app.post("/session/{session_id}/chat")
def session_chat(session_id: str, req: ChatRequest) -> dict[str, Any]:
    """Coach Q&A scoped to a past session — digest injected as context."""
    if not llm_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama not running. Start with `ollama serve` and pull a model.",
        )
    rec = runtime.get_recorder()
    s = rec.store.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    digest = build_insights(s, rec.store)
    sys_prompt = build_session_system_prompt(digest)
    messages = [{"role": "system", "content": sys_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]
    client = OllamaClient(model=req.model) if req.model else OllamaClient()
    reply = client.chat(messages, temperature=req.temperature)
    return {"reply": reply, "model": client.model}


@app.post("/llm/chat")
def llm_chat(req: ChatRequest) -> dict[str, Any]:
    if not llm_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama not running. Start with `ollama serve` and pull a model.",
        )
    sys_prompt = build_system_prompt(history_seconds=10.0)
    messages = [{"role": "system", "content": sys_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]
    client = OllamaClient(model=req.model) if req.model else OllamaClient()
    reply = client.chat(messages, temperature=req.temperature)
    return {"reply": reply, "model": client.model}


# ---- Entry ----


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    runtime.get_pipeline()  # warm up
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
