#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t

from htmessage import HTMessage, decode_ht_message


class HTMessageStream:
    _buffer: bytes

    def __init__(self):
        self._buffer = b""

    def feed(self, data: bytes) -> t.List[HTMessage]:
        self._buffer += data

        messages: t.List[HTMessage] = []

        while len(self._buffer) >= 8:
            if self._buffer[0] != 0xff:
                print(
                    f"Expected buffer[0] = 0xff, got {self._buffer}",
                    file=sys.stderr
                )
                idx = self._buffer.find(b"\xff")
                if idx == -1:
                    self._buffer = b""
                else:
                    self._buffer = self._buffer[idx:]
                continue

            msg, self._buffer = decode_ht_message(self._buffer)

            if msg is None:
                break

            messages.append(msg)

        return messages


def to_text(cmd: bytes):
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in cmd])


reader = csv.DictReader(sys.stdin)

output_header = ["id", "dir", "message_type_id", "message_type_str", "message"]

writer = csv.DictWriter(sys.stdout, fieldnames=output_header)
writer.writeheader()

phone_to_radio = HTMessageStream()
radio_to_phone = HTMessageStream()

for frame in reader:
    if frame["id"] == "NEW_BTSNOOP":
        writer.writerow({
            "id": "NEW_BTSNOOP"
        })
        continue
    data = bytes.fromhex(frame["data"].replace(":", ""))

    try:
        match frame["dir"]:
            case "phone->radio":
                messages = phone_to_radio.feed(data)
            case "radio->phone":
                messages = radio_to_phone.feed(data)
            case _:
                raise ValueError(f"Unknown direction: {frame['dir']}")
    except ValueError as e:
        print(data, file=sys.stderr)
        print(f"Error processing frame {frame['id']}: {e}", file=sys.stderr)
        break

    for message in messages:
        writer.writerow({
            "id": frame["id"],
            "dir": frame["dir"],
            "message_type_id": ", ".join(hex(i) for i in message.message_type_id),
            "message_type_str": message.message_type_str,
            "message": str(message)
        })
