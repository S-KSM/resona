"""HTTP API smoke + key paths against synthetic source."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Ensure synthetic source even if config says muse.
    monkeypatch.setenv("NAO_SOURCE", "synthetic")
    monkeypatch.setenv("NAO_SYNTH_INJECT_HZ", "10")
    # Reset runtime singletons for test isolation.
    from nao import runtime
    if runtime._pipeline is not None:
        runtime._pipeline.stop()
    runtime._pipeline = None
    runtime._history.clear()
    runtime._calibration = None

    from nao.api.server import app
    runtime.get_pipeline()
    time.sleep(2.0)  # warm pipeline so /state has data
    yield TestClient(app)
    if runtime._pipeline is not None:
        runtime._pipeline.stop()
    runtime._pipeline = None


def test_health(client) -> None:
    assert client.get("/health").json() == {"ok": True, "version": "0.1.0"}


def test_state_warmed_up(client) -> None:
    s = client.get("/state").json()
    assert s["status"] == "live"
    assert "focus_ema" in s
    assert "label" in s
    assert s["label"] in {"deeply_focused", "engaged", "neutral", "resting", "uncertain"}


def test_history_returns_recent_frames(client) -> None:
    h = client.get("/history?seconds=5").json()
    assert isinstance(h, list)
    assert len(h) > 0
    assert "focus" in h[0]


def test_signal_quality(client) -> None:
    q = client.get("/signal/quality").json()
    assert q["status"] == "live"
    assert "current" in q
    assert "signal_quality" in q
    assert len(q["signal_quality"]) == 4  # one entry per channel


def test_config_roundtrip(client) -> None:
    # GET shape.
    cfg = client.get("/config").json()
    for k in ("muse_address", "voice_name", "voice_rate", "last_source"):
        assert k in cfg
    # POST partial update — voice_rate only.
    new_rate = (cfg["voice_rate"] or 175) + 5
    updated = client.post("/config", json={"voice_rate": new_rate}).json()
    assert updated["voice_rate"] == new_rate


def test_calibration_endpoints(client) -> None:
    # No calibration running yet.
    assert client.get("/calibrate/progress").json() == {"phase": "idle"}
    # Start short calibration; cancel quickly.
    started = client.post("/calibrate/start", json={"seconds_per_phase": 1.0}).json()
    assert started["phase"] in ("idle", "eyes_open", "eyes_closed", "saving", "done", "error")
    client.post("/calibrate/cancel")
    time.sleep(0.5)
    p = client.get("/calibrate/progress").json()
    assert p["phase"] in ("idle", "eyes_open", "eyes_closed", "done", "error")


def test_llm_health_no_crash(client) -> None:
    # Doesn't matter if Ollama is up or not — endpoint must respond.
    r = client.get("/llm/health").json()
    assert "available" in r
    assert isinstance(r["available"], bool)


def test_llm_prose_always_returns_text(client) -> None:
    # Falls back to fixed pool if Ollama is down or model errors.
    r = client.post("/llm/prose", json={}).json()
    assert "text" in r
    assert len(r["text"]) > 30


def test_gatekeeper_status_default_open(client) -> None:
    s = client.get("/gatekeeper/status").json()
    for k in ("quiet", "since_ts", "queued_count", "last_label", "last_decision_reason"):
        assert k in s
    assert s["quiet"] is False  # synthetic 10 Hz inject is alpha — should not lock QUIET
    assert s["queued_count"] == 0


def test_gatekeeper_queue_and_release(client) -> None:
    r = client.post(
        "/gatekeeper/queue",
        json={"source": "slack", "summary": "PR review request", "urgency": "low"},
    ).json()
    assert "queued_id" in r
    assert r["queued_count"] == 1
    # Release via override.
    rel = client.post("/gatekeeper/override", json={"target": "release"}).json()
    assert rel["status"] == "released"
    assert rel["released_count"] == 1
    assert rel["items"][0]["source"] == "slack"
    # Status now empty.
    assert client.get("/gatekeeper/status").json()["queued_count"] == 0


def test_gatekeeper_override_open_quiet(client) -> None:
    s = client.post("/gatekeeper/override", json={"target": "QUIET"}).json()
    assert s["quiet"] is True
    s = client.post("/gatekeeper/override", json={"target": "OPEN"}).json()
    assert s["quiet"] is False


def test_gatekeeper_queue_rejects_bad_urgency(client) -> None:
    r = client.post(
        "/gatekeeper/queue",
        json={"source": "x", "summary": "y", "urgency": "extreme"},
    )
    assert r.status_code == 400


def test_appraisal_status_shape(client) -> None:
    s = client.get("/appraisal/status").json()
    for k in (
        "recent_spike", "since_spike_s", "baseline_n", "baseline_mean",
        "last_z", "caution", "cooldown_seconds", "reason",
    ):
        assert k in s
    # Synthetic stream with no spike injection should never set recent_spike.
    assert s["recent_spike"] is False
    assert s["caution"] is False
    assert s["reason"] == "no_recent_spike"


def test_gatekeeper_queued_peek(client) -> None:
    # Empty initially.
    assert client.get("/gatekeeper/queued").json() == []
    # Add two pings; verify peek returns FIFO and does not drain.
    client.post(
        "/gatekeeper/queue",
        json={"source": "slack", "summary": "PR review", "urgency": "low"},
    )
    client.post(
        "/gatekeeper/queue",
        json={"source": "mail", "summary": "newsletter", "urgency": "low"},
    )
    peek1 = client.get("/gatekeeper/queued").json()
    assert [p["source"] for p in peek1] == ["slack", "mail"]
    # Calling peek again should return the same items — read-only.
    peek2 = client.get("/gatekeeper/queued").json()
    assert peek2 == peek1
    assert client.get("/gatekeeper/status").json()["queued_count"] == 2
