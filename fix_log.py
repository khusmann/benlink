#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t

from htmessage import ByteStream, UnknownMessage, read_next_message, Message


class MessageStream:
    _stream: ByteStream

    def __init__(self):
        self._stream = ByteStream(b"")

    def feed(self, data: bytes) -> t.List[Message | UnknownMessage]:
        self._stream.append(data)

        messages: t.List[Message | UnknownMessage] = []

        while True:
            message = read_next_message(self._stream)
            if message is None:
                break
            messages.append(message)

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
            messages = phone_to_radio.feed(data)
        case "radio->phone":
            messages = radio_to_phone.feed(data)
        case _:
            raise ValueError(f"Unknown direction: {frame['dir']}")

    for message in messages:
        writer.writerow({
            "id": frame["id"],
            "dir": frame["dir"],
            "is_known": not isinstance(message, UnknownMessage),
            "group": message.tid.group,
            "is_reply": message.tid.is_reply,
            "command": message.tid.command,
            "message": str(message)
        })
