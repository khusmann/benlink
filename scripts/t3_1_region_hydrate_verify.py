#!/usr/bin/env python3
"""Tier 3 — verify region_names auto-hydrates on connect.

- Connects to the N76.
- Immediately reads `radio.region_names` (should be populated by _hydrate).
- Compares against a fresh `await radio.get_region_names()` probe.
- Verifies they match.
"""
import asyncio
import sys
from pathlib import Path
from bleak import BleakScanner
import benlink.controller as bc

sys.path.insert(0, str(Path(__file__).parent))
from _teelog import setup_teelog
setup_teelog(__file__)


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

        # 1. Cached names (populated by _hydrate())
        cached = radio.region_names
        print(f"\ncached radio.region_names ({len(cached)} entries):")
        for i, n in enumerate(cached):
            print(f"  region {i}: {n!r}")

        # 2. Fresh probe (should match)
        fresh = await radio.get_region_names()
        print(f"\nfresh get_region_names() ({len(fresh)} entries):")
        for i, n in enumerate(fresh):
            print(f"  region {i}: {n!r}")

        # 3. Compare
        if cached == fresh:
            print("\n✅ cached == fresh — hydrate works")
        else:
            print("\n❌ cached != fresh")
            print(f"   cached: {cached!r}")
            print(f"   fresh:  {fresh!r}")

        # 4. Rename test — bump region 5 to '__test__' then restore
        if len(cached) >= 6:
            original = cached[5]
            print(f"\nrename test: region 5 currently {original!r}")
            await radio.set_region_name(5, "__test__")
            print(f"  after set_region_name: cached[5]={radio.region_names[5]!r}")
            assert radio.region_names[5] == "__test__", "cache not updated after rename"
            await radio.set_region_name(5, original)
            print(f"  restored: cached[5]={radio.region_names[5]!r}")
            assert radio.region_names[5] == original, "cache not restored"
            print("✅ rename cache-sync works")

        print("\nDONE")


if __name__ == "__main__":
    asyncio.run(main())
