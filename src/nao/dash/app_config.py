"""Persistent config at ~/.nao/config.json.

Read by: dash (active source + voice), MCP server (live source).
Written by: Setup page in the dash, env-var override still wins.
"""
from __future__ import annotations

import json
import os
import pathlib
from dataclasses import asdict, dataclass

from nao.dash.voice import DEFAULT_RATE_WPM, DEFAULT_VOICE

CONFIG_PATH = pathlib.Path.home() / ".nao" / "config.json"


@dataclass
class NaoConfig:
    muse_address: str | None = None
    voice_name: str = DEFAULT_VOICE
    voice_rate: int = DEFAULT_RATE_WPM
    last_source: str = "synthetic"

    def save(self, path: pathlib.Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: pathlib.Path = CONFIG_PATH) -> "NaoConfig":
        if not path.exists():
            return cls()
        d = json.loads(path.read_text())
        # Tolerate older configs missing newer fields.
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})

    def effective_muse_address(self) -> str | None:
        """Env var wins so headless launches still control the address."""
        return os.environ.get("NAO_MUSE_ADDRESS") or self.muse_address
