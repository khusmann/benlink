#!/usr/bin/env python3
"""Tier 2.3 — beacon (BSS/APRS) settings read. Read-only, no TX risk.

Dumps radio.beacon_settings. Cross-references with the 52-byte
BSS_SETTINGS_CHANGED payload we observed in 2.4b (likely contains
beacon_message + aprs_callsign).
"""
import asyncio
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


def dump_beacon(bs) -> None:
    fields = [
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
    ]
    print("--- beacon_settings ---")
    for f in fields:
        try:
            v = getattr(bs, f)
        except Exception as e:
            v = f"<err {e!r}>"
        # Pretty-print bytes-y strings
        if isinstance(v, str):
            v_repr = repr(v)
        else:
            v_repr = v
        print(f"  {f:32s} = {v_repr}")


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")
    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: vendor_id={di.vendor_id} product_id={di.product_id} hw={di.hardware_version} fw={di.firmware_version}")

        # radio.beacon_settings is populated during initial state sync
        bs = radio.beacon_settings
        dump_beacon(bs)

        # Round-trip check: also fetch fresh via the low-level conn to
        # confirm the cached copy matches what the radio reports now.
        try:
            # _conn.get_beacon_settings() already unwraps the reply and
            # returns a BeaconSettings directly (not GetBeaconSettingsReply).
            fresh_bs = await radio._conn.get_beacon_settings()
            print()
            print("--- fresh read via _conn.get_beacon_settings() ---")
            same = all(
                getattr(bs, f) == getattr(fresh_bs, f)
                for f in bs.model_dump().keys()
            )
            print(f"  matches cached radio.beacon_settings: {same}")
            if not same:
                dump_beacon(fresh_bs)
        except Exception as e:
            print(f"fresh get_beacon_settings error: {e!r}")


if __name__ == "__main__":
    asyncio.run(main())
