#!/usr/bin/env python3
"""Tier 4 — Linux RFCOMM smoke test. Uses paired VR-N76 over BR/EDR SPP."""
import asyncio, sys
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

ADDR = "38:D2:00:01:74:D9"

async def main() -> None:
    print(f"[t4] rfcomm connect {ADDR} (auto channel)...")
    async with bc.RadioController.new_rfcomm(ADDR) as radio:
        di = radio.device_info
        print(f"connected: vendor_id={di.vendor_id} product_id={di.product_id} hw={di.hardware_version} fw={di.firmware_version}")
        for label, coro in [
            ("battery_voltage()", radio.battery_voltage()),
            ("battery_level_as_percentage()", radio.battery_level_as_percentage()),
            ("battery_level()", radio.battery_level()),
        ]:
            try:
                val = await coro
                print(f"{label}: {val}")
            except Exception as e:
                print(f"{label} error: {e!r}")

asyncio.run(main())
