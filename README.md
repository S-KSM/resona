# NAO — Neuro-Agentic Orchestration

Local pipeline: **Muse-14B3 EEG → real-time features → MCP server → adaptive AI agents.**

See `SPECS.MD` for the PRD and `PLAN.md` for the live build plan.

## Status

Phase 0 → Phase 1 (M1: vertical slice — ingest, FFT, Focus Coefficient `F=β/α`, Streamlit dashboard).

## Architecture

```
SwiftUI app  ──HTTP/SSE──► Python sidecar (FastAPI :8765)
  ├ MenuBarExtra                          ├ MuseStream (BLE via muselsl)
  ├ Live   (Swift Charts)                 ├ Pipeline (FFT, Focus, Artifacts)
  ├ Setup  (BLE scan + AVSpeech)          ├ MCP server (stdio for AI agents)
  ├ Calibrate (AVSpeech-guided wizard)    └ Ollama client (local LLM)
  └ Coach  (chat w/ injected state)
```

The Streamlit dashboard is still around (`uv run nao-dash`) but the SwiftUI app is the primary UI.

## Quickstart

```bash
# 1. Install Python deps
uv sync --extra dev --extra hardware

# 2. (Optional) Install Ollama for the Coach + neutral-prose generator
brew install ollama
ollama serve &
ollama pull llama3.2:3b   # or qwen2.5:3b, phi3:mini

# 3. Start the Python sidecar
uv run nao-sidecar

# 4. In another terminal, build + run the SwiftUI app
cd swift/NaoBrain
swift run NaoBrain
```

Window opens with 4 tabs (Live, Setup, Calibrate, Coach) and a menu-bar icon
showing live focus + label.

### First-time flow inside the app

1. **Setup** — Scan, click "Use" on your Muse, pick a Premium voice, save.
2. **Calibrate** — Eyes-open phase shows LLM-generated neutral prose; AVSpeech
   guides you through both phases. Saves to `~/.nao/baseline.json`.
3. **Live** — Real-time focus, band power, signal-quality boxes.
4. **Coach** — Ask questions about your brain state. Current FocusFrame +
   recent trend + per-channel quality are auto-injected as context every
   turn, so the local LLM can answer specifically (not generically).

## Streamlit dash (legacy, still works)

```bash
uv run nao-dash
```

## CLI helpers (headless / scripting)

```bash
uv run nao-pair                          # BLE scan
uv run nao-verify --seconds 10           # live-link sanity
uv run nao-calibrate --source muse       # CLI calibration
uv run nao-baseline --duration 60        # raw EEG to CSV
uv run nao-mcp                           # MCP server for AI agents (stdio)
uv run nao-sidecar                       # HTTP/SSE for the SwiftUI app
```

## Wiring an agent to your brain

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nao-brain": {
      "command": "uv",
      "args": ["--directory", "/Users/shobeir/Code/EEG_Agentic", "run", "nao-mcp"],
      "env": { "NAO_SOURCE": "muse" }
    }
  }
}
```

Tools the agent gets:
- `get_user_cognitive_load()` — single label (`deeply_focused | engaged | neutral | resting | uncertain`).
- `get_current_brain_state()` — full FocusFrame (band powers, per-channel α/β, latency).
- `get_focus_history(seconds)` — recent labeled trend.
- `get_calibration()` — personal F baseline (or null).

## Privacy

Raw EEG (µV) **never leaves the Mac**. Only summary scalars (Focus Coefficient, state labels) are exposed via MCP.

## Layout

```
src/nao/
  ingest/   BLE + synthetic streams behind a Stream protocol
  process/  Ring buffer, FFT band power, Focus Coefficient, artifact detection
  dash/     Streamlit Live Brain Load
  scripts/  Pair + baseline recorder
```
