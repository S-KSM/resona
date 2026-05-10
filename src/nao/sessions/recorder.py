"""SessionRecorder — Pipeline subscriber that writes frames when active.

Lifecycle:
    rec = SessionRecorder()
    pipeline.subscribe(rec.on_frame)        # always subscribed; cheap when idle
    rec.start(label="meditate")             # opens jsonl + index entry
    ...                                      # frames flow to disk
    session = rec.stop()                    # closes file, computes summary

When no session is active, on_frame() returns immediately. No-op overhead is
one boolean check per frame — safe to keep wired.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from nao.process.frame import FocusFrame
from nao.sessions.models import Session, SessionSummary
from nao.sessions.store import SessionStore

log = logging.getLogger(__name__)


class SessionRecorder:
    def __init__(self, store: SessionStore | None = None) -> None:
        self.store = store or SessionStore()
        self._lock = threading.Lock()
        self._active: Session | None = None
        # Running aggregates over the active session (clean frames only for
        # mean/std; artifact rate uses all frames).
        self._n_total: int = 0
        self._n_clean: int = 0
        self._sum_focus: float = 0.0
        self._sum_focus_sq: float = 0.0
        self._sum_alpha: float = 0.0
        self._sum_beta: float = 0.0
        self._sum_theta: float = 0.0
        self._sum_asym: float = 0.0
        self._n_asym: int = 0
        self._sum_arousal: float = 0.0
        self._n_arousal: int = 0

    # ---- public ----

    @property
    def active(self) -> Session | None:
        return self._active

    def start(self, label: str, notes: str = "") -> Session:
        with self._lock:
            if self._active is not None:
                # Caller policy: enforce stop-before-start. Surfaces clearly
                # in the API as a 409 instead of silently switching labels.
                raise RuntimeError(f"Session already active: {self._active.id}")
            sid = uuid.uuid4().hex
            self._reset_aggregates()
            self._active = Session(
                id=sid,
                label=label,
                started_at=time.time(),
                notes=notes,
            )
            self.store.upsert(self._active)
            log.info("session start id=%s label=%s", sid, label)
            return self._active

    def stop(self) -> Session | None:
        with self._lock:
            if self._active is None:
                return None
            session = self._active
            session.ended_at = time.time()
            session.summary = self._build_summary(session.started_at, session.ended_at)
            self.store.upsert(session)
            self._active = None
            self._reset_aggregates()
            log.info(
                "session stop id=%s frames=%d clean=%d",
                session.id,
                session.summary.frame_count,
                session.summary.clean_frame_count,
            )
            return session

    def on_frame(self, frame: FocusFrame) -> None:
        # Hot path. Bail before any work when idle.
        if self._active is None:
            return
        # Lock is fine here — recorder is the only writer + serializing per
        # frame keeps summary aggregates consistent if stop() races.
        with self._lock:
            if self._active is None:
                return
            try:
                self.store.append_frame(self._active.id, frame)
            except OSError as e:
                log.warning("session write failed id=%s err=%s", self._active.id, e)
                return
            self._n_total += 1
            if frame.artifact_clean:
                self._n_clean += 1
                self._sum_focus += frame.focus_ema
                self._sum_focus_sq += frame.focus_ema * frame.focus_ema
                self._sum_alpha += frame.alpha
                self._sum_beta += frame.beta
                self._sum_theta += frame.theta
                if frame.frontal_asymmetry is not None:
                    self._sum_asym += frame.frontal_asymmetry
                    self._n_asym += 1
                if frame.arousal_index is not None:
                    self._sum_arousal += frame.arousal_index
                    self._n_arousal += 1

    # ---- internals ----

    def _reset_aggregates(self) -> None:
        self._n_total = 0
        self._n_clean = 0
        self._sum_focus = 0.0
        self._sum_focus_sq = 0.0
        self._sum_alpha = 0.0
        self._sum_beta = 0.0
        self._sum_theta = 0.0
        self._sum_asym = 0.0
        self._n_asym = 0
        self._sum_arousal = 0.0
        self._n_arousal = 0

    def _build_summary(self, started: float, ended: float) -> SessionSummary:
        n = self._n_clean
        focus_mean: Optional[float] = (self._sum_focus / n) if n else None
        focus_std: Optional[float] = None
        if n >= 2 and focus_mean is not None:
            var = max(0.0, (self._sum_focus_sq / n) - (focus_mean * focus_mean))
            focus_std = var ** 0.5
        return SessionSummary(
            frame_count=self._n_total,
            clean_frame_count=n,
            duration_s=max(0.0, ended - started),
            focus_mean=focus_mean,
            focus_std=focus_std,
            alpha_mean=(self._sum_alpha / n) if n else None,
            beta_mean=(self._sum_beta / n) if n else None,
            theta_mean=(self._sum_theta / n) if n else None,
            artifact_rate=(
                (self._n_total - self._n_clean) / self._n_total
                if self._n_total else 0.0
            ),
            asymmetry_mean=(self._sum_asym / self._n_asym) if self._n_asym else None,
            arousal_mean=(self._sum_arousal / self._n_arousal) if self._n_arousal else None,
        )
