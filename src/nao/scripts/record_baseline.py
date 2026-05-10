"""Record a baseline EEG segment to CSV.

Closes Phase 0 of the SPECS roadmap. Use this while doing a high-concentration
task to capture your personal "Focus Baseline" — later runs can z-score
against it.
"""
from __future__ import annotations

import argparse
import time

import pandas as pd

from nao.config import ACCEL_AXES, EEG_CHANNELS
from nao.ingest.muse import MuseStream
from nao.ingest.synthetic import SyntheticStream


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=60.0, help="seconds")
    parser.add_argument("--out", default="baseline.csv")
    parser.add_argument(
        "--source",
        choices=["muse", "synthetic"],
        default="muse",
        help="Use synthetic for dev / no-hardware testing.",
    )
    parser.add_argument("--address", default=None, help="BLE address or name")
    parser.add_argument("--inject-hz", type=float, default=None,
                        help="(synthetic only) inject sinusoid at this Hz")
    args = parser.parse_args()

    source = (
        MuseStream(address=args.address)
        if args.source == "muse"
        else SyntheticStream(inject_hz=args.inject_hz)
    )

    rows: list[dict[str, float]] = []
    t_end = time.monotonic() + args.duration
    print(f"Recording {args.duration}s from {args.source}...")
    source.start()
    try:
        for sample in source:
            row = {"ts": sample.ts}
            for ch, v in zip(EEG_CHANNELS, sample.eeg):
                row[ch] = float(v)
            for ax, v in zip(ACCEL_AXES, sample.accel):
                row[ax] = float(v)
            rows.append(row)
            if time.monotonic() >= t_end:
                break
    finally:
        source.stop()

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} samples to {args.out}")
    print(df.head())


if __name__ == "__main__":
    main()
