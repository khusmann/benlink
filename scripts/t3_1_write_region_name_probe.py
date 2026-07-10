#!/usr/bin/env python3
"""Tier 3.1 probe — WRITE_REGION_NAME (opcode 59).

Guess: request body mirrors READ_REGION_NAME's success reply payload:
  <region_id: u8><name: str(10)>  = 11 bytes
Reply body: <reply_status: u8> = 1 byte

Uses blank region 5 as the target (verified blank by earlier probe:
name = ''). Writes a probe name, reads back, restores baseline (blank).

If the guess is wrong, we'll see it via:
- unexpected reply size or nonzero status
- READ_REGION_NAME(5) still returning the old blank name

Never touches Eric's named regions (0, 1, 2) or his active one (3).
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
PROBE_REGION = 5  # confirmed blank on Eric's radio
PROBE_NAME = "BENLINK"  # 7 chars, well under the 10-byte field


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


async def send_write_region_name(radio, region_id: int, name: str, reply_events: list, timeout_s: float = 2.0):
    """Send WRITE_REGION_NAME with guessed body shape; wait for reply."""
    name_bytes = name.encode("ascii").ljust(10, b"\x00")[:10]
    body = bytes([region_id]) + name_bytes
    assert len(body) == 11, f"body must be 11 bytes, got {len(body)}"
    raw = p.Message(
        command_group=p.CommandGroup.BASIC,
        is_reply=False,
        command=p.BasicCommand.WRITE_REGION_NAME,
        body=body,
    )
    print(f"  -> WRITE_REGION_NAME region_id={region_id} name={name!r} body={body.hex()}")
    before = len(reply_events)
    await radio._conn._link.send(raw)
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        for (t, msg) in reply_events[before:]:
            if msg.command == p.BasicCommand.WRITE_REGION_NAME and msg.is_reply:
                return msg
        await asyncio.sleep(0.05)
    return None


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        # Safety: probe target must be blank on read
        baseline_name = await radio.get_region_name(PROBE_REGION)
        if baseline_name is None:
            print(f"ABORT: region {PROBE_REGION} does not exist (get_region_name returned None)")
            return
        if baseline_name.strip():
            print(f"ABORT: region {PROBE_REGION} already has a name ({baseline_name!r}); refusing to overwrite")
            return
        print(f"baseline region {PROBE_REGION} is blank (name={baseline_name!r}); safe to write\n")

        reply_events = []

        def raw_handler(radio_msg):
            if isinstance(radio_msg, UnknownProtocolMessage):
                msg = radio_msg.message
                reply_events.append((time.monotonic(), msg))
                if msg.command == p.BasicCommand.WRITE_REGION_NAME and msg.is_reply:
                    body = msg.body
                    body_hex = body.hex() if isinstance(body, (bytes, bytearray)) else repr(body)[:80]
                    print(f"    <- WRITE_REGION_NAME reply is_reply={msg.is_reply} body={body_hex}")

        remove_raw = radio._conn._add_message_handler(raw_handler)

        try:
            # --- write probe ---
            print(f"[write] set region {PROBE_REGION} name = {PROBE_NAME!r}")
            reply = await send_write_region_name(radio, PROBE_REGION, PROBE_NAME, reply_events)
            if reply is None:
                print("  no reply within timeout")
                return

            # Read back
            await asyncio.sleep(0.3)
            read_back = await radio.get_region_name(PROBE_REGION)
            print(f"  read-back: {read_back!r}")
            ok_write = (read_back is not None) and (read_back.rstrip("\x00").strip() == PROBE_NAME)
            print(f"  write took: {ok_write}")

            # --- restore ---
            print(f"\n[restore] clear region {PROBE_REGION} name")
            reply2 = await send_write_region_name(radio, PROBE_REGION, "", reply_events)
            if reply2 is None:
                print("  no reply within timeout on restore")

            await asyncio.sleep(0.3)
            after = await radio.get_region_name(PROBE_REGION)
            print(f"  read-back after restore: {after!r}")
            ok_restore = (after is not None) and (not after.strip())
            print(f"  restore clean: {ok_restore}")

        finally:
            remove_raw()

        # summary
        print("\n=== RESULT ===")
        write_replies = [
            (t, m) for (t, m) in reply_events
            if m.command == p.BasicCommand.WRITE_REGION_NAME and m.is_reply
        ]
        print(f"WRITE_REGION_NAME reply frames: {len(write_replies)}")
        for t, m in write_replies:
            body = m.body
            print(f"  reply body: {body.hex() if isinstance(body, (bytes, bytearray)) else body!r}")

        if ok_write and ok_restore:
            print(f"\n\u2705 WRITE_REGION_NAME with 11-byte body (<region_id><name:str(10)>) WORKS.")
        else:
            print(f"\n\u274c write or restore failed. See raw frames above.")


if __name__ == "__main__":
    asyncio.run(main())
