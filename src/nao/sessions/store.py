"""Disk layout for sessions.

    ~/.nao/sessions/
        index.json          [Session, ...] — append-only, rewritten on each end/update
        <id>.jsonl          one FocusFrame.model_dump_json() per line

JSONL chosen over Parquet to avoid pulling pyarrow into core deps; ~1 MB/hr at
4 Hz frames is fine. Loaders convert to DataFrame on read.
"""
from __future__ import annotations

import json
import pathlib
import threading
from typing import Iterable

from nao.process.frame import FocusFrame
from nao.sessions.models import Session

DEFAULT_ROOT = pathlib.Path.home() / ".nao" / "sessions"


class SessionStore:
    """Filesystem-backed index + JSONL writer/reader.

    Thread-safe for concurrent writes (one lock per store instance). The
    Recorder owns a single store instance per process.
    """

    def __init__(self, root: pathlib.Path | None = None) -> None:
        self.root = pathlib.Path(root) if root is not None else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._lock = threading.Lock()

    # ---- index ----

    def list_sessions(self) -> list[Session]:
        if not self._index_path.exists():
            return []
        try:
            raw = json.loads(self._index_path.read_text())
        except json.JSONDecodeError:
            return []
        return [Session.model_validate(d) for d in raw]

    def get(self, session_id: str) -> Session | None:
        for s in self.list_sessions():
            if s.id == session_id:
                return s
        return None

    def upsert(self, session: Session) -> None:
        with self._lock:
            sessions = self.list_sessions()
            replaced = False
            for i, s in enumerate(sessions):
                if s.id == session.id:
                    sessions[i] = session
                    replaced = True
                    break
            if not replaced:
                sessions.append(session)
            self._index_path.write_text(
                json.dumps([s.model_dump() for s in sessions], indent=2)
            )

    # ---- frame jsonl ----

    def jsonl_path(self, session_id: str) -> pathlib.Path:
        return self.root / f"{session_id}.jsonl"

    def append_frame(self, session_id: str, frame: FocusFrame) -> None:
        # Open per-write to keep the recorder restartable; stride is 250 ms so
        # the open/close cost is negligible vs the FFT we just did.
        with self._lock, self.jsonl_path(session_id).open("a") as fh:
            fh.write(frame.model_dump_json() + "\n")

    def read_frames(self, session_id: str) -> list[FocusFrame]:
        path = self.jsonl_path(session_id)
        if not path.exists():
            return []
        out: list[FocusFrame] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(FocusFrame.model_validate_json(line))
        return out

    def iter_frames(self, session_id: str) -> Iterable[FocusFrame]:
        path = self.jsonl_path(session_id)
        if not path.exists():
            return iter(())
        def _gen():
            with path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    yield FocusFrame.model_validate_json(line)
        return _gen()

    def delete(self, session_id: str) -> bool:
        with self._lock:
            sessions = [s for s in self.list_sessions() if s.id != session_id]
            self._index_path.write_text(
                json.dumps([s.model_dump() for s in sessions], indent=2)
            )
            path = self.jsonl_path(session_id)
            if path.exists():
                path.unlink()
                return True
            return False
