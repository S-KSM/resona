"""Record a personal F baseline and write ~/.nao/baseline.json.

Two phases (default 60s each):
  1. Eyes-open, neutral task (read a screen).
  2. Eyes-closed, relaxed (high alpha → low F expected).

The pooled mean+std becomes the user-relative reference: future labels
are z-scored against it so "focused" means focused FOR YOU, not for an
average human.
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np

from nao.ingest.muse import MuseStream
from nao.ingest.synthetic import SyntheticStream
from nao.process.frame import FocusFrame
from nao.process.pipeline import Pipeline
from nao.state import Calibration


def _collect(pipeline: Pipeline, seconds: float, label: str) -> list[FocusFrame]:
    print(f"\n[{label}] Recording {seconds:.0f}s. Hold still.")
    print(f"  Starts in 3...", end="", flush=True)
    for i in range(2, 0, -1):
        time.sleep(1)
        print(f" {i}...", end="", flush=True)
    time.sleep(1)
    print(" GO.")

    frames: list[FocusFrame] = []
    pipeline.subscribe(frames.append)
    try:
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            time.sleep(0.25)
    finally:
        pipeline.unsubscribe(frames.append)
    print(f"  Captured {len(frames)} frames.")
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["muse", "synthetic"], default="muse")
    parser.add_argument(
        "--address",
        default=os.environ.get("NAO_MUSE_ADDRESS"),
        help="BLE address/UUID (or set NAO_MUSE_ADDRESS env var).",
    )
    parser.add_argument("--seconds-per-phase", type=float, default=60.0)
    args = parser.parse_args()

    src = (
        MuseStream(address=args.address)
        if args.source == "muse"
        else SyntheticStream(inject_hz=10.0, realtime=True)
    )
    pipeline = Pipeline(source=src)
    pipeline.start()
    try:
        eyes_open = _collect(pipeline, args.seconds_per_phase, "Eyes-open neutral")
        eyes_closed = _collect(pipeline, args.seconds_per_phase, "Eyes-closed relaxed")
    finally:
        pipeline.stop()

    pool = [
        f.focus for f in (eyes_open + eyes_closed)
        if f.artifact_clean and np.isfinite(f.focus) and f.focus < 1e4
    ]
    if len(pool) < 10:
        raise SystemExit(
            f"Only {len(pool)} clean frames after artifact filter — calibration unreliable. "
            "Reseat headband (good frontal + temporal contact) and retry."
        )

    cal = Calibration(
        mean_f=float(np.mean(pool)),
        std_f=float(np.std(pool)),
        n_samples=len(pool),
    )
    cal.save()

    open_means = [f.focus for f in eyes_open if f.artifact_clean]
    closed_means = [f.focus for f in eyes_closed if f.artifact_clean]
    print()
    print(f"Eyes-open  F mean: {np.mean(open_means):.3f}  (n={len(open_means)})")
    print(f"Eyes-closed F mean: {np.mean(closed_means):.3f}  (n={len(closed_means)})")
    if np.mean(closed_means) >= np.mean(open_means):
        print("⚠  Eyes-closed F is not lower than eyes-open. Expected α to rise (F to drop) when eyes close.")
        print("   Check sensor contact, especially temporal (TP9/TP10) channels.")
    else:
        print("✓ Eyes-closed lower than eyes-open — α rose, signal looks neurally meaningful.")
    print(f"\nSaved baseline to ~/.nao/baseline.json:\n{cal.to_json()}")


if __name__ == "__main__":
    main()
