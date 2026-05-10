"""On-device TTS via macOS `say`.

`say` uses CoreAudio voices that ship with macOS — fully on-device, no network.
Premium / Neural voices ("Ava (Premium)") sound better; install via
System Settings → Accessibility → Spoken Content → System Voice → Manage Voices.
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass

DEFAULT_VOICE = "Samantha"  # always present on macOS, en_US
DEFAULT_RATE_WPM = 175

_VOICE_LINE_RE = re.compile(r"^(.+?)\s+([a-z]{2}_[A-Z]{2})\s+#\s*(.+)$")


@dataclass(frozen=True, slots=True)
class Voice:
    name: str
    locale: str
    sample: str

    @property
    def is_premium(self) -> bool:
        n = self.name.lower()
        return any(k in n for k in ("premium", "enhanced", "neural"))


def say_available() -> bool:
    return platform.system() == "Darwin" and shutil.which("say") is not None


def parse_voices(raw: str) -> list[Voice]:
    """Parse the output of `say -v ?`. Whitespace-separated, fixed-ish width."""
    out: list[Voice] = []
    for line in raw.splitlines():
        m = _VOICE_LINE_RE.match(line)
        if m:
            out.append(Voice(name=m.group(1).strip(), locale=m.group(2), sample=m.group(3).strip()))
    return out


def list_voices(locale_prefix: str = "en") -> list[Voice]:
    """Return en_* voices sorted Premium/Neural first, then alphabetically."""
    if not say_available():
        return []
    proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=False)
    voices = [v for v in parse_voices(proc.stdout) if v.locale.startswith(locale_prefix)]
    voices.sort(key=lambda v: (not v.is_premium, v.name.lower()))
    return voices


def speak(
    text: str,
    voice: str | None = DEFAULT_VOICE,
    rate_wpm: int = DEFAULT_RATE_WPM,
    blocking: bool = True,
) -> subprocess.Popen | None:
    """Speak `text` via `say`. Returns the process when blocking=False so the
    caller can interrupt. No-op (and returns None) on non-Mac systems.
    """
    if not say_available():
        return None
    cmd = ["say", "-r", str(rate_wpm)]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    if blocking:
        subprocess.run(cmd, check=False)
        return None
    return subprocess.Popen(cmd)
