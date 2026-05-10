"""Gatekeeper finite state machine.

Subscribes to Pipeline FocusFrames and maintains a hysteretic OPEN ↔ QUIET
state. The MCP tool layer calls `decide(urgency)` which combines the current
state with the policy table in `policy.py`.

Why a separate FSM (instead of just calling policy on every frame)?
- **Hysteresis.** Raw labels jitter; we want sustained focus before going
  QUIET, and sustained sub-focus before coming back. Cheap, stops
  notifications oscillating.
- **Bad-contact guard.** If the headband loses contact for `bad_contact_streak_s`
  we force OPEN — never let a fallen-off sensor silence the user's apps.
- **Queueing.** Cooperating agents that get blocked can drop a ping into
  the FSM's bounded deque; the FSM hands them back when it returns to OPEN.

All state mutation goes through `on_frame` (frames are the clock) or the
explicit user methods (`queue`, `release_queued`, `manual_override`).
`time.monotonic()` is used only for streak / override timing — frame
timestamps drive state transitions so unit tests can be deterministic.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from nao.agents.gatekeeper.frontal import frontal_focus
from nao.agents.gatekeeper.policy import Decision, Urgency, decide
from nao.process.frame import FocusFrame
from nao.state import Calibration, CognitiveLoad, label_focus, label_frame

log = logging.getLogger(__name__)

State = Literal["OPEN", "QUIET"]
ManualTarget = Literal["OPEN", "QUIET"]

_MANUAL_OVERRIDE_S = 60.0
_QUEUE_MAXLEN = 50


@dataclass(slots=True)
class QueuedPing:
    """A notification that asked to interrupt while QUIET — held for replay."""

    id: str
    source: str
    summary: str
    urgency: str
    queued_at: float


@dataclass(slots=True)
class _FrameStreak:
    """Tracks 'how long has the focus condition been continuously true?'

    Driven by FocusFrame timestamps so tests can advance time by setting ts.
    """

    started_at: float | None = None

    def update(self, condition: bool, ts: float) -> float:
        """Push a new sample; return the current run-length in seconds."""
        if not condition:
            self.started_at = None
            return 0.0
        if self.started_at is None:
            self.started_at = ts
            return 0.0
        return max(0.0, ts - self.started_at)

    def reset(self) -> None:
        self.started_at = None


class GatekeeperFSM:
    """Hysteretic OPEN ↔ QUIET state machine over FocusFrames.

    Args:
        enter_seconds: sustained engaged-or-better required to enter QUIET.
        exit_seconds: sustained sub-engaged required to exit QUIET.
        bad_contact_streak_s: BAD_CONTACT seen for this long forces OPEN
            and reports `signal_uncertain=True` to the policy layer.
        entry_grace_s: window after entering QUIET where medium urgency
            still gets through (avoids slamming the door on in-flight pings).
    """

    def __init__(
        self,
        *,
        enter_seconds: float = 12.0,
        exit_seconds: float = 8.0,
        bad_contact_streak_s: float = 5.0,
        entry_grace_s: float = 3.0,
    ) -> None:
        self.enter_seconds = enter_seconds
        self.exit_seconds = exit_seconds
        self.bad_contact_streak_s = bad_contact_streak_s
        self.entry_grace_s = entry_grace_s

        self._state: State = "OPEN"
        self._state_since_ts: float | None = None
        self._last_frame_ts: float | None = None
        self._last_label: CognitiveLoad = "uncertain"
        self._last_decision_reason: str = "init"

        # Streaks driven by frame timestamps.
        self._enter_streak = _FrameStreak()
        self._exit_streak = _FrameStreak()
        self._bad_contact_streak = _FrameStreak()
        # True when bad_contact_streak_s has been exceeded; cleared on first
        # clean frame.
        self._signal_uncertain: bool = False

        # Queue of pings deferred while QUIET. Bounded so a runaway agent
        # can't OOM us. Drops oldest on overflow (FIFO).
        self._queue: deque[QueuedPing] = deque(maxlen=_QUEUE_MAXLEN)

        # Manual override: sticky for 60s of monotonic wall time.
        self._manual_target: ManualTarget | None = None
        self._manual_until_mono: float = 0.0

    # --- public API --------------------------------------------------

    @property
    def state(self) -> State:
        """Current effective state, honoring active manual override."""
        if self._manual_active():
            return self._manual_target  # type: ignore[return-value]
        return self._state

    @property
    def quiet(self) -> bool:
        return self.state == "QUIET"

    def on_frame(self, frame: FocusFrame, calibration: Calibration | None = None) -> None:
        """Consume one FocusFrame; update streaks and state.

        Frames are the clock — we use `frame.ts` (monotonic seconds from the
        Pipeline) for hysteresis timing rather than wall time, so synthetic
        streams and tests behave identically to real hardware.
        """
        ts = frame.ts
        self._last_frame_ts = ts

        # Bad-contact streak: continuous BAD_CONTACT in artifact list.
        bad_contact = "BAD_CONTACT" in frame.artifact
        bad_run = self._bad_contact_streak.update(bad_contact, ts)
        if bad_run >= self.bad_contact_streak_s and bad_contact:
            self._signal_uncertain = True
            self._last_decision_reason = "bad_contact_streak"
            self._force_open(ts)
            self._last_label = "uncertain"
            return
        if not bad_contact:
            # First clean frame clears the latched flag.
            self._signal_uncertain = False

        # Compute label using the canonical state.label_frame so artifact
        # gating and calibration shifts stay consistent with the rest of NAO.
        label = label_frame(frame, calibration)

        # Prefer frontal focus when per-channel data is present; this
        # tightens the attention signal vs the 4-channel mean. Gate it
        # through label_focus so thresholds match the rest of the system,
        # then defer to label_frame's artifact decision.
        ff = frontal_focus(frame)
        if ff is not None and frame.artifact_clean:
            shifted = ff
            if calibration is not None:
                shifted = calibration.zscore(ff) + 1.5
            label = label_focus(shifted)

        self._last_label = label

        # Hysteretic transitions.
        focused_now = label in ("engaged", "deeply_focused")
        sub_engaged_now = label in ("neutral", "resting")

        if self._state == "OPEN":
            self._exit_streak.reset()
            run = self._enter_streak.update(focused_now, ts)
            if run >= self.enter_seconds:
                self._state = "QUIET"
                self._state_since_ts = ts
                self._enter_streak.reset()
                log.info("gatekeeper: OPEN -> QUIET at ts=%.3f (label=%s)", ts, label)
        else:  # QUIET
            self._enter_streak.reset()
            run = self._exit_streak.update(sub_engaged_now, ts)
            if run >= self.exit_seconds:
                self._state = "OPEN"
                self._state_since_ts = ts
                self._exit_streak.reset()
                log.info("gatekeeper: QUIET -> OPEN at ts=%.3f (label=%s)", ts, label)

    def decide(
        self,
        urgency: Urgency,
        calibration: Calibration | None = None,  # noqa: ARG002 - kept for symmetry / future use
    ) -> Decision:
        """Answer should_interrupt(urgency). Hot path — keep it cheap."""
        # Manual override short-circuits everything — user wins over BCI.
        if self._manual_active():
            assert self._manual_target is not None
            if self._manual_target == "OPEN":
                d = Decision(True, None, "manual_override_open", self._last_label)
            else:
                # Manual QUIET: still fail-open on high urgency.
                if urgency == "high":
                    d = Decision(True, None, "manual_override_quiet_high", self._last_label)
                else:
                    defer = 60.0 if urgency == "medium" else 300.0
                    d = Decision(False, defer, "manual_override_quiet", self._last_label)
            self._last_decision_reason = d.reason
            return d

        # Bad-signal escape hatch (FSM-level — keeps policy.decide pure).
        if self._signal_uncertain:
            d = Decision(True, None, "signal_uncertain", self._last_label)
            self._last_decision_reason = d.reason
            return d

        # Inside the entry-grace window we relax medium so in-flight pings
        # aren't slammed shut the instant we go QUIET.
        if (
            self._state == "QUIET"
            and self._state_since_ts is not None
            and self._last_frame_ts is not None
            and (self._last_frame_ts - self._state_since_ts) < self.entry_grace_s
            and urgency == "medium"
        ):
            d = Decision(True, None, "entry_grace_failopen", self._last_label)
            self._last_decision_reason = d.reason
            return d

        # Otherwise consult the policy table. We treat artifact_clean=True
        # because the FSM has already absorbed signal-quality concerns into
        # `_signal_uncertain`; passing False would double-count.
        d = decide(
            self._last_label,
            urgency,
            artifact_clean=True,
            signal_uncertain=False,
        )
        self._last_decision_reason = d.reason
        return d

    def queue(self, source: str, summary: str, urgency: str) -> str:
        """Queue a ping that was deferred. Returns its id (uuid4 hex)."""
        ping = QueuedPing(
            id=uuid.uuid4().hex,
            source=source,
            summary=summary,
            urgency=urgency,
            queued_at=time.monotonic(),
        )
        # deque(maxlen=...) silently drops oldest on overflow — log it.
        if len(self._queue) == self._queue.maxlen:
            log.warning("gatekeeper: queue full (%d), dropping oldest", self._queue.maxlen)
        self._queue.append(ping)
        return ping.id

    def release_queued(self) -> list[QueuedPing]:
        """Drain and return all queued pings in FIFO order."""
        out = list(self._queue)
        self._queue.clear()
        return out

    def peek_queued(self) -> list[QueuedPing]:
        """Return queued pings in FIFO order without draining."""
        return list(self._queue)

    def status(self) -> dict:
        """Snapshot for UI / sidecar. No raw EEG numbers."""
        return {
            "quiet": self.quiet,
            "since_ts": self._state_since_ts,
            "queued_count": len(self._queue),
            "last_label": self._last_label,
            "last_decision_reason": self._last_decision_reason,
        }

    def manual_override(self, target: ManualTarget) -> None:
        """User-driven override. Sticky for 60s, then FSM resumes control."""
        self._manual_target = target
        self._manual_until_mono = time.monotonic() + _MANUAL_OVERRIDE_S
        log.info("gatekeeper: manual override %s for %.0fs", target, _MANUAL_OVERRIDE_S)

    def clear_manual_override(self) -> None:
        """Drop any active override immediately."""
        self._manual_target = None
        self._manual_until_mono = 0.0

    # --- internals ---------------------------------------------------

    def _manual_active(self) -> bool:
        if self._manual_target is None:
            return False
        if time.monotonic() >= self._manual_until_mono:
            self._manual_target = None
            return False
        return True

    def _force_open(self, ts: float) -> None:
        if self._state != "OPEN":
            self._state = "OPEN"
            self._state_since_ts = ts
        self._enter_streak.reset()
        self._exit_streak.reset()


# Friendly alias matching the SPECS-level "Gatekeeper" name.
Gatekeeper = GatekeeperFSM
