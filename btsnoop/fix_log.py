#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t

from benlink.internal.protocol import GaiaFrame
from benlink.internal.bitfield import BitStream


class GaiaFrameStream:
    _stream: BitStream

    def __init__(self):
        self._stream = BitStream()

    def update(self, data: bytes) -> t.List[GaiaFrame]:
        self._stream = self._stream.extend_bytes(data)

        messages: t.List[GaiaFrame] = []

        while self._stream.remaining():
            if self._stream.peek_bytes(1) != b"\xff":
                print("Warning: skipping unknown data", file=sys.stderr)
                while self._stream.remaining() and self._stream.peek_bytes(1) != b"\xff":
                    _, self._stream = self._stream.take_bytes(1)

            try:
                value, self._stream = GaiaFrame.from_bitstream(self._stream)
                messages.append(value)
            except EOFError:
                break

        return messages


def to_text(cmd: bytes):
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in cmd])


reader = csv.DictReader(sys.stdin)

output_header = [
    "id", "dir", "is_known", "group", "is_reply", "command", "message"
]

writer = csv.DictWriter(sys.stdout, fieldnames=output_header)
writer.writeheader()

phone_to_radio = GaiaFrameStream()
radio_to_phone = GaiaFrameStream()

for snoop_frame in reader:
    if snoop_frame["id"] == "NEW_BTSNOOP":
        writer.writerow({
            "id": "NEW_BTSNOOP"
        })
        continue

    data = bytes.fromhex(snoop_frame["data"].replace(":", ""))

    match snoop_frame["dir"]:
        case "phone->radio":
            frames = phone_to_radio.update(data)
        case "radio->phone":
            frames = radio_to_phone.update(data)
        case _:
            raise ValueError(f"Unknown direction: {snoop_frame['dir']}")

    for frame in frames:
        writer.writerow({
            "id": snoop_frame["id"],
            "dir": snoop_frame["dir"],
            "is_known": True,
            "group": frame.data.command_group.name,
            "is_reply": frame.data.is_reply,
            "command": frame.data.command.name,
            "message": str(frame.data.body)
        })
