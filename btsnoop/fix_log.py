#!/bin/env python3
from __future__ import annotations
import csv
import sys

from benlink.protocol import GaiaFrame, Message
from benlink.protocol.command.bitfield import BitStream


def to_text(cmd: bytes):
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in cmd])


reader = csv.DictReader(sys.stdin)

output_header = [
    "id", "dir", "is_known", "group", "is_reply", "command", "message", "original"
]

writer = csv.DictWriter(sys.stdout, fieldnames=output_header)
writer.writeheader()

phone_to_radio = BitStream()
radio_to_phone = BitStream()

for snoop_frame in reader:
    if snoop_frame["id"] == "NEW_BTSNOOP":
        writer.writerow({
            "id": "NEW_BTSNOOP"
        })
        continue

    data = bytes.fromhex(snoop_frame["data"].replace(":", ""))

    match snoop_frame["dir"]:
        case "phone->radio":
            phone_to_radio = phone_to_radio.extend_bytes(data)
            frames, phone_to_radio = GaiaFrame.from_bitstream_batch(
                phone_to_radio,
                consume_errors=True,
            )
        case "radio->phone":
            radio_to_phone = radio_to_phone.extend_bytes(data)
            frames, radio_to_phone = GaiaFrame.from_bitstream_batch(
                radio_to_phone,
                consume_errors=True,
            )
        case _:
            raise ValueError(f"Unknown direction: {snoop_frame['dir']}")

    for frame in frames:
        message = Message.from_bytes(frame.data)
        writer.writerow({
            "id": snoop_frame["id"],
            "dir": snoop_frame["dir"],
            "is_known": True,
            "group": message.command_group.name,
            "is_reply": message.is_reply,
            "command": message.command.name,
            "message": str(message.body),
            "original": message.to_bytes()
        })
