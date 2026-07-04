#!/usr/bin/env python3
"""Turn on auto-beacon (location share) and turn off all PTT-release beacon signaling.

Result: radio auto-shares position on schedule (interval-driven), but keying
the PTT does NOT append any beacon/ID/location frames to voice transmissions.

Writes (targeted, via set_beacon_settings kwargs):
- should_share_location        = True   (arm the interval-driven beacon)
- ptt_release_send_location    = False  (no auto-append on PTT)
- ptt_release_send_id_info     = False  (no auto-append on PTT)
- ptt_release_send_bss_user_id = False  (no auto-append on PTT)

Leaves alone: aprs_callsign, aprs_ssid, aprs_symbol, beacon_message,
location_share_interval, smart_beacon_*, packet_format, and every other
field. Verified by full-snapshot diff.
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"

TARGETS = {
    "should_share_location": True,
    "ptt_release_send_location": False,
    "ptt_release_send_id_info": False,
    "ptt_release_send_bss_user_id": False,
}

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


def snap(bs):
    return {f: getattr(bs, f) for f in SNAPSHOT_FIELDS}


def diff(before, after):
    return {k: (before[k], after[k]) for k in before if before[k] != after[k]}


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")
    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}\n")

        # sanity: beacon channel should already be pointed at slot 32 (APRS)
        s = radio.settings
        if s.auto_share_loc_ch != 31:
            print(f"WARNING: auto_share_loc_ch = {s.auto_share_loc_ch!r} (expected 31 for slot 32 APRS)")
            print("Refusing to enable auto-beacon while the beacon channel isn't the APRS channel.")
            return
        # sanity: channel 32 should still say APRS on 144.390
        ch32 = radio.channels[31]
        if ch32.name != "APRS" or abs(ch32.rx_freq - 144.390) > 1e-6:
            print(f"WARNING: channels[31] is {ch32.name!r} @ {ch32.rx_freq} (expected APRS @ 144.390)")
            print("Refusing to enable auto-beacon.")
            return
        print(f"pre-flight OK: beacon channel = slot 32 ({ch32.name!r} @ {ch32.rx_freq} {ch32.bandwidth})\n")

        before = snap(radio.beacon_settings)
        print(f"before: {before}\n")

        print(f"applying: {TARGETS}\n")
        await radio.set_beacon_settings(**TARGETS)
        await asyncio.sleep(0.5)

        after = snap(radio.beacon_settings)
        d = diff(before, after)
        print(f"fields changed: {d}\n")

        # every target should now equal the target value
        ok_targets = all(after[k] == v for k, v in TARGETS.items())
        # nothing else should have changed
        ok_scope = set(d.keys()).issubset(set(TARGETS.keys()))

        if ok_targets and ok_scope:
            print("SUCCESS")
            print(f"  auto-beacon ARMED: should_share_location={after['should_share_location']}")
            print(f"  interval: {after['location_share_interval']}s")
            print(f"  packet_format: {after['packet_format']}")
            print(f"  callsign-ssid: {after['aprs_callsign']}-{after['aprs_ssid']}")
            print(f"  symbol: {after['aprs_symbol']!r} (person on primary APRS table)")
            print(f"  beacon channel: slot 32 = {ch32.name} {ch32.rx_freq} MHz {ch32.bandwidth} FM")
            print(f"  PTT signaling all OFF:")
            for k in ("ptt_release_send_location", "ptt_release_send_id_info", "ptt_release_send_bss_user_id"):
                print(f"    {k} = {after[k]}")
            print("\nRadio will now transmit APRS position every "
                  f"{after['location_share_interval']}s (= {after['location_share_interval']//60} min) on 144.390 MHz.")
            print("Voice PTT will NOT append any auto-signaling.")
        else:
            print("VERIFY FAILED")
            print(f"  all targets took: {ok_targets}")
            print(f"  scope contained:  {ok_scope} (unexpected diff keys: {set(d.keys()) - set(TARGETS.keys())})")


if __name__ == "__main__":
    asyncio.run(main())
