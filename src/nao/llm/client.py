"""Ollama HTTP client. Stays optional — if Ollama isn't running we degrade
gracefully instead of crashing.

Ollama default port: 11434. Install: `brew install ollama && ollama serve`.
Recommended models: `ollama pull llama3.2:3b` (default), `phi3:mini`, `qwen2.5:3b`.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Iterator

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("NAO_LLM_MODEL", "llama3.2:3b")


def llm_available(base_url: str = DEFAULT_BASE_URL, timeout: float = 1.5) -> bool:
    """True if Ollama is reachable. Cached calls = the source of truth for the
    /llm/health endpoint."""
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        return r.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


@dataclass
class OllamaClient:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = 60.0

    def list_models(self) -> list[str]:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except httpx.HTTPError:
            return []

    def resolve_model(self) -> str:
        """Return self.model if installed, else the first available model.
        Raises if Ollama has no models at all."""
        installed = self.list_models()
        if self.model in installed:
            return self.model
        if installed:
            log.warning("Model %s not installed; falling back to %s", self.model, installed[0])
            return installed[0]
        raise RuntimeError(
            "No Ollama models installed. Run e.g. `ollama pull llama3.2:3b`."
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.4,
    ) -> str:
        """One-shot chat. Returns the assistant message. Blocking."""
        payload = {
            "model": self.resolve_model(),
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        r = httpx.post(
            f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.4,
    ) -> Iterator[str]:
        """Yield assistant tokens as they arrive."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        with httpx.stream(
            "POST", f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = obj.get("message", {}).get("content", "")
                if msg:
                    yield msg
                if obj.get("done"):
                    return
