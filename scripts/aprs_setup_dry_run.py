#!/usr/bin/env python3
"""APRS setup — dry run.

Read-only inspection of what we're about to touch before writing:
1. What is currently in channel slot 32 (channels[31])?
2. What is the current `settings.auto_share_loc_ch` set to?
3. What is `radio.beacon_settings.should_share_location` (must stay False for a safe dry run)?

Prints everything so we can decide whether it's safe to write.
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
        print(f"connected: vendor_id={di.vendor_id} product_id={di.product_id} hw={di.hardware_version} fw={di.firmware_version}")

        # channel 32 = index 31
        ch32 = radio.channels[31]
        print("\n--- current channel 32 (channels[31]) ---")
        for field in (
            "channel_id", "name", "rx_freq", "tx_freq",
            "rx_mod", "tx_mod", "bandwidth",
            "rx_sub_audio", "tx_sub_audio",
            "scan", "tx_disable", "tx_at_max_power", "tx_at_med_power",
            "talk_around", "mute",
        ):
            print(f"  {field:20s} = {getattr(ch32, field)!r}")

        s = radio.settings
        print("\n--- relevant settings ---")
        print(f"  auto_share_loc_ch    = {s.auto_share_loc_ch!r}")
        print(f"  positioning_system   = {s.positioning_system!r}")
        print(f"  gpwpl_upload_en      = {s.gpwpl_upload_en!r}")
        print(f"  channel_a            = {s.channel_a!r}  (currently-tuned VFO A)")
        print(f"  channel_b            = {s.channel_b!r}  (currently-tuned VFO B)")

        bs = radio.beacon_settings
        print("\n--- relevant beacon safety ---")
        print(f"  packet_format             = {bs.packet_format!r}")
        print(f"  should_share_location     = {bs.should_share_location!r}  (must be False for dry run)")
        print(f"  smart_beacon_en           = {bs.smart_beacon_en!r}   (auto-beacon on if True)")
        print(f"  aprs_callsign             = {bs.aprs_callsign!r}")
        print(f"  aprs_ssid                 = {bs.aprs_ssid!r}")
        print(f"  aprs_symbol               = {bs.aprs_symbol!r}")
        print(f"  beacon_message            = {bs.beacon_message!r}")

        print("\n--- planned writes (NOT executed by this script) ---")
        print("  1) channels[31] -> name='APRS', rx_freq=144.390, tx_freq=144.390,")
        print("       rx_mod='FM', tx_mod='FM', bandwidth='WIDE',")
        print("       sub_audio=None (no tone), scan=False, tx_disable=False")
        print("  2) settings.auto_share_loc_ch = 31  (radio slot 32, 0-based via API)")
        print("     (should_share_location remains False so nothing actually beacons)")


if __name__ == "__main__":
    asyncio.run(main())
