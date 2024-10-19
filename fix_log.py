#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t


class HTMessageUnknown(t.NamedTuple):
    message_type_id: int
    data: bytes
    is_reply: bool

    def type_str(self) -> str:
        return f"unknown ({self.message_type_id})"

    @staticmethod
    def from_message_body(body: bytes, message_type_id: int, is_reply: bool) -> HTMessageUnknown:
        return HTMessageUnknown(
            message_type_id=message_type_id,
            data=body,
            is_reply=is_reply,
        )

    def to_message_body(self) -> bytes:
        return self.data


class HTMessageAprsChunk(t.NamedTuple):
    chunk_data: bytes
    chunk_num: int
    is_final_chunk: bool
    decode_status: t.Literal["ok", "error"]
    is_reply: bool

    def type_str(self) -> str:
        return "aprs_chunk"

    @staticmethod
    def from_message_body(body: bytes, is_reply: bool) -> HTMessageAprsChunk:
        if len(body) < 2:
            raise ValueError(
                f"Expected aprs chunk least 2 bytes, got {len(body)}. Frame body: {body}"
            )

        aprs_header = body[:2]
        aprs_body = body[2:]

        (
            decode_status_id,
            part_info,
        ) = aprs_header

        match decode_status_id:
            case 0x01:
                decode_status = "error"
            case 0x02:
                decode_status = "ok"
            case _:
                raise ValueError(
                    f"Unknown decode status: {decode_status_id}. Frame body: {body}"
                )

        is_final_part = part_info & 0x80 == 0x80

        chunk_num = part_info & 0x7f

        return HTMessageAprsChunk(
            chunk_data=aprs_body,
            chunk_num=chunk_num,
            decode_status=decode_status,
            is_final_chunk=is_final_part,
            is_reply=is_reply,
        )

    def to_message_body(self) -> bytes:
        part_info = self.chunk_num | (0x80 if self.is_final_chunk else 0x00)
        return bytes([0x02, part_info]) + self.chunk_data


HTMessage = HTMessageAprsChunk | HTMessageUnknown


def encode_ht_message(msg: HTMessage) -> bytes:
    body = msg.to_message_body()

    header = bytes([
        0xff,  # start_flag
        0x01,  # constant_1
        0x00,  # reserved_1
        len(body),  # message_length
        0x00,  # reserved_2
        0x02,  # constant_2
        0x80 if msg.is_reply else 0x00,  # reply_flag
        0x09,  # message_type
    ])

    return header + body


def decode_ht_message(buffer: bytes) -> t.Tuple[HTMessage | None, bytes]:
    if len(buffer) < 8:
        return (None, buffer)

    header = buffer[:8]
    buffer = buffer[8:]

    (
        start_flag,
        constant_1,
        reserved_1,
        body_length,
        reserved_2,
        constant_2,
        reply_flag,
        message_type_id,
    ) = header

    if start_flag != 0xff:
        raise ValueError(
            f"Expected header byte[0](start_flag) = 0xff, got {start_flag}. Buffer: {buffer}"
        )

    if constant_1 != 0x01:
        raise ValueError(
            f"Expected header byte[1](constant_1) = 0x01, got {constant_1}. Buffer: {buffer}"
        )

    if reserved_1 != 0x00:
        raise ValueError(
            f"Expected header byte[2](reserved_1) = 0x00, got {reserved_1}. Buffer: {buffer}"
        )

    if reserved_2 != 0x00:
        raise ValueError(
            f"Expected header byte[4](reserved_2) = 0x00, got {reserved_2}. Buffer: {buffer}"
        )

    if constant_2 != 0x02:
        raise ValueError(
            f"Expected header byte[5](constant_2) = 0x02, got {constant_2}. Buffer: {buffer}"
        )

    if not (reply_flag == 0x00 or reply_flag == 0x80):
        raise ValueError(
            f"Expected header byte[6](reply_flag) = 0x00 or 0x80, got {reply_flag}. Buffer: {buffer}"
        )

    is_reply = reply_flag == 0x80

    if body_length > len(buffer):
        return (None, buffer)

    body = buffer[:body_length]
    buffer = buffer[body_length:]

    match message_type_id:
        case 0x09:
            return (
                HTMessageAprsChunk.from_message_body(body, is_reply),
                buffer
            )
        case _:
            return (
                HTMessageUnknown.from_message_body(
                    body, message_type_id, is_reply
                ),
                buffer
            )


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

output_header = ["id", "dir", "msg_type", "msg"]

writer = csv.DictWriter(sys.stdout, fieldnames=output_header)
writer.writeheader()

phone_to_radio = HTMessageStream()
radio_to_phone = HTMessageStream()

for frame in reader:
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
            "msg_type": message.type_str(),
            "msg": str(message)
        })
