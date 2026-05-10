"""Skeptic — Phase-2 appraisal-bias agent.

Detects transient frontal-gamma bursts (cognitive reward / "aha" / agreement
signals) over a rolling baseline. Cooperating agents query
`get_appraisal_state()` before reinforcing the user's recent choice — the
Skeptic flags moments where the user is likely riding a reward wave and may
not be the best judge of their own decisions.

Distinct from the Gatekeeper (which gates *interruption*); the Skeptic gates
*affirmation*.
"""
from nao.agents.skeptic.detector import frontal_gamma, frontal_gamma_from_powers
from nao.agents.skeptic.fsm import (
    AppraisalState,
    RewardSpike,
    SkepticFSM,
)
from nao.agents.skeptic.policy import AppraisalAdvice, advise

__all__ = [
    "AppraisalAdvice",
    "AppraisalState",
    "RewardSpike",
    "SkepticFSM",
    "advise",
    "frontal_gamma",
    "frontal_gamma_from_powers",
]

# Friendly alias matching the SPECS-level name.
Skeptic = SkepticFSM
