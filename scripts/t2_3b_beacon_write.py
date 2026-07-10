#!/usr/bin/env python3
"""Tier 2.3b — beacon-settings write round-trip.

Safest possible write test: toggle `should_share_location` between
False and True. No transmission is involved — this bool only controls
whether the radio *includes* position in future beacon packets. The
radio is not commanded to send anything.

Also verifies that all other beacon fields are preserved across each
targeted write (no adjacent-bit damage).
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"

# Fields to snapshot for diff purposes. We expect only the target
# field to change on each write.
SNAPSHOT_FIELDS = [
    "packet_format",
    "aprs_callsign",
    "aprs_ssid",
    "aprs_symbol",
    "beacon_message",
    "ptt_release_id_info",
    "bss_user_id",
    "location_share_interval",
    "should_share_location",
    "send_pwr_voltage",
    "allow_position_check",
    "ptt_release_send_location",
    "ptt_release_send_id_info",
    "ptt_release_send_bss_user_id",
    "max_fwd_times",
    "time_to_live",
    "smart_beacon_en",
    "smart_beacon_min_interval",
    "smart_beacon_max_interval",
    "mic_e_en",
    "send_id_by_aprs",
]


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


def snapshot(bs):
    return {f: getattr(bs, f) for f in SNAPSHOT_FIELDS}


def diff(before, after):
    return {k: (before[k], after[k]) for k in before if before[k] != after[k]}


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: vendor_id={di.vendor_id} product_id={di.product_id} hw={di.hardware_version} fw={di.firmware_version}")

        orig_bs = radio.beacon_settings
        orig = snapshot(orig_bs)
        orig_val = orig_bs.should_share_location
        target_val = not orig_val

        print(f"\n[baseline] should_share_location = {orig_val}")
        print(f"  full snapshot: {orig}")

        # --- write 1: flip to the opposite value ---
        print(f"\n[write 1] set should_share_location = {target_val}")
        await radio.set_beacon_settings(should_share_location=target_val)
        # Small settle time; the radio may echo a BSS_SETTINGS_CHANGED
        # event we don't wait on explicitly.
        await asyncio.sleep(0.5)

        after1 = snapshot(radio.beacon_settings)
        d1 = diff(orig, after1)
        print(f"  fields changed: {d1}")
        if list(d1.keys()) == ["should_share_location"] and after1["should_share_location"] == target_val:
            print("  \u2705 write 1: only target field changed, value took")
        else:
            print("  \u274c write 1: unexpected diff or wrong final value")

        # --- write 2: restore ---
        print(f"\n[write 2] restore should_share_location = {orig_val}")
        await radio.set_beacon_settings(should_share_location=orig_val)
        await asyncio.sleep(0.5)

        after2 = snapshot(radio.beacon_settings)
        d2 = diff(orig, after2)
        print(f"  fields diff vs original baseline: {d2}")
        if not d2:
            print("  \u2705 write 2: back to baseline exactly")
        else:
            print("  \u274c write 2: baseline not restored cleanly")

        print("\ndone.")


if __name__ == "__main__":
    asyncio.run(main())
