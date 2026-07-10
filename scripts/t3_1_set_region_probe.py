#!/usr/bin/env python3
"""Tier 3.1 probe — try SET_REGION with a guessed body shape.

Guess: body is a single byte `region_id` (0-based).

Strategy:
1. Read radio.status.curr_region -> that's the baseline. Call it R0.
2. Fresh-read the channel table for R0 (channels 0..31) via
   _conn.get_channel(). Snapshot names + (rx_freq, tx_freq) tuples.
3. Pick a probe target != R0 (safe: 0, or 1 if baseline is 0).
4. Send raw SET_REGION with body=bytes([probe_target]).
5. Poll radio.status.curr_region for up to 3s to see if it flipped.
6. Fresh-read the channel table again (bypasses the stale cache) and
   snapshot.
7. Diff the two snapshots. If any slot's name or freq differs, the
   region really switched. If they match completely, either (a) both
   banks are identical (user duplicated), or (b) SET_REGION didn't
   actually take.
8. Restore: send SET_REGION with body=bytes([R0]). Verify.

We log every UnknownProtocolMessage we see during the probe so if
SET_REGION emits a reply we can capture its shape.
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
CHANNELS_TO_SAMPLE = list(range(32))


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


async def snapshot_channels(radio):
    """Fresh-read every channel via _conn.get_channel() (bypasses cache)."""
    snap = {}
    for i in CHANNELS_TO_SAMPLE:
        try:
            ch = await radio._conn.get_channel(i)
            snap[i] = (ch.name, round(ch.rx_freq, 4), round(ch.tx_freq, 4), ch.bandwidth)
        except Exception as e:
            snap[i] = f"<err {e!r}>"
    return snap


def diff_snapshots(a, b):
    changed = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            changed.append((k, a.get(k), b.get(k)))
    return changed


async def send_set_region(radio, region_id: int):
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

        probe = 0 if baseline != 0 else 1
        print(f"probe target = {probe} (safe: known-existing group)\n")

        reply_events = []

        def raw_handler(radio_msg):
            if isinstance(radio_msg, UnknownProtocolMessage):
                msg = radio_msg.message
                reply_events.append((time.monotonic(), msg))
                body = msg.body
                body_hex = body.hex() if isinstance(body, (bytes, bytearray)) else repr(body)[:80]
                print(f"    <- {msg.command_group.name} {msg.command.name} is_reply={msg.is_reply} body={body_hex}")

        remove_raw = radio._conn._add_message_handler(raw_handler)

        try:
            # --- baseline channel snapshot ---
            print(f"snapshotting {len(CHANNELS_TO_SAMPLE)} channels in baseline region {baseline}...")
            snap_baseline = await snapshot_channels(radio)
            populated = sum(1 for v in snap_baseline.values() if isinstance(v, tuple) and v[0])
            print(f"  {populated} slots have a non-empty name")
            # Show first few for reference
            for i in [0, 15, 31]:
                print(f"    slot {i}: {snap_baseline.get(i)}")

            # --- probe ---
            print(f"\n[probe] switching to region {probe}...")
            await send_set_region(radio, probe)
            ok = await wait_curr_region(radio, probe, timeout_s=3.0)
            print(f"  curr_region after probe = {radio.status.curr_region}")
            print(f"  probe curr_region flipped: {ok}")

            # Wait a beat and re-snapshot
            await asyncio.sleep(0.5)
            print(f"\nsnapshotting {len(CHANNELS_TO_SAMPLE)} channels in probe region {probe}...")
            snap_probe = await snapshot_channels(radio)
            populated_probe = sum(1 for v in snap_probe.values() if isinstance(v, tuple) and v[0])
            print(f"  {populated_probe} slots have a non-empty name")
            for i in [0, 15, 31]:
                print(f"    slot {i}: {snap_probe.get(i)}")

            changed = diff_snapshots(snap_baseline, snap_probe)
            print(f"\n{len(changed)}/{len(CHANNELS_TO_SAMPLE)} slots differ between baseline and probe")
            for slot, before, after in changed[:8]:  # limit output
                print(f"  slot {slot}: {before}  =>  {after}")
            if len(changed) > 8:
                print(f"  ... {len(changed) - 8} more")

            # --- restore ---
            print(f"\n[restore] switching back to region {baseline}...")
            await send_set_region(radio, baseline)
            ok_restore = await wait_curr_region(radio, baseline, timeout_s=3.0)
            print(f"  curr_region after restore = {radio.status.curr_region}")
            print(f"  restore took: {ok_restore}")

            # Final sanity: verify a couple of channels in restored region match baseline
            print(f"\nverifying restored region matches baseline...")
            snap_after = await snapshot_channels(radio)
            drift = diff_snapshots(snap_baseline, snap_after)
            print(f"  {len(drift)}/{len(CHANNELS_TO_SAMPLE)} slots differ vs baseline (want 0)")
            for slot, before, after in drift[:4]:
                print(f"    slot {slot}: {before}  =>  {after}")

        finally:
            remove_raw()

        # --- verdict ---
        print(f"\n=== RESULT ===")
        set_region_replies = [
            (t, m) for (t, m) in reply_events
            if m.command == p.BasicCommand.SET_REGION and m.is_reply
        ]
        print(f"SET_REGION reply frames observed: {len(set_region_replies)}")
        for t, m in set_region_replies:
            body = m.body
            print(f"  reply body: {body.hex() if isinstance(body, (bytes, bytearray)) else body!r}")

        if ok and ok_restore:
            if changed:
                print(f"\n\u2705 SET_REGION with 1-byte body WORKS. curr_region flipped, "
                      f"{len(changed)} channel slots differ between banks, and baseline restored.")
            else:
                print(f"\n\u26a0\ufe0f  curr_region flipped both ways, but the two banks look identical "
                      f"(all {len(CHANNELS_TO_SAMPLE)} channels match). Either you've duplicated the "
                      f"same channel table across both banks, or channels[] doesn't actually vary per region.")
        else:
            print(f"\n\u274c curr_region didn't flip as expected. SET_REGION guess may be wrong. "
                  f"See raw frames above for the actual reply shape.")


if __name__ == "__main__":
    asyncio.run(main())
