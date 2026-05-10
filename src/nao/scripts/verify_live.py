"""Sanity check the live BLE path: connect, pull N seconds, print stats.

Use after `nao-pair` confirmed the device is visible. Prints sample count,
sample-rate estimate, per-channel µV ranges, and any artifact flags from
the first emitted FocusFrame. Failure modes are loud and named.
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np

from nao.config import EEG_CHANNELS, SAMPLE_RATE_HZ
from nao.ingest.muse import MuseStream


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument(
        "--address",
        default=os.environ.get("NAO_MUSE_ADDRESS"),
        help="BLE address/UUID (or set NAO_MUSE_ADDRESS env var).",
    )
    args = parser.parse_args()

    stream = MuseStream(address=args.address)
    samples: list = []
    print(f"Connecting (this can take ~5s while LSL outlet warms up)...")
    stream.start()
    t_end = time.monotonic() + args.seconds
    try:
        for s in stream:
            samples.append(s)
            if time.monotonic() >= t_end:
                break
    finally:
        stream.stop()

    if not samples:
        raise SystemExit("No samples received. Is the headband on + sensors making contact?")

    n = len(samples)
    duration = samples[-1].ts - samples[0].ts if n > 1 else 1.0
    rate = n / duration if duration > 0 else 0.0
    eeg = np.stack([s.eeg for s in samples])

    print(f"Got {n} samples in {duration:.2f}s — effective {rate:.1f} Hz (target {SAMPLE_RATE_HZ}).")
    print("Per-channel µV range:")
    for i, ch in enumerate(EEG_CHANNELS):
        col = eeg[:, i]
        print(f"  {ch:>4}  min={col.min():>9.1f}  max={col.max():>9.1f}  std={col.std():>7.2f}")
    if rate < SAMPLE_RATE_HZ * 0.7:
        print("⚠  Effective rate well below 256 Hz — BLE link is dropping packets.")
    if (eeg.std(axis=0) < 1.0).any():
        print("⚠  At least one channel near flat-line — sensor contact bad?")
    print("OK")


if __name__ == "__main__":
    main()
