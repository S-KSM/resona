"""Session schema. Free-text label is allowed; SessionLabel lists the canonical
suggestions the Swift UI surfaces in its dropdown."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Suggested labels — UI picker. Free-text "other" still flows through label.
SessionLabel = Literal[
    "meditate",
    "sleep",
    "deep_work",
    "coding",
    "reading",
    "meeting",
    "rest",
    "other",
]

CANONICAL_LABELS: tuple[str, ...] = (
    "meditate", "sleep", "deep_work", "coding", "reading", "meeting", "rest", "other"
)


class SessionSummary(BaseModel):
    """Aggregate stats over a session's clean frames. Built on stop."""

    frame_count: int = 0
    clean_frame_count: int = 0
    duration_s: float = 0.0
    focus_mean: float | None = None
    focus_std: float | None = None
    alpha_mean: float | None = None
    beta_mean: float | None = None
    theta_mean: float | None = None
    artifact_rate: float = 0.0
    asymmetry_mean: float | None = None
    arousal_mean: float | None = None


class Session(BaseModel):
    """Index entry. Frames live in the sibling JSONL — not embedded here."""

    id: str = Field(description="UUIDv4 hex.")
    label: str = Field(description="User-chosen label, free text. Defaults to canonical set.")
    started_at: float = Field(description="Unix epoch seconds at start.")
    ended_at: float | None = None
    notes: str = ""
    summary: SessionSummary = Field(default_factory=SessionSummary)

    @property
    def is_active(self) -> bool:
        return self.ended_at is None
