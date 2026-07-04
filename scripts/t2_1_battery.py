#!/usr/bin/env python3
"""Tier 2.1 — battery read, cache-safe. Matches by name OR known UUID."""
import asyncio
import sys
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
NAME_HINTS = ("VR-N76", "N76", "VERO", "BENSHI")


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    named = []
    uuid_hit = None
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            uuid_hit = d
        if d.name and any(h in d.name.upper() for h in NAME_HINTS):
            named.append(d)
    if named:
        d = named[0]
        print(f"  matched by name: {d.name!r} @ {d.address}")
        return d.address
    if uuid_hit:
        print(f"  matched by known UUID (no name in this ad): {uuid_hit.address}")
        return uuid_hit.address
    print("  --- all devices seen ---")
    for d in devices:
        print(f"    {d.address}  {d.name!r}")
    raise RuntimeError("N76 not found this scan")


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")
    async with bc.RadioController.new_ble(address) as radio:
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


if __name__ == "__main__":
    asyncio.run(main())
