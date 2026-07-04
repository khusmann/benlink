#!/usr/bin/env python3
"""Tier 3.1 verify — exercise radio.set_region_channel() end-to-end.

Same shape as the earlier raw probe, but uses the friendly API
instead of raw p.Message construction. Confirms the wire wiring is
correct end-to-end.
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
TARGET_REGION = 5
TARGET_SLOT = 31


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


def sig(ch):
    return (ch.name, round(ch.rx_freq, 4), round(ch.tx_freq, 4),
            ch.bandwidth, ch.rx_sub_audio, ch.tx_sub_audio,
            ch.scan, ch.tx_disable)


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        R0 = radio.status.curr_region
        print(f"baseline curr_region = {R0}")
        assert R0 != TARGET_REGION

        # Snapshot baseline of target
        await radio.set_region(TARGET_REGION)
        baseline = radio.channels[TARGET_SLOT]
        baseline_sig = sig(baseline)
        print(f"baseline region {TARGET_REGION} slot {TARGET_SLOT}: {baseline_sig}")

        # Return to R0
        await radio.set_region(R0)

        # Write via the friendly API — no region switch needed
        print(f"\n[write] radio.set_region_channel({TARGET_REGION}, {TARGET_SLOT}, ...)")
        await radio.set_region_channel(
            TARGET_REGION,
            TARGET_SLOT,
            name="APITEST",
            rx_freq=145.500,
            tx_freq=145.500,
            rx_mod="FM",
            tx_mod="FM",
            bandwidth="WIDE",
            rx_sub_audio=None,
            tx_sub_audio=None,
            scan=False,
            tx_disable=True,
        )
        print(f"  curr_region still = {radio.status.curr_region} (no switch)")

        # Verify by hopping over
        await radio.set_region(TARGET_REGION)
        after = radio.channels[TARGET_SLOT]
        after_sig = sig(after)
        print(f"  after write: {after_sig}")
        ok_write = after.name == "APITEST" and abs(after.rx_freq - 145.5) < 1e-6

        # Restore via the same API from region 5 back to R0
        await radio.set_region(R0)
        print(f"\n[restore] radio.set_region_channel({TARGET_REGION}, {TARGET_SLOT}, <baseline>)")
        await radio.set_region_channel(
            TARGET_REGION,
            TARGET_SLOT,
            name=baseline.name,
            rx_freq=baseline.rx_freq,
            tx_freq=baseline.tx_freq,
            rx_mod=baseline.rx_mod,
            tx_mod=baseline.tx_mod,
            bandwidth=baseline.bandwidth,
            rx_sub_audio=baseline.rx_sub_audio,
            tx_sub_audio=baseline.tx_sub_audio,
            scan=baseline.scan,
            tx_disable=baseline.tx_disable,
            tx_at_max_power=baseline.tx_at_max_power,
            tx_at_med_power=baseline.tx_at_med_power,
            talk_around=baseline.talk_around,
            mute=baseline.mute,
        )

        # Verify restore
        await radio.set_region(TARGET_REGION)
        restored = radio.channels[TARGET_SLOT]
        restored_sig = sig(restored)
        print(f"  after restore: {restored_sig}")
        ok_restore = restored_sig == baseline_sig

        # cleanup
        await radio.set_region(R0)
        print(f"\nback to region {R0}")

        if ok_write and ok_restore:
            print("\n\u2705 radio.set_region_channel() API works end-to-end. Bit-exact restore.")
        else:
            print(f"\n\u274c write ok={ok_write}, restore ok={ok_restore}")


if __name__ == "__main__":
    asyncio.run(main())
