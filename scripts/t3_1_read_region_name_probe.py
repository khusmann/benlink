#!/usr/bin/env python3
"""Tier 3.1 probe — READ_REGION_NAME (opcode 73).

Guesses:
  request body: 1 byte region_id (0-based) [same shape as SET_REGION]
  reply body:   1 byte reply_status + N-byte name string (N unknown yet)

Reads region names for ids 0..11 (N76 UI shows 12 groups max). Dumps
each reply's raw bytes with hex + ASCII rendering so we can see the
name field length and any trailing status/padding bytes.

Strictly read-only. No writes, no region switch — reads don't
implicate the currently-active region.
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
import benlink.protocol as p
from benlink.command import UnknownProtocolMessage
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


def render_ascii(b: bytes) -> str:
    return "".join(chr(x) if 0x20 <= x < 0x7f else "." for x in b)


async def read_region_name(radio, region_id: int, reply_events: list, timeout_s: float = 2.0):
    """Send READ_REGION_NAME with 1-byte body; wait briefly for reply."""
    body = bytes([region_id])
    raw = p.Message(
        command_group=p.CommandGroup.BASIC,
        is_reply=False,
        command=p.BasicCommand.READ_REGION_NAME,
        body=body,
    )
    before = len(reply_events)
    await radio._conn._link.send(raw)
    # Wait for reply
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        # scan for a new reply frame matching READ_REGION_NAME with is_reply=True
        for (t, msg) in reply_events[before:]:
            if msg.command == p.BasicCommand.READ_REGION_NAME and msg.is_reply:
                return msg
        await asyncio.sleep(0.05)
    return None


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        current = radio.status.curr_region
        print(f"current region = {current} (not changing it)\n")

        reply_events = []

        def raw_handler(radio_msg):
            if isinstance(radio_msg, UnknownProtocolMessage):
                msg = radio_msg.message
                reply_events.append((time.monotonic(), msg))
                if msg.command == p.BasicCommand.READ_REGION_NAME and msg.is_reply:
                    body = msg.body
                    body_bytes = body if isinstance(body, (bytes, bytearray)) else b""
                    print(f"    <- READ_REGION_NAME reply len={len(body_bytes)} hex={body_bytes.hex()} ascii={render_ascii(bytes(body_bytes))!r}")

        remove_raw = radio._conn._add_message_handler(raw_handler)

        try:
            for region_id in range(12):
                print(f"[probe] READ_REGION_NAME region_id={region_id}")
                reply = await read_region_name(radio, region_id, reply_events)
                if reply is None:
                    print(f"  no reply within timeout")
                # small delay so replies don't stack up
                await asyncio.sleep(0.15)
        finally:
            remove_raw()

        # Summary
        rn_replies = [
            (t, m) for (t, m) in reply_events
            if m.command == p.BasicCommand.READ_REGION_NAME and m.is_reply
        ]
        print(f"\n=== SUMMARY: {len(rn_replies)} READ_REGION_NAME replies captured ===")
        for i, (t, m) in enumerate(rn_replies):
            body = m.body
            body_bytes = bytes(body) if isinstance(body, (bytes, bytearray)) else b""
            # Hypothesis: first byte = reply_status, rest = name
            first = body_bytes[0] if body_bytes else None
            name_field = body_bytes[1:]
            name_str = name_field.rstrip(b"\x00").decode("ascii", errors="replace") if name_field else ""
            print(f"  region ~{i}:  status_byte={first}  name_field({len(name_field)}B)={name_str!r}  raw={body_bytes.hex()}")


if __name__ == "__main__":
    asyncio.run(main())
