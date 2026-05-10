"""Session tracking — Start/Stop labeled recordings of FocusFrames.

The user labels what they're doing (meditate, sleep, deep_work, coding, ...);
frames are appended to per-session JSONL on disk. Foundation for per-label
baselines down the line.

Privacy invariant held: only FocusFrames hit disk (band powers + label +
affect scalars). No raw microvolts.
"""
from nao.sessions.models import Session, SessionLabel, SessionSummary
from nao.sessions.recorder import SessionRecorder
from nao.sessions.store import SessionStore

__all__ = ["Session", "SessionLabel", "SessionSummary", "SessionRecorder", "SessionStore"]
