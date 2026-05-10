"""Custom Muse → LSL runner. Same as `muselsl stream` but also publishes a
Battery outlet so the UI can show headband charge level.

muselsl 2.3 only exposes EEG/PPG/ACC/GYRO outlets — its Muse class does
have a `callback_telemetry` (battery, fuel-gauge, ADC volts, temp) but
`stream.py` never wires it. This runner pulls in muselsl's Muse class
directly, mirrors the 4 standard outlets, and adds a 5th `Battery` outlet
fed by the telemetry callback.

Invoked as a subprocess by `MuseStream._stream_muselsl`. Exits when BLE
disconnects (matches muselsl's behavior — outer Python watchdog reconnects).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from functools import partial

from muselsl.constants import (  # type: ignore
    AUTO_DISCONNECT_DELAY,
    LSL_ACC_CHUNK,
    LSL_EEG_CHUNK,
    LSL_GYRO_CHUNK,
    LSL_PPG_CHUNK,
    MUSE_NB_ACC_CHANNELS,
    MUSE_NB_EEG_CHANNELS,
    MUSE_NB_GYRO_CHANNELS,
    MUSE_NB_PPG_CHANNELS,
    MUSE_SAMPLING_ACC_RATE,
    MUSE_SAMPLING_EEG_RATE,
    MUSE_SAMPLING_GYRO_RATE,
    MUSE_SAMPLING_PPG_RATE,
)
from muselsl.muse import Muse  # type: ignore
from pylsl import StreamInfo, StreamOutlet, local_clock  # type: ignore

log = logging.getLogger("nao.muse_runner")


def _push_chunk(data, timestamps, outlet):
    for i in range(data.shape[1]):
        outlet.push_sample(data[:, i], timestamps[i])


def _make_eeg_outlet(address: str) -> StreamOutlet:
    info = StreamInfo(
        "Muse", "EEG", MUSE_NB_EEG_CHANNELS, MUSE_SAMPLING_EEG_RATE,
        "float32", f"Muse{address}",
    )
    info.desc().append_child_value("manufacturer", "Muse")
    chs = info.desc().append_child("channels")
    for c in ("TP9", "AF7", "AF8", "TP10", "Right AUX"):
        chs.append_child("channel") \
            .append_child_value("label", c) \
            .append_child_value("unit", "microvolts") \
            .append_child_value("type", "EEG")
    return StreamOutlet(info, LSL_EEG_CHUNK)


def _make_aux_outlet(
    address: str, type_: str, channels: tuple[str, ...], n: int, rate: float,
    unit: str, chunk: int,
) -> StreamOutlet:
    info = StreamInfo("Muse", type_, n, rate, "float32", f"Muse{address}")
    info.desc().append_child_value("manufacturer", "Muse")
    chs = info.desc().append_child("channels")
    for c in channels:
        chs.append_child("channel") \
            .append_child_value("label", c) \
            .append_child_value("unit", unit) \
            .append_child_value("type", type_)
    return StreamOutlet(info, chunk)


def _make_battery_outlet(address: str) -> StreamOutlet:
    """4-channel telemetry: battery%, fuel_gauge, ADC voltage, temperature.

    Irregular sampling — Muse pushes telemetry every few seconds. Setting
    nominal_srate=0 marks it as irregular for downstream consumers.
    """
    info = StreamInfo(
        "Muse", "Battery", 4, 0.0, "float32", f"MuseBat{address}",
    )
    info.desc().append_child_value("manufacturer", "Muse")
    chs = info.desc().append_child("channels")
    for label, unit in (
        ("battery_pct", "percent"),
        ("fuel_gauge", "mAh"),
        ("adc_volt", "V"),
        ("temperature", "C"),
    ):
        chs.append_child("channel") \
            .append_child_value("label", label) \
            .append_child_value("unit", unit) \
            .append_child_value("type", "Battery")
    return StreamOutlet(info, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-a", "--address", required=False)
    parser.add_argument("-n", "--name", default=None)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--log", default="warning",
        choices=("debug", "info", "warning", "error", "critical"),
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    address = args.address
    if not address:
        from muselsl.stream import find_muse  # type: ignore
        found = find_muse(name=args.name)
        if not found:
            print("No Muse found.", file=sys.stderr)
            return 2
        address = found["address"]
        log.info("auto-discovered %s at %s", found["name"], address)

    eeg_outlet = _make_eeg_outlet(address)
    ppg_outlet = _make_aux_outlet(
        address, "PPG", ("PPG1", "PPG2", "PPG3"),
        MUSE_NB_PPG_CHANNELS, MUSE_SAMPLING_PPG_RATE, "mmHg", LSL_PPG_CHUNK,
    )
    acc_outlet = _make_aux_outlet(
        address, "ACC", ("X", "Y", "Z"),
        MUSE_NB_ACC_CHANNELS, MUSE_SAMPLING_ACC_RATE, "g", LSL_ACC_CHUNK,
    )
    gyro_outlet = _make_aux_outlet(
        address, "GYRO", ("X", "Y", "Z"),
        MUSE_NB_GYRO_CHANNELS, MUSE_SAMPLING_GYRO_RATE, "dps", LSL_GYRO_CHUNK,
    )
    bat_outlet = _make_battery_outlet(address)

    push_eeg = partial(_push_chunk, outlet=eeg_outlet)
    push_ppg = partial(_push_chunk, outlet=ppg_outlet)
    push_acc = partial(_push_chunk, outlet=acc_outlet)
    push_gyro = partial(_push_chunk, outlet=gyro_outlet)

    def push_telemetry(timestamp, battery, fuel_gauge, adc_volt, temp):
        bat_outlet.push_sample(
            [float(battery), float(fuel_gauge), float(adc_volt), float(temp)],
            float(timestamp),
        )

    muse = Muse(
        address=address,
        callback_eeg=push_eeg,
        callback_ppg=push_ppg,
        callback_acc=push_acc,
        callback_gyro=push_gyro,
        callback_telemetry=push_telemetry,
        backend="auto",
        name=args.name,
        time_func=time.time,
    )

    if not muse.connect(retries=args.retries):
        print(f"Failed to connect to {address}", file=sys.stderr)
        return 1
    print(f"Connected to {address}.", flush=True)

    muse.start()
    print("Streaming EEG PPG ACC GYRO Battery...", flush=True)

    try:
        while time.time() - muse.last_timestamp < AUTO_DISCONNECT_DELAY:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
    finally:
        try:
            muse.stop()
        finally:
            muse.disconnect()
    print("Disconnected.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
