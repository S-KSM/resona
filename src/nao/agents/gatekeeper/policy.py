"""Pure decision policy for the Gatekeeper.

SPECS §3 Phase 2: cooperating agents call `should_interrupt(urgency)` before
speaking. This module is the *single source of truth* for what we say back.

Design notes:
- **Fail open.** A noisy or unknown signal must NOT silence the user's apps.
  When `signal_uncertain` or the underlying frame is dirty, allow=True with
  reason="signal_uncertain". Privacy/utility tradeoff: better one extra
  notification than a brittle BCI that swallows alerts the user needed.
- **Pure function, no I/O, no globals.** Trivially testable; cheap enough to
  call from the MCP tool path on every interrupt request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nao.state import CognitiveLoad

Urgency = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class Decision:
    """Result of `decide(...)`. Returned over the wire as a plain dict."""

    allow: bool
    defer_seconds: float | None
    reason: str
    label: CognitiveLoad


# Defer durations in seconds. Tweakable here; FSM doesn't second-guess them.
_DEFER_DEEP_LOW = 300.0
_DEFER_DEEP_MED = 60.0
_DEFER_ENGAGED_LOW = 180.0
_DEFER_ENGAGED_MED = 30.0


def decide(
    label: CognitiveLoad,
    urgency: Urgency,
    *,
    artifact_clean: bool,
    signal_uncertain: bool,
) -> Decision:
    """Map (label, urgency, signal-quality) to an allow / defer Decision.

    Order matters — the noisy-signal escape hatch is checked first so we can
    never block on bad data. After that we walk the policy table.
    """
    # 1. Fail open on bad signal — never block on noise.
    if signal_uncertain or not artifact_clean:
        return Decision(
            allow=True,
            defer_seconds=None,
            reason="signal_uncertain",
            label=label,
        )

    # 2. Warmup or genuinely uncertain label (FSM hasn't decided yet).
    if label == "uncertain":
        return Decision(
            allow=True,
            defer_seconds=None,
            reason="warmup_or_uncertain",
            label=label,
        )

    # 3. Deep focus — protect aggressively.
    if label == "deeply_focused":
        if urgency == "high":
            return Decision(True, None, "high_urgency_breakthrough", label)
        if urgency == "medium":
            return Decision(False, _DEFER_DEEP_MED, "deeply_focused_block", label)
        # low
        return Decision(False, _DEFER_DEEP_LOW, "deeply_focused_block", label)

    # 4. Engaged — defer non-urgent stuff but don't bury it as long.
    if label == "engaged":
        if urgency == "high":
            return Decision(True, None, "high_urgency_breakthrough", label)
        if urgency == "medium":
            return Decision(False, _DEFER_ENGAGED_MED, "engaged_brief_defer", label)
        # low
        return Decision(False, _DEFER_ENGAGED_LOW, "engaged_low_defer", label)

    # 5. Neutral / resting — let everything through.
    if label == "neutral":
        return Decision(True, None, "neutral_open", label)
    if label == "resting":
        return Decision(True, None, "resting_open", label)

    # Fallthrough (Literal exhaustion): be conservative and allow.
    return Decision(True, None, "unknown_label_failopen", label)
