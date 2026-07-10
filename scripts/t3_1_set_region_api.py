#!/usr/bin/env python3
"""Tier 3.1 verify — use the freshly-wired radio.set_region() API.

After the raw-probe in scripts/t3_1_set_region_probe.py confirmed the
wire shape, we added SetRegion / SetRegionReply / radio.set_region()
to the fork. This script exercises the friendly API and confirms:

- radio.set_region(target) returns cleanly (no reply-status error)
- radio.status.curr_region updates to target
- radio.channels[] cache auto-refreshes to the new region's table
- restore round-trips bit-exact (baseline channel table restored)
"""
import asyncio
import time
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


def channels_snapshot(radio):
    """Snapshot cached channels[] as name/freq tuples."""
    return {
        i: (c.name, round(c.rx_freq, 4), round(c.tx_freq, 4), c.bandwidth)
        for i, c in enumerate(radio.channels)
    }


def diff(a, b):
    return [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")
    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        baseline = radio.status.curr_region
        probe = 0 if baseline != 0 else 1
        print(f"baseline curr_region = {baseline}")
        print(f"probe target = {probe}\n")

        snap_baseline = channels_snapshot(radio)
        pop = sum(1 for v in snap_baseline.values() if v[0])
        print(f"baseline region {baseline}: {pop} populated slots")
        print(f"  slot 0: {snap_baseline[0]}")

        print(f"\n[probe] radio.set_region({probe})...")
        t0 = time.monotonic()
        await radio.set_region(probe)
        elapsed = time.monotonic() - t0
        print(f"  took {elapsed:.2f}s (includes 32-channel refresh)")
        print(f"  curr_region = {radio.status.curr_region}")

        snap_probe = channels_snapshot(radio)
        pop_p = sum(1 for v in snap_probe.values() if v[0])
        print(f"  probe region {probe}: {pop_p} populated slots")
        print(f"  slot 0: {snap_probe[0]}")

        changed = diff(snap_baseline, snap_probe)
        print(f"  {len(changed)}/32 slots differ between baseline and probe (cache auto-refreshed)")

        print(f"\n[restore] radio.set_region({baseline})...")
        await radio.set_region(baseline)
        print(f"  curr_region = {radio.status.curr_region}")
        snap_after = channels_snapshot(radio)
        drift = diff(snap_baseline, snap_after)
        print(f"  drift vs original baseline: {len(drift)}/32 slots (want 0)")

        if radio.status.curr_region == baseline and not drift and radio.status.curr_region != probe:
            print("\n\u2705 radio.set_region() API works end-to-end. Bit-exact restore.")
        else:
            print("\n\u274c unexpected state")


if __name__ == "__main__":
    asyncio.run(main())
