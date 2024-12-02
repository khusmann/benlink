#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t

from messageframeOld import MessageFrame
from packedbits import BitStreamOld


class MessageStream:
    _stream: BitStreamOld

    def __init__(self):
        self._stream = BitStreamOld()

    def update(self, data: bytes) -> t.List[MessageFrame]:
        self._stream.extend_bytes(data)

        messages: t.List[MessageFrame] = []

        while self._stream.remaining():
            if self._stream.peek_bytes(1) != b"\xff":
                print("Warning: skipping unknown data", file=sys.stderr)
                while self._stream.remaining() and self._stream.peek_bytes(1) != b"\xff":
                    self._stream.read_bytes(1)

            pos = self._stream.tell()
            try:
                messages.append(MessageFrame.from_bitstream(self._stream))
            except EOFError:
                self._stream.seek(pos)
                break

        self._stream.rebase()
        return messages


def to_text(cmd: bytes):
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in cmd])


reader = csv.DictReader(sys.stdin)

output_header = [
    "id", "dir", "is_known", "group", "is_reply", "command", "message"
]

writer = csv.DictWriter(sys.stdout, fieldnames=output_header)
writer.writeheader()

phone_to_radio = MessageStream()
radio_to_phone = MessageStream()

for frame in reader:
    if frame["id"] == "NEW_BTSNOOP":
        writer.writerow({
            "id": "NEW_BTSNOOP"
        })
        continue

    data = bytes.fromhex(frame["data"].replace(":", ""))

    match frame["dir"]:
        case "phone->radio":
            messages = phone_to_radio.update(data)
        case "radio->phone":
            messages = radio_to_phone.update(data)
        case _:
            raise ValueError(f"Unknown direction: {frame['dir']}")

    for message in messages:
        writer.writerow({
            "id": frame["id"],
            "dir": frame["dir"],
            "is_known": True,
            "group": message.type_group.name,
            "is_reply": message.is_reply,
            "command": message.type.name,
            "message": str(message.body)
        })
