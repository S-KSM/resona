"""Neutral-prose generator for the calibration eyes-open phase.

Goal: text that reads naturally but evokes no strong emotion (which would
shift β/α). Domains: weather, geology, mechanics, plant biology, geometry.
Avoid: surprise, humor, conflict, second-person, imperatives, numbers
the reader has to parse.

LLM path generates fresh text each session. Fallback pool used when
Ollama is unavailable so calibration always has prose to show.
"""
from __future__ import annotations

import random

from nao.llm.client import OllamaClient, llm_available

FALLBACK_POOL: list[str] = [
    "The river follows the contour of the valley, widening where the bank "
    "softens and narrowing where stone resists the flow. Sediment settles in "
    "the slower pools. Smaller stones travel further than larger ones, sorted "
    "by the steady, even pull of the current over many seasons.",

    "Cumulus clouds form when warm air rises from the ground and meets cooler "
    "layers above. Water vapor condenses into droplets around small particles "
    "of dust. The clouds appear flat at the base and rounded on top, drifting "
    "slowly with the prevailing wind across the open sky.",

    "A bicycle wheel turns on a steel axle held in place by ball bearings. "
    "The bearings reduce friction between the moving parts. Each ball rolls "
    "in a circular track, distributing the load evenly. The hub spins freely "
    "for many minutes after a single push of the pedal.",

    "Moss grows in shaded places where moisture stays in the air. It has no "
    "true roots; small filaments anchor it to bark or stone. Water is "
    "absorbed across the surface of each tiny leaf. New shoots appear in "
    "spring as the days lengthen and the temperature rises.",

    "A regular hexagon has six equal sides and six equal interior angles. "
    "It tiles the plane without gaps. Honeybees build their combs in this "
    "pattern because it uses the least wax for the most storage. Each cell "
    "shares walls with its neighbors on all sides.",
]


_PROSE_SYSTEM = (
    "Generate one short paragraph (about 70 to 90 words) of emotionally "
    "neutral, factually descriptive prose for a person to read aloud during "
    "an EEG calibration session. Topics: weather patterns, geological "
    "processes, mechanical descriptions, plant biology, geometry. "
    "Constraints: no second-person ('you'), no imperatives, no surprising "
    "facts, no humor or conflict, no proper nouns, plain present-tense "
    "statements, simple syntax. Output ONLY the paragraph."
)


def calibration_prose(seed: int | None = None, model: str | None = None) -> str:
    """Return neutral prose. Tries Ollama; falls back to the fixed pool."""
    if not llm_available():
        rng = random.Random(seed)
        return rng.choice(FALLBACK_POOL)
    try:
        client = OllamaClient(model=model) if model else OllamaClient()
        text = client.chat(
            messages=[
                {"role": "system", "content": _PROSE_SYSTEM},
                {"role": "user", "content": "Generate one neutral paragraph."},
            ],
            temperature=0.7,
        )
        # LLMs sometimes preface with "Here is..." — trim the first line if so.
        text = text.strip()
        if text.lower().startswith(("here is", "here's", "sure", "certainly")):
            parts = text.split("\n\n", 1)
            text = parts[1] if len(parts) > 1 else text
        return text.strip()
    except Exception as e:  # noqa: BLE001
        rng = random.Random(seed)
        return rng.choice(FALLBACK_POOL)
