"""Skeptic FSM — rolling baseline + reward-spike detection over FocusFrames.

Why a Welford running mean/variance:
- Streaming-friendly (single pass, O(1) per frame).
- Numerically stable for the long horizons we care about (10s of minutes).

Spike rule:
- Skip frames where `artifact_clean=False` — jaw clench artifacts shred the
  gamma band; including them would constantly trigger false-positives.
- Compare current frontal gamma to the running baseline; flag a spike when
  z = (g - mean) / std exceeds `z_threshold` (default 2.5).
- Refractory window prevents back-to-back triggers on a single sustained
  elevation (e.g., one long thought).
- A baseline must have at least `warmup_n` clean samples before any spike
  is reported — otherwise early-session variance produces nonsense.

State exposed via `state()`:
    {
        "recent_spike": bool,        # within BIAS window of last spike
        "since_spike_s": float|None, # seconds since last spike
        "baseline_n": int,           # clean samples in baseline
        "baseline_mean": float|None,
        "last_z": float|None,
    }
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

from nao.agents.skeptic.detector import frontal_gamma
from nao.agents.skeptic.policy import AppraisalAdvice, advise
from nao.process.frame import FocusFrame

log = logging.getLogger(__name__)

# Window inside which a spike still counts as "recent". Matches policy._BIAS_WINDOW_S
# but kept independent so policy.py owns the agent-facing constant.
RECENT_SPIKE_WINDOW_S = 30.0


@dataclass(slots=True)
class RewardSpike:
    ts: float
    z: float
    gamma: float


@dataclass(slots=True)
class AppraisalState:
    """Snapshot returned by `state()`. Plain dict for JSON serialization."""

    recent_spike: bool
    since_spike_s: float | None
    baseline_n: int
    baseline_mean: float | None
    last_z: float | None


class _Welford:
    """Running mean + variance via Welford's algorithm."""

    __slots__ = ("n", "mean", "_m2")

    def __init__(self) -> None:
        self.n: int = 0
        self.mean: float = 0.0
        self._m2: float = 0.0

    def push(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self._m2 += delta * delta2

    @property
    def std(self) -> float:
        if self.n < 2:
            return 0.0
        return math.sqrt(self._m2 / (self.n - 1))


class SkepticFSM:
    """Detects reward-state gamma bursts on a streaming FocusFrame source.

    Args:
        z_threshold: z-score above which a clean frame is a spike.
        refractory_s: minimum seconds between consecutive spike triggers.
        warmup_n: minimum baseline samples before any spike is reported.
        recent_window_s: window inside which a past spike still counts as recent.
    """

    def __init__(
        self,
        *,
        z_threshold: float = 2.5,
        refractory_s: float = 2.0,
        warmup_n: int = 60,  # ~15s @ 4 Hz
        recent_window_s: float = RECENT_SPIKE_WINDOW_S,
    ) -> None:
        self.z_threshold = z_threshold
        self.refractory_s = refractory_s
        self.warmup_n = warmup_n
        self.recent_window_s = recent_window_s

        self._baseline = _Welford()
        self._last_spike: RewardSpike | None = None
        self._last_frame_ts: float | None = None
        self._last_z: float | None = None

    # --- public API ---------------------------------------------------

    def on_frame(self, frame: FocusFrame) -> RewardSpike | None:
        """Consume one frame; return a RewardSpike if one was detected."""
        ts = frame.ts
        self._last_frame_ts = ts

        if not frame.artifact_clean:
            # Don't update baseline from artifact-corrupted frames; jaw-clench
            # alone can sit at >5σ and would poison the running stats.
            return None

        g = frontal_gamma(frame)
        if g is None or not math.isfinite(g):
            return None

        # Compute z BEFORE updating, so a real spike doesn't silently pull
        # the baseline up to meet itself.
        z: float | None = None
        if self._baseline.n >= self.warmup_n and self._baseline.std > 0:
            z = (g - self._baseline.mean) / self._baseline.std
            self._last_z = z

        spike: RewardSpike | None = None
        in_refractory = (
            self._last_spike is not None
            and (ts - self._last_spike.ts) < self.refractory_s
        )
        if (
            z is not None
            and z >= self.z_threshold
            and not in_refractory
        ):
            spike = RewardSpike(ts=ts, z=z, gamma=g)
            self._last_spike = spike
            log.info("skeptic: reward spike at ts=%.3f z=%.2f gamma=%.3f", ts, z, g)
            # Don't fold a spike sample into the baseline — it's an outlier.
            return spike

        # Normal sample: extend the baseline.
        self._baseline.push(g)
        return None

    def state(self) -> dict:
        s = self._snapshot()
        return {
            "recent_spike": s.recent_spike,
            "since_spike_s": s.since_spike_s,
            "baseline_n": s.baseline_n,
            "baseline_mean": s.baseline_mean,
            "last_z": s.last_z,
        }

    def advise(self) -> AppraisalAdvice:
        """Convenience: combine current state with `policy.advise()`."""
        s = self._snapshot()
        return advise(recent_spike=s.recent_spike, since_spike_s=s.since_spike_s)

    # --- internals ----------------------------------------------------

    def _snapshot(self) -> AppraisalState:
        since: float | None = None
        recent = False
        if self._last_spike is not None and self._last_frame_ts is not None:
            since = max(0.0, self._last_frame_ts - self._last_spike.ts)
            recent = since <= self.recent_window_s
        return AppraisalState(
            recent_spike=recent,
            since_spike_s=since,
            baseline_n=self._baseline.n,
            baseline_mean=(self._baseline.mean if self._baseline.n > 0 else None),
            last_z=self._last_z,
        )


# SPECS-level alias.
Skeptic: type[SkepticFSM] = SkepticFSM
_State = Literal["idle", "ready"]  # reserved; not used today but documents future surface
