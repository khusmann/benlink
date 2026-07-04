#!/usr/bin/env python3
"""Tier 3.1 probe — try SET_REGION with a guessed body shape.

Guess: body is a single byte `region_id` (0-based).

Strategy:
1. Read radio.status.curr_region -> that's the baseline. Call it R0.
2. Pick a probe target != R0 (small, known-safe range, e.g. R0 XOR 1).
3. Send a raw SET_REGION message with body=bytes([probe_target]).
4. Watch for the reply frame (whatever shape) and for HT_STATUS_CHANGED
   events. If curr_region flips to probe_target, the guess was right.
5. Restore: send another SET_REGION with body=bytes([R0]).
6. Verify curr_region is back to R0.

If the reply comes back with a nonzero reply_status byte or with a
different body length, we log everything so we can adjust the guess.
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
import benlink.protocol as p
from benlink.command import (
    StatusChangedEvent,
    UnknownProtocolMessage,
)
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


async def send_set_region(radio, region_id: int, reply_events: list):
    """Send a raw SET_REGION frame; log any incoming reply/event bytes."""
    body = bytes([region_id])
    raw = p.Message(
        command_group=p.CommandGroup.BASIC,
        is_reply=False,
        command=p.BasicCommand.SET_REGION,
        body=body,
    )
    print(f"  -> SET_REGION region_id={region_id} body={body.hex()}")
    await radio._conn._link.send(raw)


async def wait_curr_region(radio, target: int, timeout_s: float = 3.0) -> bool:
    """Poll radio.status.curr_region for up to timeout_s."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if radio.status.curr_region == target:
            return True
        await asyncio.sleep(0.1)
    return False


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        baseline = radio.status.curr_region
        print(f"baseline curr_region = {baseline}")

        # Pick a probe target that isn't the baseline. Prefer 0 if baseline!=0
        # (safest: group 1 always exists), else 1.
        probe = 0 if baseline != 0 else 1
        print(f"probe target = {probe} (safe: known-existing group)")

        reply_events = []

        # The connection handler receives RadioMessage (transformed), not the
        # raw p.Message. For opcodes benlink doesn't understand (like
        # SET_REGION), the transform result is UnknownProtocolMessage wrapping
        # the raw p.Message. Unwrap it here.
        def raw_handler(radio_msg):
            if isinstance(radio_msg, UnknownProtocolMessage):
                msg = radio_msg.message
                reply_events.append((time.monotonic(), msg))
                body = msg.body
                body_hex = body.hex() if isinstance(body, (bytes, bytearray)) else repr(body)[:80]
                print(f"    <- {msg.command_group.name} {msg.command.name} is_reply={msg.is_reply} body={body_hex}")

        remove_raw = radio._conn._add_message_handler(raw_handler)

        try:
            # --- probe ---
            print(f"\n[probe] switching to region {probe}...")
            await send_set_region(radio, probe, reply_events)
            ok = await wait_curr_region(radio, probe, timeout_s=3.0)
            print(f"  curr_region after probe = {radio.status.curr_region}")
            print(f"  probe took: {ok}")

            # small settle
            await asyncio.sleep(0.5)

            # --- restore ---
            print(f"\n[restore] switching back to region {baseline}...")
            await send_set_region(radio, baseline, reply_events)
            ok_restore = await wait_curr_region(radio, baseline, timeout_s=3.0)
            print(f"  curr_region after restore = {radio.status.curr_region}")
            print(f"  restore took: {ok_restore}")

        finally:
            remove_raw()

        # Summary
        print(f"\ntotal Unknown frames captured (from handler): {len(reply_events)}")
        set_region_replies = [
            (t, m) for (t, m) in reply_events
            if m.command == p.BasicCommand.SET_REGION and m.is_reply
        ]
        print(f"SET_REGION reply frames: {len(set_region_replies)}")
        for t, m in set_region_replies:
            body = m.body
            print(f"  reply body: {body.hex() if isinstance(body, (bytes, bytearray)) else body!r}")

        if ok and ok_restore:
            print("\nRESULT: SET_REGION with 1-byte body works.")
            print("  Half of Tier 3.1 write-side is now proven (needs proper Body struct in fork).")
        else:
            print("\nRESULT: probe or restore didn't take. See raw frames above for the actual reply shape.")


if __name__ == "__main__":
    asyncio.run(main())
