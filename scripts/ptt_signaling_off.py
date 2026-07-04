#!/usr/bin/env python3
"""Turn off every "PTT signals something" flag on the N76 beacon config.

Leaves auto-beacon (interval + smart_beacon) fully armed. Just makes sure
that keying the mic to talk does NOT also broadcast position, callsign
ID, BSS user id, or Mic-E-compressed position.

Writes:
- ptt_release_send_location    = False
- ptt_release_send_id_info     = False
- ptt_release_send_bss_user_id = False
- mic_e_en                     = False   (Mic-E appends pos to voice PTT)

Also verifies send_id_by_aprs stays False.
"""
import asyncio
from bleak import BleakScanner
import benlink.controller as bc
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"

TARGETS = {
    "ptt_release_send_location": False,
    "ptt_release_send_id_info": False,
    "ptt_release_send_bss_user_id": False,
    "mic_e_en": False,
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

        before = snap(radio.beacon_settings)
        print(f"before: {before}\n")

        print(f"applying: {TARGETS}\n")
        await radio.set_beacon_settings(**TARGETS)
        await asyncio.sleep(0.5)

        after = snap(radio.beacon_settings)
        d = diff(before, after)
        print(f"fields changed: {d}\n")

        ok_targets = all(after[k] == v for k, v in TARGETS.items())
        ok_scope = set(d.keys()).issubset(set(TARGETS.keys()))
        # sanity: send_id_by_aprs should still be False
        ok_extras = (after["send_id_by_aprs"] is False)

        if ok_targets and ok_scope and ok_extras:
            print("SUCCESS: all PTT signaling disabled")
            print(f"  auto-beacon still ARMED: should_share_location={after['should_share_location']}")
            print(f"  smart_beacon_en          = {after['smart_beacon_en']}")
            print(f"  interval                 = {after['location_share_interval']}s")
            print(f"  callsign-ssid            = {after['aprs_callsign']}-{after['aprs_ssid']}")
            print(f"  PTT-release flags all OFF:")
            for k in ("ptt_release_send_location", "ptt_release_send_id_info", "ptt_release_send_bss_user_id", "mic_e_en", "send_id_by_aprs"):
                print(f"    {k:32s} = {after[k]}")
        else:
            print("VERIFY FAILED")
            print(f"  targets took: {ok_targets}")
            print(f"  scope contained: {ok_scope} (unexpected diff keys: {set(d.keys()) - set(TARGETS.keys())})")
            print(f"  send_id_by_aprs still False: {ok_extras}")


if __name__ == "__main__":
    asyncio.run(main())
