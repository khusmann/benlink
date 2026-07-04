"""
Write a channel plan to a Benshi-family radio (Vero VR-N76, BTech UV-Pro,
RadioOddity GA-5WB, etc.) from a simple CSV.

Usage:
    python write_channels_csv.py <csv-file>          # dry-run (no writes)
    python write_channels_csv.py <csv-file> --go     # actually write

CSV columns (see hull_ma_channels.csv for a full example):
    slot,name,rx_freq,tx_freq,tone_out,tone_in,mode,bandwidth,tx_disable,notes

- slot: 0-based channel index (0 .. channel_count-1 as reported by device_info)
- name: up to 10 characters (radio limit)
- rx_freq / tx_freq: MHz as float (e.g. 146.520)
- tone_out / tone_in: CTCSS tone (Hz) or blank for none
- mode: FM (only tested option here)
- bandwidth: WIDE or NARROW
- tx_disable: True/False — set True for RX-only channels (NOAA, AIS, marine
  when you don't hold the license, etc.)

Writes go to the CURRENT region on the radio. If you want to program a
different bank/region, switch regions on the radio itself first
(benlink cannot switch regions yet — see docs/testing/N76.md).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from benlink.controller import RadioController


def parse_tone(s: str) -> float | None:
    s = (s or "").strip()
    return None if s == "" else float(s)


def parse_bool(s: str) -> bool:
    return (s or "").strip().lower() in ("true", "1", "yes", "y")


def parse_plan(path: Path):
    plan = []
    with path.open() as f:
        for row in csv.DictReader(f):
            plan.append({
                "slot": int(row["slot"]),
                "name": row["name"].strip()[:10],
                "rx_freq": float(row["rx_freq"]),
                "tx_freq": float(row["tx_freq"]),
                "tx_sub_audio": parse_tone(row["tone_out"]),
                "rx_sub_audio": parse_tone(row["tone_in"]),
                "bandwidth": (row["bandwidth"].strip().upper() or "WIDE"),
                "tx_disable": parse_bool(row.get("tx_disable", "")),
                "notes": row.get("notes", "").strip(),
            })
    return plan


async def run(csv_path: Path, uuid: str, go: bool) -> None:
    plan = parse_plan(csv_path)
    print(f"Channel plan: {csv_path.name}  ({len(plan)} entries)")
    print(f"Mode: {'WRITE' if go else 'DRY-RUN (add --go to write)'}")
    print(f"Target: CURRENT REGION on radio "
          f"-- switch regions on the radio first if needed")
    print("-" * 100)

    async with RadioController.new_ble(uuid) as radio:
        for entry in plan:
            slot = entry["slot"]
            current = radio.channels[slot]
            txd = "RX-only" if entry["tx_disable"] else "TX+RX"
            print(
                f"[{slot:2d}] {entry['name']:<12} "
                f"RX={entry['rx_freq']:>8.4f}  TX={entry['tx_freq']:>8.4f}  "
                f"Tout={entry['tx_sub_audio']!s:<6} "
                f"Tin={entry['rx_sub_audio']!s:<6} "
                f"BW={entry['bandwidth']:<6} {txd:<8}"
            )
            print(f"     was: name={current.name!r} "
                  f"rx={current.rx_freq} tx={current.tx_freq}")
            print(f"     -->  {entry['notes']}")

            if go:
                await radio.set_channel(
                    slot,
                    name=entry["name"],
                    rx_freq=entry["rx_freq"],
                    tx_freq=entry["tx_freq"],
                    rx_mod="FM",
                    tx_mod="FM",
                    tx_sub_audio=entry["tx_sub_audio"],
                    rx_sub_audio=entry["rx_sub_audio"],
                    bandwidth=entry["bandwidth"],
                    scan=True,
                    tx_at_max_power=True,
                    tx_at_med_power=False,
                    tx_disable=entry["tx_disable"],
                    talk_around=False,
                    pre_de_emph_bypass=False,
                    sign=True,
                    fixed_freq=False,
                    fixed_bandwidth=False,
                    fixed_tx_power=False,
                    mute=False,
                )
                print("     wrote OK")

    print("-" * 100)
    print("done." if go else "dry-run only. Re-run with --go to write.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Bulk-program channels from CSV")
    ap.add_argument("csv", type=Path, help="CSV plan to load")
    ap.add_argument("--uuid", required=True,
                    help="BLE peripheral UUID of the radio "
                         "(from BleakScanner.discover())")
    ap.add_argument("--go", action="store_true",
                    help="Actually write to the radio "
                         "(default is dry-run only)")
    args = ap.parse_args()
    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")
    asyncio.run(run(args.csv, args.uuid, args.go))


if __name__ == "__main__":
    main()
