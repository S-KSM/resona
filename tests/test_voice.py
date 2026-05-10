"""Voice helper — parser correctness + safe no-op on non-Mac."""
from __future__ import annotations

from nao.dash.voice import parse_voices, say_available, speak

SAMPLE_OUTPUT = """\
Albert              en_US    # Hello! My name is Albert.
Alice               it_IT    # Ciao! Mi chiamo Alice.
Ava (Premium)       en_US    # Hello! My name is Ava.
Samantha            en_US    # Hello! My name is Samantha.
Zoe (Enhanced)      en_US    # Hi! I'm Zoe.
"""


def test_parse_voices_extracts_name_locale_sample() -> None:
    voices = parse_voices(SAMPLE_OUTPUT)
    names = {v.name for v in voices}
    assert "Albert" in names
    assert "Ava (Premium)" in names
    ava = next(v for v in voices if v.name == "Ava (Premium)")
    assert ava.locale == "en_US"
    assert ava.sample.startswith("Hello")


def test_premium_flag() -> None:
    voices = parse_voices(SAMPLE_OUTPUT)
    premium = {v.name for v in voices if v.is_premium}
    assert premium == {"Ava (Premium)", "Zoe (Enhanced)"}


def test_speak_no_op_when_say_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("nao.dash.voice.say_available", lambda: False)
    # Should not raise even with say absent.
    assert speak("hello") is None


def test_say_available_returns_bool() -> None:
    assert isinstance(say_available(), bool)
