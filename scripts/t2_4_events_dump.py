#!/usr/bin/env python3
"""Tier 2.4b — event handler with raw dump of UnknownProtocolMessage.

Same as t2_4_events.py but every UnknownProtocolMessage prints:
  - command_group
  - command
  - is_reply
  - body (repr + hex if bytes)
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
from benlink.command import UnknownProtocolMessage

ALL_EVENTS = [
    "HT_STATUS_CHANGED",
    "DATA_RXD",
    "NEW_INQUIRY_DATA",
    "RESTORE_FACTORY_SETTINGS",
    "HT_CH_CHANGED",
    "HT_SETTINGS_CHANGED",
    "RINGING_STOPPED",
    "RADIO_STATUS_CHANGED",
    "USER_ACTION",
    "SYSTEM_EVENT",
    "BSS_SETTINGS_CHANGED",
    "DATA_TXD",
    "POSITION_CHANGED",
]

WATCH_SECONDS = 60


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s for VR-N76...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.name and "VR-N76" in d.name.upper():
            print(f"  found {d.name!r} @ {d.address}")
            return d.address
    raise RuntimeError("N76 not found — put it in pair mode or wake the screen")


def dump_unknown(evt: UnknownProtocolMessage) -> None:
    m = evt.message
    print("  UnknownProtocolMessage:")
    for attr in ("command_group", "command", "is_reply", "message_id"):
        if hasattr(m, attr):
            print(f"    {attr}: {getattr(m, attr)!r}")
    body = getattr(m, "body", None)
    if isinstance(body, (bytes, bytearray)):
        print(f"    body (bytes, {len(body)}): {body.hex()}")
    else:
        print(f"    body: {body!r}")


async def main() -> None:
    address = await find_radio()
    async with bc.RadioController.new_ble(address) as radio:
        print(f"connected fw={radio.device_info.firmware_version}")

        seen: list = []
        unknowns: list = []
        t0 = time.monotonic()

        def handler(evt):
            t = time.monotonic() - t0
            seen.append(evt)
            if isinstance(evt, UnknownProtocolMessage):
                unknowns.append(evt)
                print(f"[{t:6.2f}s] UNKNOWN:")
                dump_unknown(evt)
            else:
                print(f"[{t:6.2f}s] {type(evt).__name__}")

        radio.add_event_handler(handler)

        for et in ALL_EVENTS:
            try:
                await radio.enable_event(et)
            except Exception as e:
                print(f"  enable {et} FAILED: {e!r}")

        print(f"\n=== watching {WATCH_SECONDS}s — wiggle the radio ===\n")
        await asyncio.sleep(WATCH_SECONDS)

        print(f"\n=== {len(seen)} events, {len(unknowns)} unknowns ===")
        counts: dict = {}
        for e in seen:
            counts[type(e).__name__] = counts.get(type(e).__name__, 0) + 1
        for k, v in sorted(counts.items()):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
