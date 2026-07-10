#!/usr/bin/env python3
"""APRS setup — apply writes.

Sets channel 32 to APRS 2m simplex (144.390 MHz, FM, WIDE, no tone) and
points settings.auto_share_loc_ch at that channel.

Pre-conditions checked at runtime (aborts if any fail):
- radio.beacon_settings.should_share_location is False
- radio.beacon_settings.smart_beacon_en is False
- radio.settings.channel_a != 31 and channel_b != 31 (not currently tuned to slot 32)

Post-conditions verified by re-read:
- channels[31].name == "APRS"
- channels[31].rx_freq == channels[31].tx_freq == 144.390
- channels[31].bandwidth == "WIDE"
- channels[31].rx_sub_audio is None and tx_sub_audio is None
- settings.auto_share_loc_ch == 31
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


def dump_channel(ch, label):
    print(f"--- {label} ---")
    for field in (
        "channel_id", "name", "rx_freq", "tx_freq",
        "rx_mod", "tx_mod", "bandwidth",
        "rx_sub_audio", "tx_sub_audio",
        "scan", "tx_disable", "tx_at_max_power", "tx_at_med_power",
        "talk_around", "mute",
    ):
        print(f"  {field:20s} = {getattr(ch, field)!r}")


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}\n")

        # --- pre-flight safety checks ---
        bs = radio.beacon_settings
        s = radio.settings
        problems = []
        if bs.should_share_location:
            problems.append("should_share_location is True -- refusing to touch beacon channel")
        if bs.smart_beacon_en:
            problems.append("smart_beacon_en is True -- refusing to touch beacon channel")
        if s.channel_a == 31 or s.channel_b == 31:
            problems.append(f"VFO A/B currently tuned to slot 32 (a={s.channel_a}, b={s.channel_b})")
        if problems:
            print("PRE-FLIGHT FAILED:")
            for p in problems:
                print(f"  - {p}")
            return
        print("pre-flight OK: beacon TX disabled, no VFO on slot 32\n")

        dump_channel(radio.channels[31], "before: channels[31]")
        print(f"  settings.auto_share_loc_ch = {s.auto_share_loc_ch!r}\n")

        # --- write 1: channel 32 -> APRS 144.390 ---
        print("[write 1] channels[31] -> APRS 144.390 FM WIDE no-tone")
        await radio.set_channel(
            31,
            name="APRS",
            rx_freq=144.390,
            tx_freq=144.390,
            rx_mod="FM",
            tx_mod="FM",
            bandwidth="WIDE",
            rx_sub_audio=None,
            tx_sub_audio=None,
            scan=False,
            tx_disable=False,
            tx_at_max_power=True,
            tx_at_med_power=False,
            talk_around=False,
            mute=False,
        )
        await asyncio.sleep(0.4)

        # --- write 2: settings.auto_share_loc_ch = 31 (0-based -> slot 32) ---
        # Already 31 in the dry run, but we set it explicitly to be sure.
        print("[write 2] settings.auto_share_loc_ch = 31 (visual slot 32)")
        await radio.set_settings(auto_share_loc_ch=31)
        await asyncio.sleep(0.4)

        # --- verify ---
        print("\n--- verify ---")
        ch32 = radio.channels[31]
        dump_channel(ch32, "after: channels[31]")
        s2 = radio.settings
        print(f"  settings.auto_share_loc_ch = {s2.auto_share_loc_ch!r}")

        ok = (
            ch32.name == "APRS"
            and abs(ch32.rx_freq - 144.390) < 1e-6
            and abs(ch32.tx_freq - 144.390) < 1e-6
            and ch32.bandwidth == "WIDE"
            and ch32.rx_mod == "FM"
            and ch32.tx_mod == "FM"
            and ch32.rx_sub_audio is None
            and ch32.tx_sub_audio is None
            and ch32.scan is False
            and ch32.tx_disable is False
            and s2.auto_share_loc_ch == 31
        )
        # sanity check beacon safety unchanged
        bs2 = radio.beacon_settings
        safety_ok = (bs2.should_share_location is False and bs2.smart_beacon_en is False)

        print()
        if ok and safety_ok:
            print("APRS setup complete. Radio will use slot 32 (144.390 MHz FM WIDE)")
            print("when beacon is enabled. Auto-beacon remains off; keying up beacon")
            print("still requires flipping should_share_location or pressing PTT-with-beacon.")
        else:
            print("VERIFY FAILED")
            print(f"  channel ok: {ok}")
            print(f"  safety ok:  {safety_ok}")


if __name__ == "__main__":
    asyncio.run(main())
