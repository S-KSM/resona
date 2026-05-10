# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

Implementation underway. Layout:

- `src/nao/` — Python package (Py 3.12, `uv` + `pyproject.toml`). Subpackages: `ingest/` (Muse + synthetic streams), `dash/` (Streamlit + calibration worker + voice), `api/` (FastAPI sidecar with `/state`, `/events` SSE, `/config`, `/scan`), `mcp/` (MCP server), `agents/`, `llm/`, `scripts/` (pair, calibrate, baseline, verify).
- `swift/NaoBrain/` — Swift Package menu-bar SwiftUI client. Talks to the `nao-sidecar` over HTTP/SSE. Views: Setup, Live, Calibrate, Coach, Skeptic, Quiet, MenuBar.
- `tests/` — pytest suite (artifacts, bands, focus, pipeline, gatekeeper, skeptic, calibration, api, voice, state).
- `SPECS.MD`, `PLAN.md`, `README.md`, `branding/`.

Source of truth for product intent is `SPECS.MD`; current task list is `PLAN.md`.

## Build / Test / Run

Python (from repo root):
- `uv sync --extra hardware --extra dev` — install with Muse BLE stack + dev tools
- `uv run pytest` — full suite; `uv run pytest tests/test_focus.py -k name` to target
- `uv run ruff check src tests` — lint
- Entry points (defined in `pyproject.toml`): `nao-sidecar`, `nao-dash`, `nao-mcp`, `nao-pair`, `nao-calibrate`, `nao-baseline`, `nao-verify`

Swift client:
- `cd swift/NaoBrain && swift build` — debug build
- `swift run NaoBrain` — launch menu-bar app (sidecar must be running on default port)

## Architecture (Target, per SPECS.MD)

The system is a **four-stage local pipeline** where each stage's output feeds the next, and the entire chain must stay under **500 ms** sensor-to-agent latency:

1. **Ingest** — Muse-14B3 over BLE (4 EEG channels: TP9, AF7, AF8, TP10 @ 256 Hz, plus accelerometer/gyro). Streamed via `OpenMuse` / `muselsl` using `Bleak` for BLE handling.
2. **Process** — Raw µV decoded to Pandas DataFrames; `MNE-Python` for signal processing; FFT to derive Alpha (8–13 Hz) and Beta (13–30 Hz) band power. The headline derived metric is the **Focus Coefficient** `F = β / α`.
3. **Expose** — A local **MCP server** (`MCP-SDK`) exposes brain state as a tool/resource (e.g. `get_user_cognitive_load`, `get_current_brain_state`) that other agents query.
4. **Act** — Downstream agents (Gatekeeper for notifications, Skeptic for appraisal bias, generative audio, etc.) consume the brain-state context and adapt behavior.

### Architectural invariants — do not violate without discussion

- **Local-only EEG processing.** Raw brainwaves never leave the Mac. Only high-level state summaries ("User is Focused") may be sent to remote LLM APIs. This is a privacy guardrail, not a performance choice.
- **Direct-to-compute.** No Raspberry Pi or other intermediary between headband and host.
- **Motion-rejection required.** The accelerometer feed exists specifically to filter movement artifacts from EEG; any feature-extraction code should consume it, not ignore it.
- **Latency budget is 500 ms end-to-end.** Architectural choices (buffering, sync vs async, model size) should be made against this budget.

### Artifact awareness

EEG signals contain large non-brain artifacts that must be handled, not treated as signal:
- Blinks → sharp "V" shapes in AF7/AF8
- Jaw clenches → high-frequency static across all channels
- Poor sensor contact → flat line or random noise

## Roadmap Phase

Phase 1 (FFT + Focus Coefficient + Streamlit dashboard) and Phase 2 scaffolding (MCP server, Gatekeeper, Skeptic, FastAPI sidecar, SwiftUI client) are landed in skeleton form — see `src/nao/` and `swift/NaoBrain/`. Active focus per `PLAN.md`: hardening the Resona/Gatekeeper flagship loop. Phase 3 (Lyria 3 audio, A2A multi-agent, closed-loop biofeedback) still deferred — prefer work that advances the current flagship over speculative Phase 3 scaffolding.

Note: product is being rebranded **Resona** (decision 2026-05-09); Python package name remains `nao` until a rename is greenlit.

## Stack Choices Already Decided

- Python 3.12+
- `OpenMuse` (preferred) or `muselsl` for streaming — not custom BLE
- `Bleak` for BLE
- `MNE-Python` for neuro-signal processing
- `MCP-SDK` for agent integration
- Streamlit for the local dashboard

When adding dependencies, prefer these over alternatives unless there's a concrete reason to deviate.
