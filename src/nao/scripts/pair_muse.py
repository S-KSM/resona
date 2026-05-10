"""Scan for Muse devices over BLE and print MAC addresses.

Hardware-side step: hold the Muse power button ~6s until lights cascade,
then run this. Does NOT pair via the OS; OpenMuse/muselsl handle the
"speaking-terms" connection directly later.
"""
from __future__ import annotations

import argparse
import asyncio

from bleak import BleakScanner


async def _scan(timeout: float, name_prefix: str) -> list[tuple[str, str]]:
    print(f"Scanning {timeout}s for BLE devices matching '{name_prefix}*'...")
    devices = await BleakScanner.discover(timeout=timeout)
    matches = [
        (d.address, d.name or "")
        for d in devices
        if d.name and d.name.startswith(name_prefix)
    ]
    return matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--prefix", default="Muse")
    args = parser.parse_args()

    matches = asyncio.run(_scan(args.timeout, args.prefix))
    if not matches:
        print(
            "No Muse devices found.\n"
            "  - Is the headband in pairing mode? Hold power 6s until lights cascade.\n"
            "  - Bluetooth on?\n"
            "  - On macOS, Terminal/your IDE may need Bluetooth permission "
            "(System Settings → Privacy & Security → Bluetooth)."
        )
        raise SystemExit(1)

    print("Found:")
    for addr, name in matches:
        print(f"  {name}  {addr}")
    print("\nPass an address (or just the name) to MuseStream(address=...).")


if __name__ == "__main__":
    main()
