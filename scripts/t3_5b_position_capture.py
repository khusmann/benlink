#!/usr/bin/env python3
"""Tier 3 — POSITION_CHANGE raw body capture.

Records every POSITION_CHANGED event (parsed + raw body hex) for a fixed
window so we can byte-diff runs from the same spot vs. different spots
to reverse the 18-byte body encoding.
"""
import asyncio
import sys
import time
from pathlib import Path
from bleak import BleakScanner
import benlink.controller as bc

# tee stdout to logs/
sys.path.insert(0, str(Path(__file__).parent))
from _teelog import setup_teelog
setup_teelog(__file__)

WATCH_SECONDS = 300  # 5 minutes


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s for VR-N76...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.name and "VR-N76" in d.name.upper():
            print(f"  found {d.name!r} @ {d.address}")
            return d.address
    raise RuntimeError("N76 not found")


async def main() -> None:
    address = await find_radio()
    async with bc.RadioController.new_ble(address) as radio:
        print(f"connected fw={radio.device_info.firmware_version}")
        wall = time.strftime("%Y-%m-%d %H:%M:%S %z")
        print(f"start_wall={wall}")

        t0 = time.monotonic()
        positions = []

        def handler(evt):
            name = type(evt).__name__
            if "Position" not in name:
                return
            t = time.monotonic() - t0
            # Try to get raw body from the underlying message
            raw_hex = None
            body = getattr(evt, "body", None)
            if isinstance(body, (bytes, bytearray)):
                raw_hex = body.hex()
            # Also dump every attr for later diffing
            attrs = {k: v for k, v in vars(evt).items() if not k.startswith("_")}
            positions.append((t, attrs, raw_hex))
            print(f"[{t:7.2f}s] {name}")
            for k, v in attrs.items():
                print(f"    {k}: {v!r}")
            if raw_hex:
                print(f"    body_hex: {raw_hex}")

        radio.add_event_handler(handler)

        try:
            await radio.enable_event("POSITION_CHANGED")
            print("POSITION_CHANGED enabled")
        except Exception as e:
            print(f"enable POSITION_CHANGED FAILED: {e!r}")
            return

        # Also grab raw unknowns in case parsing loses info
        from benlink.command import UnknownProtocolMessage
        def raw_handler(evt):
            if isinstance(evt, UnknownProtocolMessage):
                m = evt.message
                cmd = getattr(m, "command", None)
                body = getattr(m, "body", None)
                if cmd is None:
                    return
                if isinstance(body, (bytes, bytearray)):
                    t = time.monotonic() - t0
                    print(f"[{t:7.2f}s] UNKNOWN cmd={cmd!r} body({len(body)}): {body.hex()}")
        radio.add_event_handler(raw_handler)

        print(f"\n=== capturing {WATCH_SECONDS}s — RADIO STAYS PUT ===\n")
        await asyncio.sleep(WATCH_SECONDS)

        print(f"\n=== {len(positions)} position events captured ===")


if __name__ == "__main__":
    asyncio.run(main())
