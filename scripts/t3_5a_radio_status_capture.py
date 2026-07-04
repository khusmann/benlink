#!/usr/bin/env python3
"""Tier 3.5.a — capture correlated RADIO_STATUS_CHANGED bodies.

Subscribes to RADIO_STATUS_CHANGED (and HT_STATUS_CHANGED for context)
and prints every event body with a timestamp. Runs for a configurable
duration so an auto-beacon TX will land inside the window (default
360s = 6 min, safely > default 300s beacon interval).

Goal: watch which byte(s) of the 4-byte payload flip during TX (or
whatever else is happening). Anything that changes is a candidate
status-flag bit.

Prints a compact diff line whenever the payload differs from the
previous one, so you can spot the TX transitions at a glance.
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
from benlink.command import UnknownProtocolMessage, StatusChangedEvent
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
WATCH_SECONDS = 360


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


def bit_diff(a: bytes, b: bytes) -> str:
    """Return a human-readable diff of which bit positions differ between a and b."""
    if len(a) != len(b):
        return f"len {len(a)} vs {len(b)}"
    parts = []
    for i in range(len(a)):
        if a[i] != b[i]:
            xor = a[i] ^ b[i]
            # list bit positions (0..7) where a and b differ, LSB-first
            bits = [str(bp) for bp in range(8) if (xor >> bp) & 1]
            parts.append(f"B{i}[{','.join(bits)}] {a[i]:08b}->{b[i]:08b}")
    return " ; ".join(parts) if parts else "no diff"


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        # Compact context
        s = radio.settings
        bs = radio.beacon_settings
        print(f"beacon: should_share={bs.should_share_location} smart={bs.smart_beacon_en} interval={bs.location_share_interval}s ch={s.auto_share_loc_ch+1 if isinstance(s.auto_share_loc_ch,int) else s.auto_share_loc_ch}")

        radio_status_events = []
        ht_status_events = []
        t0 = time.monotonic()

        def on_event(evt):
            t = time.monotonic() - t0
            if isinstance(evt, UnknownProtocolMessage):
                m = evt.message
                # Look for RADIO_STATUS_CHANGED (event_type=8) inside event notifications
                # Since we tolerate it in the parser but don't decode the body,
                # the message.body is an EventNotificationBody with event=UnknownEvent.
                body = getattr(m, "body", None)
                event_type = getattr(body, "event_type", None) if body is not None else None
                inner = getattr(body, "event", None) if body is not None else None
                inner_bytes = getattr(inner, "data", None) if inner is not None else None
                if event_type is not None and inner_bytes is not None:
                    if event_type.name == "RADIO_STATUS_CHANGED":
                        radio_status_events.append((t, bytes(inner_bytes)))
                        prev = radio_status_events[-2][1] if len(radio_status_events) > 1 else None
                        d = bit_diff(prev, inner_bytes) if prev is not None else "(first)"
                        print(f"[{t:7.2f}s] RADIO_STATUS_CHANGED  body={inner_bytes.hex()}  diff={d}")
                        return
                # Anything else unknown: log summarised
                print(f"[{t:7.2f}s] Unknown: {m.command_group.name} {m.command.name} is_reply={m.is_reply}")
            elif isinstance(evt, StatusChangedEvent):
                st = evt.status
                snap = (
                    getattr(st, "is_power_on", None),
                    getattr(st, "is_in_tx", None),
                    getattr(st, "is_in_rx", None),
                    getattr(st, "is_sq", None),
                    getattr(st, "curr_ch_id", None),
                    getattr(st, "is_scan", None),
                    getattr(st, "curr_region", None),
                )
                ht_status_events.append((t, snap))
                # Only print HT_STATUS on change for signal-to-noise
                if len(ht_status_events) == 1 or ht_status_events[-2][1] != snap:
                    print(f"[{t:7.2f}s] HT_STATUS_CHANGED  power={snap[0]} tx={snap[1]} rx={snap[2]} sq={snap[3]} ch={snap[4]} scan={snap[5]} region={snap[6]}")
            # ignore SettingsChanged/BeaconSettingsChanged/etc. for this capture

        unsub = radio.add_event_handler(on_event)

        try:
            await radio.enable_event("RADIO_STATUS_CHANGED")
            print("enabled RADIO_STATUS_CHANGED")
        except Exception as e:
            print(f"enable RADIO_STATUS_CHANGED failed: {e!r}")
        try:
            await radio.enable_event("HT_STATUS_CHANGED")
            print("enabled HT_STATUS_CHANGED")
        except Exception as e:
            print(f"enable HT_STATUS_CHANGED failed: {e!r}")

        print(f"\nwatching {WATCH_SECONDS}s. Auto-beacon interval is {bs.location_share_interval}s, so >=1 TX should land inside this window.")
        print("If you can, also poke the volume knob / channel knob mid-window to trigger extra events.\n")

        try:
            await asyncio.sleep(WATCH_SECONDS)
        finally:
            try:
                unsub()
            except Exception:
                pass

        # summary
        print(f"\nsummary: RADIO_STATUS_CHANGED events={len(radio_status_events)}, HT_STATUS_CHANGED events={len(ht_status_events)}")
        if radio_status_events:
            print("distinct RADIO_STATUS bodies observed:")
            seen = {}
            for t, b in radio_status_events:
                seen.setdefault(b, []).append(t)
            for b, ts in seen.items():
                print(f"  {b.hex()}  count={len(ts)}  first={ts[0]:.2f}s  last={ts[-1]:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
