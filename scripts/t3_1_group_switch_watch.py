#!/usr/bin/env python3
"""Tier 3.1 recon — watch what fires when the user switches groups on the N76.

Subscribes to EVERY event benlink knows about + dumps raw bytes for anything
that falls through as UnknownProtocolMessage. Prints:
  - HT_STATUS_CHANGED with curr_region (this is the key signal)
  - HT_SETTINGS_CHANGED (fires on most menu changes)
  - HT_CH_CHANGED (channel index inside the current group)
  - BSS_SETTINGS_CHANGED / TncDataFragmentReceived / etc.
  - Any UnknownProtocolMessage with command_group, command, is_reply, body hex

Duration: 240s. Instruction to Eric: cycle through several groups (1 -> 2 -> 3
-> back to 1). The N76 UI calls them "groups"; each has its own name and
32-slot channel table.
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
from benlink.command import (
    UnknownProtocolMessage,
    StatusChangedEvent,
    SettingsChangedEvent,
    ChannelChangedEvent,
    BeaconSettingsChangedEvent,
    TncDataFragmentReceivedEvent,
    NotificationAckEvent,
)
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
WATCH_SECONDS = 240

ALL_EVENTS = [
    "HT_STATUS_CHANGED",
    "DATA_RXD",
    "NEW_INQUIRY_DATA",
    "RESTORE_FACTORY_SETTINGS",
    "HT_CH_CHANGED",
    "HT_SETTINGS_CHANGED",
    "RINGING_STOPPED",
    "RADIO_STATUS_CHANGED",
    "USER_ACTION",
    "SYSTEM_EVENT",
    "BSS_SETTINGS_CHANGED",
    "DATA_TXD",
    "POSITION_CHANGED",
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


def compact_status(st):
    """Return a compact tuple of the interesting HT_STATUS fields."""
    return {
        "curr_region": getattr(st, "curr_region", None),
        "curr_ch_id": getattr(st, "curr_ch_id", None),
        "curr_channel_id_lower": getattr(st, "curr_channel_id_lower", None),
        "is_power_on": getattr(st, "is_power_on", None),
        "is_in_tx": getattr(st, "is_in_tx", None),
        "is_in_rx": getattr(st, "is_in_rx", None),
        "is_sq": getattr(st, "is_sq", None),
        "double_channel": getattr(st, "double_channel", None),
        "is_scan": getattr(st, "is_scan", None),
    }


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")
    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        s = radio.settings
        # curr_region is on the Status struct, not Settings — read via status
        # (radio.status was pre-populated during connect)
        try:
            initial_status = compact_status(radio.status)
            print(f"initial status: {initial_status}")
        except Exception as e:
            print(f"radio.status peek failed: {e!r}")

        t0 = time.monotonic()
        last_status = None
        counts = {"status": 0, "settings": 0, "channel": 0, "beacon": 0, "unknown": 0, "ack": 0, "other": 0}

        def on_event(evt):
            nonlocal last_status
            t = time.monotonic() - t0
            if isinstance(evt, StatusChangedEvent):
                counts["status"] += 1
                cur = compact_status(evt.status)
                if cur != last_status:
                    print(f"[{t:7.2f}s] HT_STATUS_CHANGED  {cur}")
                    last_status = cur
                # else: same as before, skip to keep noise down
            elif isinstance(evt, ChannelChangedEvent):
                counts["channel"] += 1
                c = evt.channel
                print(f"[{t:7.2f}s] HT_CH_CHANGED  ch={c.channel_id} name={c.name!r} rx={c.rx_freq}")
            elif isinstance(evt, SettingsChangedEvent):
                counts["settings"] += 1
                # keep it terse — just note the fact
                st = evt.settings
                print(f"[{t:7.2f}s] HT_SETTINGS_CHANGED  ch_a={st.channel_a} ch_b={st.channel_b} scan={st.scan}")
            elif isinstance(evt, BeaconSettingsChangedEvent):
                counts["beacon"] += 1
                print(f"[{t:7.2f}s] BeaconSettingsChanged  (skip details)")
            elif isinstance(evt, TncDataFragmentReceivedEvent):
                print(f"[{t:7.2f}s] TncDataFragmentReceived")
            elif isinstance(evt, NotificationAckEvent):
                counts["ack"] += 1
                # silence acks
            elif isinstance(evt, UnknownProtocolMessage):
                counts["unknown"] += 1
                m = evt.message
                body = getattr(m, "body", None)
                # If body is an EventNotificationBody with an event field, dig deeper
                event_type = getattr(body, "event_type", None) if body is not None else None
                inner = getattr(body, "event", None) if body is not None else None
                inner_bytes = getattr(inner, "data", None) if inner is not None else None
                if event_type is not None and inner_bytes is not None:
                    print(f"[{t:7.2f}s] Unknown EventNotification: type={event_type.name}  body={bytes(inner_bytes).hex()}")
                elif isinstance(body, (bytes, bytearray)):
                    print(f"[{t:7.2f}s] Unknown: {m.command_group.name} {m.command.name} is_reply={m.is_reply} body={bytes(body).hex()}")
                else:
                    print(f"[{t:7.2f}s] Unknown: {m.command_group.name} {m.command.name} is_reply={m.is_reply} body_type={type(body).__name__}")
            else:
                counts["other"] += 1
                print(f"[{t:7.2f}s] {type(evt).__name__}")

        unsub = radio.add_event_handler(on_event)

        # Enable everything so anything the radio wants to send us shows up.
        for ev in ALL_EVENTS:
            try:
                await radio.enable_event(ev)
            except Exception as e:
                print(f"enable_event({ev}) failed: {e!r}")

        print(f"\nwatching {WATCH_SECONDS}s.")
        print("Please switch through groups on the radio (Group 1 -> 2 -> 3 -> back to 1).")
        print("Between switches, wait ~5-10s so the events are easy to visually separate.\n")

        try:
            await asyncio.sleep(WATCH_SECONDS)
        finally:
            try:
                unsub()
            except Exception:
                pass

        print(f"\nsummary: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
