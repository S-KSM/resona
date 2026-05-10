# NAO Build Plan

Living doc. Updated as work progresses. Source of truth = `SPECS.MD`. Phase = 0→1.

Last updated: 2026-05-09 (M4.1 + M4.2 shipped — bundle 0.3.0 (3))

---

## North Star

Muse-14B3 → local pipeline → MCP server → agents adapt to brain state. Sensor-to-agent <500 ms. Raw EEG never leaves the Mac.

## Decisions (locked 2026-05-09)

| Choice | Pick | Why |
|---|---|---|
| Env mgr | `uv` | Fast, lockfile, 2026 default |
| Streaming lib | `muselsl` (live) + OpenMuse-stub (future swap) | OpenMuse not yet on PyPI as of 2026-05-09; Stream protocol abstracts choice |
| Hardware status | On hand, not paired | Need pair-helper script + synthetic fallback |
| M1 scope | Full Phase-1 vertical slice | Ingest → FFT → Focus Coef → Streamlit dash |
| Python | 3.12+ | Per SPECS |

## Architecture (M1 vertical slice)

```
[Muse-14B3 BLE]                        [synthetic generator]
       │                                       │
       └──────► Stream protocol ◄──────────────┘
                        │
                        ▼
                 RingBuffer (1s @ 256Hz)
                        │
            ┌───────────┼────────────┐
            ▼           ▼            ▼
        Welch/FFT   Artifact     Motion (accel)
        band power  detector     reject mask
            │           │            │
            └────► FocusCoef F=β/α ◄──┘
                        │
                        ▼
                 Streamlit Dashboard
                 (live F, α/β bars,
                  artifact badges,
                  latency readout)
```

Future (Phase 2): pipeline output also fans into MCP server exposing `get_user_cognitive_load`.

## Layout

```
EEG_Agentic/
  pyproject.toml          uv-managed
  PLAN.md                 this file
  SPECS.MD                PRD
  CLAUDE.md               agent guide
  src/nao/
    __init__.py
    config.py             constants: SAMPLE_RATE=256, ALPHA=(8,13), BETA=(13,30), WINDOW_S=1.0
    ingest/
      stream.py           Stream protocol + Sample dataclass
      synthetic.py        SyntheticStream — pink noise + injected sinusoids per band
      muse.py             MuseStream — OpenMuse wrapper, BLE
    process/
      buffer.py           RingBuffer
      bands.py            band_power(window) → {alpha, beta, theta, ...}
      focus.py            focus_coef(α, β) → F
      artifacts.py        blink/jaw/motion flags; uses accel
      pipeline.py         orchestrate buffer → features → emit
    dash/
      app.py              Streamlit app
  scripts/
    pair_muse.py          Bleak scan; print MAC; sanity connect
    record_baseline.py    60s record → CSV (matches SPECS §3 Phase 0)
  tests/
    test_bands.py         FFT correctness on synthetic sinusoids
    test_focus.py         F=β/α arithmetic
    test_artifacts.py     motion mask
    test_pipeline.py      end-to-end synthetic → F values stable
```

## Workstreams (parallelizable after scaffold)

1. **Scaffold** — pyproject (uv), pkg, config, README stub. *Blocks all.*
2. **Ingest** — Stream protocol + Synthetic + Muse + accel passthrough.
3. **Process** — RingBuffer, FFT band power, FocusCoef, artifact detection.
4. **Dash** — Streamlit live view.
5. **Pair helper + baseline** — `pair_muse.py`, `record_baseline.py`.
6. **Tests** — pytest, signal-processing correctness on synthetic.

Critical path: Scaffold → (Ingest stream protocol) → Process → Dash. Pair-helper independent.

## Latency budget (sensor → dash)

| Stage | Budget | Notes |
|---|---|---|
| BLE jitter | ~100 ms | OpenMuse buffering |
| Ring-buffer fill (window stride) | 250 ms | Use 1s window, 250ms stride |
| FFT + features | <10 ms | 256-sample Welch, NumPy |
| Streamlit redraw | ~100 ms | `st.empty()` + `st.rerun` polling at 4 Hz |
| **Total** | **~460 ms** | Under 500 ms ✓ |

If overshoot: drop to 512-sample window @ 200ms stride; offload dash to async polling client.

## Privacy invariants (do not violate)

- Raw µV stays on disk + RAM only. No remote upload paths in M1.
- Only summary scalars (F, state label) ever cross process boundary.
- MCP server (Phase 2) returns labels not raw arrays.

## Open questions / ideas (capture as we go)

Resolved (M1+M2 build):
- [x] Welch over raw FFT — done.
- [x] Per-channel α/β kept in FocusFrame; channel-averaged F is the headline.
- [x] Personal baseline → `~/.nao/baseline.json` via `nao-calibrate`. Z-scoring shifts labels.
- [x] Theta/delta/gamma all in FocusFrame from day 1.
- [x] Filtering: scipy butter+notch in pipeline (cheaper than MNE Raw on hot path; MNE held for offline analysis).
- [x] EMA smoother (α=0.3).
- [x] Artifact policy: flagged + surfaced (dash + MCP); MCP returns `uncertain` not silent garbage.
- [x] Synthetic stream seedable.
- [x] FocusFrame pydantic model — exposed by MCP unchanged.
- [x] Pipeline.subscribe fan-out (dash + MCP history both subscribe).

Open:
- [x] **Frontal-only F variant** for Gatekeeper — *resolved partially*. Computed inside `nao.agents.gatekeeper.frontal.frontal_focus()` from `alpha_per_channel[1:3]` / `beta_per_channel[1:3]`. FocusFrame schema unchanged on the wire; if the frontal-F proves stable in production, promote it to a `frontal_focus_ema` field on FocusFrame as a follow-up. *(2026-05-09, M3.0)*
- [x] **Reward-spike detector** — *resolved*. Phase-2 Skeptic agent shipped end-to-end (pure logic + MCP tool + HTTP). `src/nao/agents/skeptic/{detector,policy,fsm}.py`. Welford rolling baseline of frontal-gamma (AF7+AF8); spike = z ≥ 2.5 with refractory window + warmup gate; artifact-clean frames only. `get_appraisal_state` MCP tool + `GET /appraisal/status` return `recent_spike` / `since_spike_s` / `caution` / `cooldown_seconds`. `gamma_per_channel` promoted to FocusFrame schema. **13 unit tests + 1 HTTP test.** *(2026-05-09, M3.6)*
- [ ] **MCP transport choice for Phase 3 multi-agent**: stdio works for one-on-one Claude Desktop; need SSE/HTTP if Gatekeeper + Skeptic + audio agent all subscribe simultaneously.
- [ ] **A2A wiring** (SPECS Phase 3): "Primary Neuro-Agent" delegates to Worker Agents based on fatigue. Theta/Alpha ratio is the trigger metric — already in FocusFrame.
- [ ] **Lyria 3 audio loop** (SPECS Phase 3): single-subscriber pattern → `pipeline.subscribe(audio_agent.on_frame)`.
- [ ] **Per-label baselines** (M3.9 follow-up): once ≥3 sessions per label exist, derive `~/.nao/baselines/<label>.json` (mean/std for F + frontal asymmetry + arousal). LiveView shows "vs your meditate baseline" instead of just global z-score. Skip until enough data; don't pre-build the analysis.
- [ ] **Affect surfacing in Coach + LiveView** (M4.0 follow-up): once `frontal_asymmetry` + `arousal_index` are in FocusFrame, expose two-axis valence/arousal display + extend `current_state_block` so Coach can answer "how do I feel?" with honest scope ("frontal alpha is shifted left vs your meditate baseline" — not "you feel sad").
- [x] **Calibration drift** — *resolved*. `Calibration.saved_at` (epoch seconds) + `age_days()` + `is_stale()` (>7 days). Worker stamps at construction; `/calibration` and `get_calibration` MCP tool expose `saved_at` / `age_days` / `is_stale`. Calibrate-tab shows an age badge — orange triangle + "stale, re-calibrate" past 7 days. Legacy baselines without `saved_at` load cleanly and are treated as unknown age (no nag). *(2026-05-09, M3.5)*
- [x] **Bad-contact fast-path** — *resolved*. Gatekeeper FSM tracks a continuous BAD_CONTACT streak (default 5 s) and forces fail-open with `reason="signal_uncertain"`; persistent contact loss never triggers QUIET. *(2026-05-09, M3.0)*
- [x] **Promote frontal-F to FocusFrame schema** — *resolved*. `frontal_focus` (raw β/α from AF7+AF8) and `frontal_focus_ema` (EMA-smoothed) added as nullable fields. Pipeline computes once via `frontal_focus_from_powers(alpha_pc, beta_pc)`; Gatekeeper reads from frame instead of recomputing. Channel-averaged `focus_ema` kept for backward compat. Swift `FocusFrame` mirrors. *(2026-05-09, M3.3)*
- [x] **Peek-queued endpoint** — *resolved*. `GET /gatekeeper/queued` (read-only) + `get_queued_pings` MCP tool + `GatekeeperFSM.peek_queued()`. Quiet tab now lists pending pings (source, summary, urgency dot) in-place, not just a count. NaoClient refreshes the queued list whenever `queued_count` changes. *(2026-05-09, M3.2)*
- [x] **`test_api.py` fixture hangs** — *resolved*. Two root causes, neither was sse-starlette: (1) `Pipeline._run` gated frame emit on `buffer.is_full()` which compares against `DISPLAY_SECONDS=4s` capacity, not `WINDOW_SAMPLES=1s`; first frame took 3.5 s, fixture's `time.sleep(2.0)` was too short. Fixed: gate on `len(buffer) >= window_samples`. (2) `runtime.start_calibration` held `_lock` and called `get_pipeline()` which re-acquired the same non-reentrant lock → deadlock at `POST /calibrate/start`. Fixed: `_lock = threading.RLock()`. Bonus: `_say` now short-circuits when `voice_name is None`, matching the documented intent. All 12 test_api tests green; full suite 106 passed in 41 s. *(2026-05-09, M3.1)*

## Risks

- BLE flakiness on Mac → keep retry/backoff in MuseStream.
- OpenMuse API drift (still young lib) → wrap behind our `Stream` so we can swap to `muselsl` if needed.
- Sensor contact poor → dash must surface "bad contact" state, not silently emit garbage F.

## Milestones

- **M4.2** ✅ **Muse full-signal ingest shipped.** `Sample` carries `gyro` + `ppg` (zero-default for synthetic & old callers). `MuseStream` muselsl path passes `acc_enabled=True ppg_enabled=True gyro_enabled=True` and resolves Accelerometer / Gyroscope / PPG LSL outlets on best-effort background threads. OpenMuse path gains `on_gyro` + `on_ppg`. `RingBuffer` extended with parallel gyro/ppg arrays + `latest_aux()`. New `nao.process.hrv`: bandpass 0.7-3 Hz + peak detection + median IBI → `heart_rate_bpm`; RMSSD over IBIs → `hrv_rmssd`. `nao.process.artifacts.detect_artifacts` accepts a `gyro_window` and raises MOTION when angular velocity exceeds `MOTION_GYRO_DPS_THRESH=60 deg/s`. FocusFrame gains nullable `heart_rate_bpm`, `hrv_rmssd`, `gyro_max`. Pipeline computes once per emit. **9 HRV tests + 161 total green.** *(2026-05-09)*
- **M4.1** ✅ **Session exploration + Coach insights shipped.** New "Sessions" Swift tab — `NavigationSplitView` with sortable list (label, duration, focus, asymmetry, noisy badge) and detail page: focus chart with biggest-drop annotation, frontal-asymmetry timeline, summary cards, quartile chips, calibration z-score, label-baseline delta, embedded Coach chat panel with seeded suggestion chips. `nao.sessions.insights.build_insights()` produces a Coach-ready digest (timeline binned to 30 buckets, per-quartile focus, trend slope, biggest drop, vs-calibration z-score, vs-label-baseline delta). New endpoints: `GET /session/{id}/frames?step=N` (capped 4000 pts), `GET /session/{id}/insights`, `POST /session/{id}/chat` — Coach LLM gets a session-scoped system prompt that injects the digest and forbids fabrication. **7 insights tests; LLM smoke test cites real numbers from the digest.** *(2026-05-09)*

- **M3.9** ✅ **Session tracking shipped.** `src/nao/sessions/{models,store,recorder}.py`. SessionRecorder subscribes to Pipeline, no-ops when idle, writes per-frame JSONL to `~/.nao/sessions/<id>.jsonl` and an index.json with finalized SessionSummary (frame_count, focus_mean/std, asymmetry_mean, arousal_mean, artifact_rate, duration). API: `POST /session/start` (409 if active), `POST /session/stop`, `GET /session/active`, `GET /sessions`, `GET /session/{id}`, `DELETE /session/{id}`. Active session auto-stops on `restart_pipeline()`. Swift `SessionStrip` on Live tab: idle → label picker (8 canonical + custom) + notes; recording → red-dot blink + label chip + mm:ss + frame count + Stop. **10 unit tests + 145 total green.** *(2026-05-09)*
- **M4.0** ✅ **Affect axes shipped.** `src/nao/process/affect.py` — `frontal_asymmetry(alpha_per_channel) = log(α_AF8) − log(α_AF7)` (Davidson; positive = approach/positive valence) + `arousal_index(α, β, γ) = (β + γ) / α`. Both nullable `FocusFrame` fields, computed once in `Pipeline._emit_frame`. Returns `None` on missing/non-positive/non-finite inputs — callers must treat as "no signal" not zero. Surfacing in LiveView + Coach deferred to follow-up. **9 unit tests.** *(2026-05-09)*

- **M1.0** ✅ Scaffold + synthetic stream + tests green. *(2026-05-09)*
- **M1.1** ✅ FFT + Focus + artifacts on synthetic. Pipeline emits FocusFrames. Latency <100ms compute. *(2026-05-09)*
- **M1.2** ✅ Streamlit dash live on synthetic. Ready: `uv run nao-dash`. *(2026-05-09)*
- **M1.3** ✅ Hardware extras installed; `nao-pair` found Muse-14B3 (CoreBluetooth UUID `92A2548A-78AE-…`). *(2026-05-09)*
- **M1.4** ✅ Full live pipeline. `nao-verify` confirms 256 Hz EEG with sane µV ranges (frontal std~12, temporal std~50). Personal baseline recorded: F mean=0.30, std=0.29. Eyes-closed F < eyes-open (α rose) → biologically plausible signal. Saved to `~/.nao/baseline.json`. *(2026-05-09)*
- **M2.0** ✅ MCP server `nao-brain` exposes get_user_cognitive_load / get_current_brain_state / get_focus_history / get_calibration. brain://state resource. Source via NAO_SOURCE env. *(2026-05-09)*
- **M3.8** ✅ **Installed.** `/Applications/NaoBrain.app` (release binary, branded `.icns`, ad-hoc codesigned). Sidecar runs from `~/Library/LaunchAgents/com.nao.sidecar.plist` (RunAtLoad + KeepAlive on crash + 30 s throttle; logs to `~/.nao/sidecar.{log,err}`). User runs zero commands. Surfaced + fixed a `pipeline ↔ gatekeeper.frontal` import cycle that only triggered when sidecar booted via launchctl (test order had been hiding it) — lazy-imported `frontal_focus_from_powers` inside `_emit_frame`. **126 tests still green.** *(2026-05-09)*
- **M3.7** ✅ **Skeptic SwiftUI surface.** New 6th tab with state card (orange dot when caution), baseline panel (clean-sample count + frontal-γ mean + warmup hint), how-agents-use-this explanation, honesty disclaimer. NaoClient publishes `appraisal: AppraisalState?` and refreshes every 2 s alongside Gatekeeper. Menu-bar shows `⚠︎ Skeptic caution — Xs cooldown` row only when active. swift build clean. *(2026-05-09)*
- **M3.6** ✅ **Skeptic agent — Phase-2 second flagship.** Frontal-gamma reward-spike detector with Welford rolling baseline + refractory + warmup gate + artifact gating. `gamma_per_channel` added to FocusFrame. New MCP tool `get_appraisal_state` + HTTP `GET /appraisal/status` return spike state and a `caution` flag for cooperating agents that are about to *affirm* a user's recent choice. Pure-logic + 13 tests + runtime wiring + 1 HTTP test. SwiftUI surface deferred. **126 passed in 49 s.** *(2026-05-09)*
- **M3.5** ✅ **Calibration drift warning shipped.** `saved_at` stamped at construction; `age_days()` + `is_stale()` (>7d) on Calibration. `/calibration` + MCP `get_calibration` expose drift. Calibrate-tab shows age badge with orange triangle when stale. Legacy baselines without `saved_at` load cleanly (unknown age, no nag). **112 passed in 43 s.** *(2026-05-09)*
- **M3.4** ✅ **Frontal-F surfaced in LiveView.** New "Frontal F (EMA)" metric card (brand amber) + third chart series so divergence vs the 4-channel mean is visible at a glance. Legend dots above the chart. *(2026-05-09)*
- **M3.3** ✅ **Frontal-F promoted to schema.** `frontal_focus` + `frontal_focus_ema` are first-class FocusFrame fields. Pipeline computes once; Gatekeeper consumes from frame. Backward-compatible (nullable; old serialized frames still validate). Swift mirrors. **110 passed in 46 s.** *(2026-05-09)*
- **M3.2** ✅ **Queue peek shipped.** `GET /gatekeeper/queued` + `get_queued_pings` MCP tool + Quiet-tab list view. 2 new tests; 108 passed in 51 s. *(2026-05-09)*
- **M3.1** ✅ **`test_api.py` fixture unblocked.** Pipeline emit-gate fixed (compare against window_samples, not capacity). `runtime._lock` promoted to `RLock` to break a `start_calibration → get_pipeline` self-deadlock. `_say` honors `voice_name=None`. Full suite: **106 passed in 41 s** including 4 new Gatekeeper HTTP tests. *(2026-05-09)*
- **M3.0** ✅ **Gatekeeper agent shipped as Phase-2 flagship.** Pure decision logic in `src/nao/agents/gatekeeper/` (policy + FSM + frontal-only F). 3 new MCP tools (`should_interrupt`, `notify_queued`, `get_quiet_status`) + 3 new sidecar HTTP endpoints + `quiet` field on `/events` SSE. SwiftUI gets a 5th "Quiet" tab + menu-bar quiet badge + a `FocusModeBridge` that runs user-installed Shortcuts (`Resona Quiet On/Off`). 63 new tests in `test_gatekeeper.py`; 94 non-API tests green. Honest scope documented in-app: no third-party notification interception, only advisory `should_interrupt` for cooperating agents. *(2026-05-09)*

## Changelog

- 2026-05-09: **M3.1 — test_api fixture unblocked.** Three real bugs, not the assumed sse-starlette / lifespan hand-wave.
  - `Pipeline._run` gated emit on `buffer.is_full()` (DISPLAY_SECONDS=4s capacity) instead of `len(buffer) >= window_samples` (1s). First frame took 3.5 s; fixture's `time.sleep(2.0)` saw only `warmup`.
  - `runtime.start_calibration` held `_lock` and called `get_pipeline()` which tried to re-acquire it → `POST /calibrate/start` deadlocked the test harness. Fix: `_lock = threading.RLock()`.
  - `calibration_worker._say` now early-returns when `voice_name is None`, matching the runtime docstring's intent (Swift drives voice via AVSpeechSynthesizer).
  - **Result**: 4 previously skipped Gatekeeper HTTP tests now run + pass; full suite **106 passed in 41 s**.

- 2026-05-09: **M3.0 — Gatekeeper agent + Resona rebrand.** Phase-2 flagship.
  - **Branding**: product renamed **Resona** ("your mind, in tune."). Assets in `branding/`: `resona-icon.svg`, `resona-logo.svg`, `resona-mark.svg`, `BRAND.md`, `MARKETING.md`. Python package and CLIs still `nao` until a code rename is greenlit.
  - **Architecture pivot — honest:** macOS does not let third parties intercept other apps' notifications without MDM. So Gatekeeper's product surface is the **advisory** MCP tool `should_interrupt(urgency)` that cooperating agents (Claude Desktop, Cursor, custom MCP clients) call before speaking. Secondary path: drive macOS Focus via user-installed Shortcuts. Tertiary: queued-pings panel.
  - **Pure logic**: `src/nao/agents/gatekeeper/{policy,frontal,fsm}.py`. 63 unit tests, sub-µs `decide()`.
  - **State machine**: OPEN ↔ QUIET. `enter_seconds=12` of clean engaged-or-better → QUIET; `exit_seconds=8` of sub-engaged → OPEN; `bad_contact_streak_s=5` forces OPEN; 3 s entry-grace lets medium urgency through.
  - **Frontal-only F**: AF7/AF8 (channel indices 1, 2) preferred over channel-averaged when per-channel data present. Computed inside Gatekeeper; FocusFrame schema unchanged.
  - **Wired to runtime**: `runtime.py` instantiates `GatekeeperFSM`, subscribes alongside `_history.append`, exposes `get_gatekeeper()`. Reset on `restart_pipeline()`.
  - **MCP**: `should_interrupt`, `notify_queued`, `get_quiet_status` decorators in `mcp/server.py`. Privacy invariant held — only labels + booleans.
  - **HTTP**: `GET /gatekeeper/status`, `POST /gatekeeper/queue`, `POST /gatekeeper/override` (target ∈ OPEN | QUIET | release). `quiet: bool` added to `/events` SSE payload.
  - **SwiftUI**: 5th "Quiet" tab (`QuietView`) with status, manual override, queued surface, honesty disclaimer, Focus-shortcut setup hint. `MenuBarMenu` shows 🔕/🔔 badge + force-OPEN/QUIET + release-queued. New `FocusModeBridge.swift` runs Shortcuts named `Resona Quiet On` / `Resona Quiet Off` on QUIET ↔ OPEN edges. `swift build` clean (1.67 s).
  - **Discovery**: `tests/test_api.py`'s real-Pipeline TestClient fixture hangs in pytest (pre-existing — sub-agent reproduced on a clean checkout); same pattern via direct `TestClient(app)` works fine. Gatekeeper endpoints smoke-tested via direct script. New pytest cases written into `test_api.py` but blocked on the fixture fix; tracked in Open Questions.

- 2026-05-09: **SwiftUI Mac app + local LLM Coach shipped.** Big architectural turn.
  - **Architecture:** Python sidecar (FastAPI on `:8765` via `nao-sidecar`) + SwiftUI app (`swift run NaoBrain`). Sidecar owns the singleton Pipeline; both MCP server and HTTP API consume the same instance — no double BLE.
  - **Swift app:** `swift/NaoBrain/Package.swift`, executable target. SourceKit indexing complains a lot; actual `swift build` succeeds. macOS 14+ for MenuBarExtra + Charts.
  - 4 tabs: Live (Swift Charts), Setup (BLE scan + AVSpeech voice picker), Calibrate (AVSpeech-guided), Coach (chat).
  - **AVSpeechSynthesizer** replaces macOS `say` — Premium/Enhanced voices ship with the OS, no manual install needed. **Discovery:** Apple renamed `AVSpeechSynthesisVoice.Quality` → top-level `AVSpeechSynthesisVoiceQuality` in MacOSX26.4 SDK. Patched.
  - **MenuBarExtra** shows live `🧠 0.42 · engaged` indicator; menu has band powers + restart pipeline + open window.
  - **SSE for live frames** at `/events`; REST for everything else. Swift `URLSession.bytes(for:).lines` consumes line-by-line.
  - **Local LLM via Ollama** (optional). `nao/llm/`: client + EEG-skilled system prompt + neutral-prose generator. Auto-resolves model: if configured `llama3.2:3b` not installed, falls back to first available (e.g. `qwen3:4b`). Graceful degrade when Ollama not running — prose uses fixed pool, Coach tab shows install hint.
  - **Calibration prose:** LLM generates ~80-word emotionally neutral paragraph on weather/geology/mechanics/biology/geometry for the eyes-open phase to read. No imperatives, no proper nouns, simple syntax.
  - **Skills for the Coach:** system prompt has full domain primer (channels, bands, F formula, calibration math, label thresholds, artifact taxonomy + fixes). Per-turn injection of current FocusFrame + 10s trend + per-channel signal quality + calibration baseline as JSON.
  - **API endpoints:** /health, /state, /events (SSE), /history, /signal/quality, /config (GET+POST), /sources/scan, /pipeline/restart, /calibration, /calibrate/{progress,start,cancel,reset}, /llm/{health,models,prose,chat}.
  - **Streamlit dash kept for legacy** but Swift is primary UI now.
  - 8 new API tests; existing 31 still green.


- 2026-05-09: **Dash promoted to full Brain Console** — pairing, voice picker, calibration moved into the UI.
  - 3 pages via `st.navigation`: Live | Setup | Calibrate.
  - **Setup page:** Bleak scan button, address picker, persistent `~/.nao/config.json`, voice picker w/ Test button, calibration status w/ age warning.
  - **Calibrate page:** voice-guided 2-phase wizard. Worker thread runs the sequence; UI polls progress at 2 Hz. Shows phase chip, countdown progress bar, live F sparkline split by phase, before/after means with α-rose-correctly check.
  - **On-device TTS** via macOS `say`. Defaults to Samantha (always present). `voice.py` parses `say -v ?` output, sorts Premium/Neural first. No network, no model download — pure CoreAudio.
  - **Persistent config** at `~/.nao/config.json` (muse_address, voice_name, voice_rate, last_source). Read by both dash and MCP server. Env vars (`NAO_MUSE_ADDRESS`, `NAO_SOURCE`) still override for headless launches.
  - **Discovery:** Streamlit `st.Page` runs view files as scripts — module-level `render()` calls fire on `import` too, flooding ScriptRunContext warnings during smoke tests. Guarded each view with `if __name__ == "__main__":`.
  - 7 new tests (voice parser, premium-flag detection, calibration worker progression + cancellation + saved-baseline). Total 31/31 green.


- 2026-05-09: Plan created. Decisions locked. Scaffolding starts.
- 2026-05-09: M1.0 + M1.1 + M1.2 shipped. Pipeline + dash + tests green (19/19).
  - **Discovery:** `openmuse` not on PyPI as of today. Pivoted: `muselsl 2.3.1` is primary BLE; OpenMuse remains aspirational. `Stream` protocol means ingest can swap when OpenMuse publishes — no upstream changes needed.
  - Hardware deps moved to optional `[hardware]` extra so dev/CI doesn't need BLE stack: `uv sync --extra dev` for processing work, `uv sync --extra hardware` adds muselsl/bleak/mne.
  - `MuseStream._stream_muselsl` is the live path; `_stream_openmuse` stays as future-swap stub.
- 2026-05-09: **M1.3 + M1.4 shipped — first real brain signal.**
  - **Discovery:** muselsl 2.3.1 + py3.13 had asyncio.get_event_loop() crash in non-main thread; patched MuseStream._stream_muselsl to install a fresh loop per spawn thread.
  - macOS surfaces Muse as a CoreBluetooth UUID, not a MAC. Address pattern: `92A2548A-78AE-C8A4-71DA-2C3430AB3201`.
  - muselsl atexit BleakBackend disconnect produces a "Future attached to different loop" traceback on shutdown — known upstream bug, cosmetic only, ignore.
  - Personal F values for this user are tiny (~0.3, not the SPECS-default ~2.5 range). Z-score calibration is not optional; without it every label would say "resting".
  - **Bug fixed during calibration analysis:** `_collect` in calibrate.py subscribed without unsubscribing → phase-2 frames double-counted. Added `Pipeline.unsubscribe()` and gated subscription in a try/finally.
- 2026-05-09: **M2.0 shipped (Phase 2 jumpstart).** MCP server `nao-brain` (FastMCP, mcp 1.27) + `nao.state` labeling + personal calibration system.
  - 4 tools: get_user_cognitive_load, get_current_brain_state, get_focus_history, get_calibration. Resource brain://state.
  - SPECS-aligned threshold F>=2.5 → `deeply_focused`. Artifacts force `uncertain` (agents must not act on noisy F).
  - Personal calibration via `nao-calibrate` (eyes-open + eyes-closed phases) → `~/.nao/baseline.json`. Z-scoring makes labels user-relative.
  - Privacy invariant held: no raw waveforms exposed; only summary scalars + per-channel band powers.
  - Tests now 24/24. Functional smoke (synthetic 22 Hz inject) returns label=deeply_focused, latency 1.2 ms.
  - **Discovery:** `mcp` SDK at 1.27.1 — FastMCP DX is clean (decorator tools). No swap needed.
