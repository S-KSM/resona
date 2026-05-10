"""Cognitive-state labeling — central thresholds, used by MCP + dash.

Labels are intentionally coarse (5 buckets). Raw F is informative but agents
need categorical context to act on. Thresholds are SPECS-derived:
SPECS §3 Phase 2 sets F > 2.5 as the "Gatekeeper silences notifications" cutoff.

Personal calibration (~/.nao/baseline.json) z-scores F so labels are
user-relative — a "focused" F for one person may be "neutral" for another.
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import Literal

from nao.process.frame import FocusFrame

CognitiveLoad = Literal[
    "deeply_focused", "engaged", "neutral", "resting", "uncertain"
]

# Defaults assume z-scored F where 0 ≈ user's average. If no baseline file
# exists, raw F is used and these thresholds are SPECS-aligned.
DEFAULT_THRESHOLDS = {
    "deeply_focused": 2.5,  # SPECS Phase-2 Gatekeeper cutoff
    "engaged": 1.5,
    "neutral": 0.8,
    "resting": 0.0,
}

CALIBRATION_PATH = pathlib.Path.home() / ".nao" / "baseline.json"


CALIBRATION_STALE_DAYS = 7.0


@dataclass(frozen=True, slots=True)
class Calibration:
    mean_f: float
    std_f: float
    n_samples: int
    # Unix epoch seconds when this baseline was written. None for legacy files
    # saved before drift-tracking — those are treated as age unknown.
    saved_at: float | None = None

    def zscore(self, f: float) -> float:
        return (f - self.mean_f) / max(self.std_f, 1e-6)

    def age_days(self, *, now: float | None = None) -> float | None:
        """Days since this baseline was written, or None if `saved_at` is unset."""
        if self.saved_at is None:
            return None
        return max(0.0, ((now if now is not None else time.time()) - self.saved_at) / 86400.0)

    def is_stale(self, *, now: float | None = None, threshold_days: float = CALIBRATION_STALE_DAYS) -> bool:
        """True if older than `threshold_days`. Unknown age → not stale (don't nag)."""
        age = self.age_days(now=now)
        return age is not None and age > threshold_days

    def to_json(self) -> str:
        d: dict[str, float | int | None] = {
            "mean_f": self.mean_f,
            "std_f": self.std_f,
            "n_samples": self.n_samples,
        }
        if self.saved_at is not None:
            d["saved_at"] = self.saved_at
        return json.dumps(d, indent=2)

    @classmethod
    def load(cls, path: pathlib.Path = CALIBRATION_PATH) -> "Calibration | None":
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        return cls(
            mean_f=d["mean_f"],
            std_f=d["std_f"],
            n_samples=d["n_samples"],
            saved_at=d.get("saved_at"),
        )

    def save(self, path: pathlib.Path = CALIBRATION_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


def label_focus(f: float) -> CognitiveLoad:
    """Map a (possibly z-scored) F to a coarse cognitive-load bucket."""
    if f >= DEFAULT_THRESHOLDS["deeply_focused"]:
        return "deeply_focused"
    if f >= DEFAULT_THRESHOLDS["engaged"]:
        return "engaged"
    if f >= DEFAULT_THRESHOLDS["neutral"]:
        return "neutral"
    return "resting"


def label_frame(
    frame: FocusFrame, calibration: Calibration | None = None
) -> CognitiveLoad:
    """Apply calibration + artifact gating to produce a single label.

    Artifacts force "uncertain" — agents should not act on garbage F values.
    """
    if not frame.artifact_clean:
        return "uncertain"
    f = frame.focus_ema
    if calibration is not None:
        f = calibration.zscore(f) + 1.5  # shift so user-baseline ≈ "engaged"
    return label_focus(f)
