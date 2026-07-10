#!/usr/bin/env python3
"""Tier 2.4c — verify BSS_SETTINGS_CHANGED now surfaces as BeaconSettingsChangedEvent.

Subscribe to BSS_SETTINGS_CHANGED only. Trigger the event by toggling
a benign beacon setting via the HT (e.g. flip should_share_location
briefly in the radio's menu) or by calling radio.set_beacon_settings()
from another script.

Prints the parsed BeaconSettings on each event. Also flags any
UnknownProtocolMessage that slips through (would indicate a size
mismatch we haven't handled).
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from benlink.command import (
    BeaconSettingsChangedEvent,
    UnknownProtocolMessage,
)
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
WATCH_SECONDS = 90


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

        counts = {"beacon": 0, "unknown": 0, "other": 0}

        def on_event(evt) -> None:
            if isinstance(evt, BeaconSettingsChangedEvent):
                counts["beacon"] += 1
                bs = evt.beacon_settings
                print(f"[{counts['beacon']:03d}] BeaconSettingsChangedEvent")
                print(f"       packet_format={bs.packet_format} aprs_callsign={bs.aprs_callsign!r} ssid={bs.aprs_ssid}")
                print(f"       aprs_symbol={bs.aprs_symbol!r} beacon_message={bs.beacon_message!r}")
                print(f"       share_interval={bs.location_share_interval} should_share={bs.should_share_location}")
            elif isinstance(evt, UnknownProtocolMessage):
                counts["unknown"] += 1
                m = evt.message
                print(f"[???] UnknownProtocolMessage cmd_group={getattr(m,'command_group',None)!r} cmd={getattr(m,'command',None)!r} is_reply={getattr(m,'is_reply',None)!r}")
            else:
                counts["other"] += 1
                print(f"[   ] other: {type(evt).__name__}")

        unsub = radio.add_event_handler(on_event)

        # Enable both BSS_SETTINGS_CHANGED and HT_SETTINGS_CHANGED so any
        # settings-menu poke will register on the wire too.
        try:
            await radio.enable_event("BSS_SETTINGS_CHANGED")
            print("enabled BSS_SETTINGS_CHANGED")
        except Exception as e:
            print(f"enable BSS_SETTINGS_CHANGED failed: {e!r}")

        print(f"\nwatching for {WATCH_SECONDS}s — trigger by toggling a beacon setting on the radio")
        print("(Menu -> APRS/BSS Settings -> flip something benign like Share Location, then flip back)\n")

        try:
            await asyncio.sleep(WATCH_SECONDS)
        finally:
            try:
                unsub()
            except Exception:
                pass

        print(f"\nsummary: beacon={counts['beacon']} unknown={counts['unknown']} other={counts['other']}")


if __name__ == "__main__":
    asyncio.run(main())
