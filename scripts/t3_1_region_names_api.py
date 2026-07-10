#!/usr/bin/env python3
"""Tier 3.1 verify — use the freshly-wired radio.get_region_names() API.

Exercises the friendly API. Should return exactly the names the raw
probe found earlier, without any manual byte-hacking.
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")
        print(f"current region = {radio.status.curr_region}\n")

        names = await radio.get_region_names()
        print(f"discovered {len(names)} regions:")
        for i, name in enumerate(names):
            marker = " <-- current" if i == radio.status.curr_region else ""
            display = repr(name) if name else "(unnamed)"
            print(f"  region {i} (UI: Group {i+1}): {display}{marker}")

        # Confirm we get None for a definitely-out-of-range id.
        beyond = await radio.get_region_name(len(names))
        print(f"\nout-of-range check: get_region_name({len(names)}) = {beyond!r} (expected None)")


if __name__ == "__main__":
    asyncio.run(main())
