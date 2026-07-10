#!/usr/bin/env python3
"""Tier 3.1 probe — WRITE_REGION_CH (opcode 58).

Guess: request body is <region_id: u8> followed by the same RfCh body
that WRITE_RF_CH (opcode 14) uses. Reply is probably
<reply_status: u8> maybe followed by <region_id><channel_id>.

Strategy (super careful):
1. Save baseline: current region R0. Switch to target region R_target=5.
2. Snapshot the existing channel at slot 31 of R5 (whatever is there).
3. Switch back to R0. All subsequent probes leave curr_region = R0.
4. Build a distinctive Channel object (name='TEST31', 145.500 MHz, tx_disable=True).
5. Send WRITE_REGION_CH(region_id=5, RfCh=<distinctive>). Reply?
6. Switch to R5, get_channel(31), verify it's our distinctive value.
7. Switch back to R0, restore: WRITE_REGION_CH(region_id=5, RfCh=<baseline>).
8. Switch to R5 one more time, verify slot 31 matches the original.
9. Switch back to R0.

The tx_disable=True on the probe channel is extra insurance: even if
something gets misdirected, the channel isn't transmit-capable.
"""
import asyncio
import time
from bleak import BleakScanner
import benlink.controller as bc
import benlink.protocol as p
from benlink.command import UnknownProtocolMessage, Channel
from _teelog import setup_teelog

setup_teelog(__file__)

KNOWN_UUID = "377F7AC2-2AA3-D0F4-8DDC-D89A4C3594C6"
TARGET_REGION = 5
TARGET_SLOT = 31


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.address.upper() == KNOWN_UUID.upper():
            return d.address
        if d.name and "VR-N76" in d.name.upper():
            return d.address
    raise RuntimeError("N76 not found")


async def send_write_region_ch(radio, region_id: int, channel: Channel, reply_events: list, timeout_s: float = 3.0):
    """Send WRITE_REGION_CH with guessed body: <region_id><RfCh>."""
    rfch = channel.to_protocol()
    rfch_bytes = rfch.to_bytes()
    body = bytes([region_id]) + rfch_bytes
    print(f"  -> WRITE_REGION_CH region_id={region_id} slot={channel.channel_id} "
          f"name={channel.name!r} freq={channel.rx_freq} body_len={len(body)}")
    print(f"     body hex: {body.hex()}")
    raw = p.Message(
        command_group=p.CommandGroup.BASIC,
        is_reply=False,
        command=p.BasicCommand.WRITE_REGION_CH,
        body=body,
    )
    before = len(reply_events)
    await radio._conn._link.send(raw)
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        for (t, msg) in reply_events[before:]:
            if msg.command == p.BasicCommand.WRITE_REGION_CH and msg.is_reply:
                return msg
        await asyncio.sleep(0.05)
    return None


async def switch_region(radio, region_id: int):
    """Switch and confirm."""
    await radio.set_region(region_id)
    assert radio.status.curr_region == region_id, f"expected region {region_id}, got {radio.status.curr_region}"


def channel_signature(ch: Channel):
    """Compact signature of a channel for diffing."""
    return (
        ch.name,
        round(ch.rx_freq, 4),
        round(ch.tx_freq, 4),
        ch.bandwidth,
        ch.rx_sub_audio,
        ch.tx_sub_audio,
        ch.scan,
        ch.tx_disable,
    )


async def main() -> None:
    address = await find_radio()
    print(f"connecting to {address}...")

    async with bc.RadioController.new_ble(address) as radio:
        di = radio.device_info
        print(f"connected: fw={di.firmware_version}")

        R0 = radio.status.curr_region
        print(f"baseline curr_region = {R0}\n")

        assert R0 != TARGET_REGION, f"already in target region {TARGET_REGION}; script assumes we start elsewhere"

        # --- capture baseline of target region slot ---
        print(f"[baseline] switching to region {TARGET_REGION} to snapshot slot {TARGET_SLOT}...")
        await switch_region(radio, TARGET_REGION)
        baseline_channel = radio.channels[TARGET_SLOT]
        baseline_sig = channel_signature(baseline_channel)
        print(f"  slot {TARGET_SLOT} baseline: {baseline_sig}")

        print(f"[baseline] switching back to region {R0}...")
        await switch_region(radio, R0)

        reply_events = []

        def raw_handler(radio_msg):
            if isinstance(radio_msg, UnknownProtocolMessage):
                msg = radio_msg.message
                reply_events.append((time.monotonic(), msg))
                if msg.command == p.BasicCommand.WRITE_REGION_CH and msg.is_reply:
                    body = msg.body
                    body_hex = body.hex() if isinstance(body, (bytes, bytearray)) else repr(body)[:80]
                    print(f"    <- WRITE_REGION_CH reply body={body_hex}")

        remove_raw = radio._conn._add_message_handler(raw_handler)

        try:
            # --- build a distinctive probe channel ---
            probe_channel = baseline_channel.model_copy(update=dict(
                channel_id=TARGET_SLOT,
                name="TEST31",
                rx_freq=145.500,
                tx_freq=145.500,
                rx_mod="FM",
                tx_mod="FM",
                bandwidth="WIDE",
                rx_sub_audio=None,
                tx_sub_audio=None,
                scan=False,
                tx_disable=True,   # belt-and-suspenders
                talk_around=False,
                mute=False,
            ))
            print(f"\n[write] writing probe channel to region {TARGET_REGION} slot {TARGET_SLOT}")
            reply = await send_write_region_ch(radio, TARGET_REGION, probe_channel, reply_events)
            if reply is None:
                print("  no reply within timeout")
                # try to restore state and bail
                return

            # Verify: switch to region 5, read slot 31
            print(f"\n[verify] switching to region {TARGET_REGION} to read back...")
            await switch_region(radio, TARGET_REGION)
            after = radio.channels[TARGET_SLOT]
            after_sig = channel_signature(after)
            print(f"  slot {TARGET_SLOT} after write: {after_sig}")

            probe_sig = channel_signature(probe_channel)
            ok_write = (after_sig == probe_sig)
            print(f"  matches probe channel signature: {ok_write}")

            # --- restore ---
            print(f"\n[restore] switching back to region {R0} to send restore write...")
            await switch_region(radio, R0)
            print(f"[restore] writing baseline back to region {TARGET_REGION} slot {TARGET_SLOT}")
            reply2 = await send_write_region_ch(radio, TARGET_REGION, baseline_channel, reply_events)
            if reply2 is None:
                print("  no reply on restore")

            print(f"[verify] switching to region {TARGET_REGION} to verify restore...")
            await switch_region(radio, TARGET_REGION)
            restored = radio.channels[TARGET_SLOT]
            restored_sig = channel_signature(restored)
            print(f"  slot {TARGET_SLOT} after restore: {restored_sig}")
            ok_restore = (restored_sig == baseline_sig)
            print(f"  matches original baseline: {ok_restore}")

            print(f"\n[cleanup] switching back to original region {R0}...")
            await switch_region(radio, R0)

        finally:
            remove_raw()

        # summary
        print("\n=== RESULT ===")
        write_replies = [
            (t, m) for (t, m) in reply_events
            if m.command == p.BasicCommand.WRITE_REGION_CH and m.is_reply
        ]
        print(f"WRITE_REGION_CH reply frames: {len(write_replies)}")
        for t, m in write_replies:
            body = m.body
            body_bytes = bytes(body) if isinstance(body, (bytes, bytearray)) else b""
            print(f"  reply len={len(body_bytes)} body: {body_bytes.hex()}")

        if ok_write and ok_restore:
            print("\n\u2705 WRITE_REGION_CH with <region_id><RfCh> body WORKS.")
        else:
            print("\n\u274c write or restore failed. See raw frames above.")


if __name__ == "__main__":
    asyncio.run(main())
