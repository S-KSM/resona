# Resona — Features

A local-first brain-computer interface for the Muse-14B3. Built around one
invariant: raw brainwaves never leave your Mac. Only summary state ever
crosses a process boundary.

---

## Live brain-state pipeline
4 EEG channels (TP9/AF7/AF8/TP10) → bandpass + Welch FFT → α/β/θ/δ/γ powers
→ **Focus Coefficient F = β/α**. End-to-end < 500 ms.
**So what.** A live, calibrated, plotted readout of your engagement state — no
cloud round-trip, no subscription.

## Personal calibration
60 s eyes-open + eyes-closed wizard saves a baseline (`mean F`, `std F`) to
`~/.nao/baseline.json`. All labels and z-scores are user-relative.
**So what.** Your "deeply focused" is your number, not a population average —
critical because raw F varies 10× between people.

## Session tracking
Start/Stop on the Live tab with a label (meditate / sleep / deep_work /
coding / reading / meeting / rest / custom) + free-text notes. Every frame
is appended to `~/.nao/sessions/<id>.jsonl`; an index records the summary.
**So what.** A growing private corpus of *your* brain across activities, ready
for analysis without anyone else seeing it.

## Session exploration + Coach insights
A dedicated **Sessions** tab. Detail view shows the focus timeline with the
biggest-drop pinned, frontal-asymmetry chart, per-quartile means, slope,
calibration z-score, and delta-vs-prior-sessions of the same label. An
embedded Coach chat panel is pre-loaded with the session digest.
**So what.** Ask "where did I lose focus in this two-hour study?" or
"how did this compare to my reading sessions?" and the local LLM cites
real numbers from your actual recording — not speculation.

## Affect axes (valence + arousal)
Frontal alpha asymmetry (Davidson, AF8 vs AF7) tracks approach/withdrawal
valence; arousal index `(β + γ) / α` tracks activation.
**So what.** A defensible 2-axis read on emotional state from 4 dry electrodes,
without the over-claim that consumer EEG can classify discrete emotions.

## Heart rate + HRV
Muse PPG → bandpass + peak detection → `heart_rate_bpm` (±2 bpm at rest)
+ RMSSD parasympathetic proxy.
**So what.** Two independent physiology channels (cortical + cardiac) at once
— so "calm brain, racing heart" is visible instead of being averaged into
one number.

## Motion-aware artifact rejection
Accelerometer (gravity deviation) + gyroscope (angular velocity) + EEG
quality flags (BLINK / JAW / BAD_CONTACT) gate every frame. Dirty windows
get the `uncertain` label and downstream agents must not act.
**So what.** No silent garbage. When a sensor lifts off your mastoid bone,
the app tells you which channel and how to reseat it.

## Gatekeeper (advisory notification suppressor)
A pure-logic FSM (OPEN ↔ QUIET) consumed by cooperating agents via the MCP
tool `should_interrupt(urgency)`. Drives macOS Focus on edge transitions
through user-installed Shortcuts.
**So what.** Your Coach / Cursor / custom MCP clients can ask your brain
"is now a good moment?" before pinging you. Honest scope: macOS doesn't
let third parties intercept other apps' notifications, so cooperation is
the lever.

## Skeptic (reward-spike caution)
Frontal-γ (AF7+AF8) Welford-rolling-baseline reward-spike detector with
refractory + warmup gates. Surfaces a `caution` flag when an agent is
about to *affirm* something the user is currently rewarding.
**So what.** A brake on flattery loops — agents can avoid amplifying a
just-felt dopamine bump that would distort judgment.

## MCP server for downstream agents
Tools: `get_user_cognitive_load`, `get_current_brain_state`,
`get_focus_history`, `get_calibration`, `should_interrupt`,
`get_appraisal_state`, `get_queued_pings`. Resource: `brain://state`.
**So what.** Any MCP-aware agent (Claude Desktop, Cursor, custom) can read
brain state as easily as reading a database — without ever touching µV.

## Architecture
Python sidecar (FastAPI on `:8765` + MCP server) holds the singleton
pipeline; SwiftUI menu-bar app (`/Applications/NaoBrain.app`) consumes
HTTP/SSE. One BLE connection feeds both. `launchd` keeps the sidecar
alive. Synthetic stream lets you build the whole stack with the band off.
**So what.** Hack on it without owning a Muse, deploy without writing a
single CLI command after install, run forever in the background.

---

Stack: Python 3.12 · `uv` · `muselsl` + `bleak` · `MNE`-aware processing ·
FastAPI · MCP-SDK · SwiftUI / Swift Charts · Ollama (optional, local LLM).
Tests: 161 pytest green · `swift build` clean.
