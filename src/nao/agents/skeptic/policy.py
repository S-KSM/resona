"""Appraisal-bias advice — pure decision table.

Cooperating agents call this before *affirming* a user's recent decision
(e.g., "yes, ship it"; "yes, send the email"). When the user just experienced
a reward spike, their judgment is biased toward the reinforcing option; the
Skeptic suggests the agent slow down or cite a counter-consideration.

Outputs are advisory — agents may ignore. Mirrors the Gatekeeper policy
table's tone.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AppraisalAdvice:
    """One advisory verdict.

    Attributes:
        caution: True if the agent should soften / probe / counter-cite.
        cooldown_seconds: how long the advice remains active.
        reason: short machine-friendly tag.
    """

    caution: bool
    cooldown_seconds: float
    reason: str


# How long after a spike to keep flagging "still under reward influence".
_BIAS_WINDOW_S = 30.0


def advise(*, recent_spike: bool, since_spike_s: float | None) -> AppraisalAdvice:
    """Decide whether to caution the cooperating agent.

    `recent_spike` reflects whether the FSM is currently within `_BIAS_WINDOW_S`
    of the last detected gamma burst; `since_spike_s` is the wall-clock
    distance and is informational. The decision rule is intentionally simple
    so unit-test coverage is exhaustive.
    """
    if recent_spike:
        remaining = _BIAS_WINDOW_S - (since_spike_s or 0.0)
        return AppraisalAdvice(
            caution=True,
            cooldown_seconds=max(0.0, remaining),
            reason="recent_reward_spike",
        )
    return AppraisalAdvice(
        caution=False,
        cooldown_seconds=0.0,
        reason="no_recent_spike",
    )
