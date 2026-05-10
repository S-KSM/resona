"""Gatekeeper agent — advisory notification suppressor.

SPECS §3 Phase 2: cooperating agents (and the macOS sidecar) call
`should_interrupt(urgency)` before speaking. The Gatekeeper consults
brain-state (FocusFrame stream) and answers allow / defer.

Privacy invariant: this module is local-only. It never sees raw EEG —
only the FocusFrames the Pipeline already exposes — and never forwards
anything beyond the categorical Decision.
"""
from __future__ import annotations

from nao.agents.gatekeeper.frontal import frontal_focus
from nao.agents.gatekeeper.fsm import Gatekeeper, GatekeeperFSM, QueuedPing
from nao.agents.gatekeeper.policy import Decision, Urgency, decide

__all__ = [
    "Decision",
    "Gatekeeper",
    "GatekeeperFSM",
    "QueuedPing",
    "Urgency",
    "decide",
    "frontal_focus",
]
