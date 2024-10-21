#!/bin/env python3
from __future__ import annotations
import csv
import sys
import typing as t
from dataclasses import dataclass


class HeaderDecodeError(ValueError):
    def __init__(self, message: str, header: bytes):
        super().__init__(message)
        self.header = header


class BodyDecodeError(ValueError):
    def __init__(self, message_type_str: str, message: str, body: bytes):
        super().__init__(message)
        self.type_str = message_type_str
        self.body = body


@dataclass(frozen=True)
class UnknownMessage:
    data: bytes
    message_type_id: t.Tuple[int, int]

    message_type_str: t.ClassVar[t.Final] = "unknown"

    @staticmethod
    def from_message_body(body: bytes, message_type_id: t.Tuple[int, int]) -> UnknownMessage:
        return UnknownMessage(
            data=body,
            message_type_id=message_type_id,
        )

    def to_message_body(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetSignalingSettingsRequest:
    data: bytes

    message_type_str: t.ClassVar[t.Final] = "get_signaling_settings_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x21)

    @staticmethod
    def from_message_body(body: bytes) -> GetSignalingSettingsRequest:
        return GetSignalingSettingsRequest(data=body)

    def to_message_body(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetSignalingSettingsResponse:
    data: bytes

    message_type_str: t.ClassVar[t.Final] = "get_signaling_settings_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x21)

    @staticmethod
    def from_message_body(body: bytes) -> GetSignalingSettingsResponse:
        return GetSignalingSettingsResponse(data=body)

    def to_message_body(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetGPSPositionRequest:
    data: bytes

    message_type_str: t.ClassVar[t.Final] = "set_gps_position_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x20)

    @staticmethod
    def from_message_body(body: bytes) -> SetGPSPositionRequest:
        return SetGPSPositionRequest(data=body)

    def to_message_body(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetGPSPositionResponse:

    message_type_str: t.ClassVar[t.Final] = "set_gps_position_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x20)

    @staticmethod
    def from_message_body(body: bytes) -> SetGPSPositionResponse:
        if len(body) != 1:
            raise BodyDecodeError(
                "set_gps_position_response",
                f"Expected body length 1, got {len(body)}",
                body
            )

        if body[0] != 0x00:
            raise BodyDecodeError(
                "set_gps_position_response",
                f"Expected body[0] = 0x00, got {body[0]}",
                body
            )

        return SetGPSPositionResponse()

    def to_message_body(self) -> bytes:
        return bytes([0x00])


@dataclass(frozen=True)
class GetChannelGroupRequest:
    group_id: int

    message_type_str: t.ClassVar[t.Final] = "get_channel_group_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x49)

    @staticmethod
    def from_message_body(body: bytes) -> GetChannelGroupRequest:
        if len(body) != 1:
            raise BodyDecodeError(
                "get_channel_group_request",
                f"Expected body length 1, got {len(body)}",
                body
            )
        return GetChannelGroupRequest(group_id=body[0])

    def to_message_body(self) -> bytes:
        return bytes([self.group_id])


@dataclass(frozen=True)
class GetChannelGroupResponse:
    group_id: int
    group_name: str

    message_type_str: t.ClassVar[t.Final] = "get_channel_group_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x49)

    @staticmethod
    def from_message_body(body: bytes) -> GetChannelGroupResponse:
        if len(body) < 2:
            raise BodyDecodeError(
                "get_channel_group_response",
                f"Expected body length 2, got {len(body)}",
                body
            )
        (
            reserved_1,
            group_id,
            *group_name_bytes
        ) = body

        if reserved_1 != 0x00:
            raise BodyDecodeError(
                "get_channel_group_response",
                f"Expected reserved_1 = 0x00, got {reserved_1}",
                body
            )

        group_name = bytes(group_name_bytes).decode("utf-8")

        return GetChannelGroupResponse(
            group_id=group_id,
            group_name=group_name,
        )

    def to_message_body(self) -> bytes:
        return bytes([0x00, self.group_id]) + self.group_name.encode("utf-8")


@dataclass(frozen=True)
class GetActiveChannelRequest:

    message_type_str: t.ClassVar[t.Final] = "get_active_channel_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x16)

    @staticmethod
    def from_message_body(body: bytes) -> GetActiveChannelRequest:
        if len(body) != 0:
            raise BodyDecodeError(
                "get_active_channel_request",
                f"Expected body length 0, got {len(body)}",
                body
            )
        return GetActiveChannelRequest()

    def to_message_body(self) -> bytes:
        return b""


@dataclass(frozen=True)
class GetActiveChannelResponse:
    channel_id: int
    unknown_1: int
    unknown_2: int

    message_type_str: t.ClassVar[t.Final] = "get_active_channel_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x16)

    @staticmethod
    def from_message_body(body: bytes) -> GetActiveChannelResponse:
        if len(body) != 3:
            raise BodyDecodeError(
                "get_active_channel_response",
                f"Expected body length 3, got {len(body)}",
                body
            )

        (
            unknown_1,
            unknown_2,
            channel_id,
        ) = body

        return GetActiveChannelResponse(
            channel_id=channel_id,
            unknown_1=unknown_1,
            unknown_2=unknown_2,
        )

    def to_message_body(self) -> bytes:
        return bytes([0x00, 0x00, self.channel_id])


@dataclass(frozen=True)
class GetSettingsRequest:

    message_type_str: t.ClassVar[t.Final] = "get_settings_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x0A)

    @staticmethod
    def from_message_body(body: bytes) -> GetSettingsRequest:
        if len(body) != 0:
            raise BodyDecodeError(
                "get_radio_settings_request",
                f"Expected body length 0, got {len(body)}",
                body
            )
        return GetSettingsRequest()

    def to_message_body(self) -> bytes:
        return b""


@dataclass(frozen=True)
class GetSettingsResponse:
    settings: bytes
    squelch: int

    message_type_str: t.ClassVar[t.Final] = "get_settings_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x0A)

    @staticmethod
    def from_message_body(body: bytes) -> GetSettingsResponse:
        if len(body) < 20:
            raise BodyDecodeError(
                "get_radio_settings_response",
                f"Expected body length 20, got {len(body)}",
                body
            )
        squelch = body[1]
        return GetSettingsResponse(settings=body, squelch=squelch)

    def to_message_body(self) -> bytes:
        return self.settings


@dataclass(frozen=True)
class SetSettingsRequest:
    settings: bytes
    squelch: int

    message_type_str: t.ClassVar[t.Final] = "set_settings_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x0B)

    @staticmethod
    def from_message_body(body: bytes) -> SetSettingsRequest:
        if len(body) < 20:
            raise BodyDecodeError(
                "set_radio_settings_request",
                f"Expected body length 20, got {len(body)}",
                body
            )
        squelch = body[1]
        return SetSettingsRequest(settings=body, squelch=squelch)

    def to_message_body(self) -> bytes:
        return self.settings


@dataclass(frozen=True)
class SetSettingsResponse:
    status_id: int

    message_type_str: t.ClassVar[t.Final] = "set_settings_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x0B)

    @staticmethod
    def from_message_body(body: bytes) -> SetSettingsResponse:
        if len(body) != 1:
            raise BodyDecodeError(
                "set_radio_settings_response",
                f"Expected body length 1, got {len(body)}",
                body
            )
        return SetSettingsResponse(body[0])

    def to_message_body(self) -> bytes:
        return bytes([self.status_id])


@dataclass(frozen=True)
class SetVolumeRequest:
    volume: int

    message_type_str: t.ClassVar[t.Final] = "set_volume_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x17)

    @staticmethod
    def from_message_body(body: bytes) -> SetVolumeRequest:
        if len(body) != 1:
            raise BodyDecodeError(
                "set_volume_request",
                f"Expected body length 1, got {len(body)}",
                body
            )
        return SetVolumeRequest(body[0])

    def to_message_body(self) -> bytes:
        return bytes([self.volume])


@dataclass(frozen=True)
class SetVolumeResponse:
    volume: int

    message_type_str: t.ClassVar[t.Final] = "set_volume_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x17)

    @staticmethod
    def from_message_body(body: bytes) -> SetVolumeResponse:
        if len(body) < 1:
            raise BodyDecodeError(
                "set_volume_response",
                f"Expected body length 1, got {len(body)}",
                body
            )

        return SetVolumeResponse(
            volume=body[0],
        )

    def to_message_body(self) -> bytes:
        return bytes([self.volume])


@dataclass(frozen=True)
class SetDigitalMessageUpdates:
    enabled: bool

    message_type_str: t.ClassVar[t.Final] = "set_digital_message_updates"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x06)

    @staticmethod
    def from_message_body(body: bytes) -> SetDigitalMessageUpdates:
        if len(body) != 1:
            raise BodyDecodeError(
                "set_digital_message_updates",
                f"Expected body length 1, got {len(body)}",
                body
            )
        if body[0] not in (0x00, 0x01):
            raise BodyDecodeError(
                "set_messaging_reports",
                f"Expected body[0] to be 0x00 or 0x01, got {body[0]}",
                body
            )
        return SetDigitalMessageUpdates(enabled=body[0] == 0x01)

    def to_message_body(self) -> bytes:
        return bytes([0x01 if self.enabled else 0x00])


@dataclass(frozen=True)
class ChannelInfoRequest:
    channel_id: int

    message_type_str: t.ClassVar[t.Final] = "channel_info_request"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x0D)

    @staticmethod
    def from_message_body(body: bytes) -> ChannelInfoRequest:
        if len(body) != 1:
            raise BodyDecodeError(
                "channel_info_request",
                f"Expected body length 1, got {len(body)}",
                body
            )
        return ChannelInfoRequest(channel_id=body[0])

    def to_message_body(self) -> bytes:
        return bytes([self.channel_id])


@dataclass(frozen=True)
class ChannelInfoResponse:
    action_id: int
    channel_id: int
    channel_data: bytes

    message_type_str: t.ClassVar[t.Final] = "channel_info_response"
    message_type_id: t.ClassVar[t.Final] = (0x80, 0x0D)

    @staticmethod
    def from_message_body(body: bytes) -> ChannelInfoResponse:
        if len(body) < 2:
            raise BodyDecodeError(
                "channel_info_response",
                f"Expected least 1 byte, got {len(body)}",
                body
            )
        (
            action_id,
            channel_id,
            *channel_data
        ) = body

        return ChannelInfoResponse(
            action_id=action_id,
            channel_id=channel_id,
            channel_data=bytes(channel_data),
        )

    def to_message_body(self) -> bytes:
        return bytes([0x00, self.channel_id]) + self.channel_data


@dataclass(frozen=True)
class RadioReceivedAprsChunk:
    chunk_data: bytes
    chunk_num: int
    is_final_chunk: bool
    decode_status: t.Literal["ok", "error"]

    message_type_str: t.ClassVar[t.Final] = "radio_received_aprs_chunk"
    message_type_id: t.ClassVar[t.Final] = (0x00, 0x09)

    @staticmethod
    def from_message_body(body: bytes) -> RadioReceivedAprsChunk:
        if len(body) < 2:
            raise BodyDecodeError(
                "radio_received_aprs_chunk",
                f"Expected least 2 bytes, got {len(body)}",
                body
            )

        aprs_header = body[:2]
        aprs_body = body[2:]

        (
            decode_status_id,
            chunk_info,
        ) = aprs_header

        match decode_status_id:
            case 0x01:
                decode_status = "error"
            case 0x02:
                decode_status = "ok"
            case _:
                raise BodyDecodeError(
                    "radio_received_aprs_chunk",
                    f"Unknown decode status: {decode_status_id}",
                    body
                )

        is_final_part = chunk_info & 0x80 == 0x80

        chunk_num = chunk_info & 0x7f

        return RadioReceivedAprsChunk(
            chunk_data=aprs_body,
            chunk_num=chunk_num,
            decode_status=decode_status,
            is_final_chunk=is_final_part,
        )

    def to_message_body(self) -> bytes:
        chunk_info = self.chunk_num | (0x80 if self.is_final_chunk else 0x00)
        match self.decode_status:
            case "error":
                decode_status_id = 0x01
            case "ok":
                decode_status_id = 0x02
        return bytes([decode_status_id, chunk_info]) + self.chunk_data


KnownHTMessage = t.Union[
    RadioReceivedAprsChunk,
    ChannelInfoRequest,
    ChannelInfoResponse,
    SetDigitalMessageUpdates,
    SetSettingsRequest,
    SetSettingsResponse,
    GetSettingsRequest,
    GetSettingsResponse,
    GetActiveChannelRequest,
    GetActiveChannelResponse,
    SetGPSPositionRequest,
    SetGPSPositionResponse,
    SetVolumeRequest,
    SetVolumeResponse,
    GetChannelGroupRequest,
    GetChannelGroupResponse,
    GetSignalingSettingsRequest,
    GetSignalingSettingsResponse,
]

HTMessage = KnownHTMessage | UnknownMessage

ALL_HT_MESSAGE_TYPES: t.Tuple[t.Type[KnownHTMessage], ...] = tuple(
    t.get_args(KnownHTMessage)
)


def encode_ht_message(msg: HTMessage) -> bytes:
    body = msg.to_message_body()

    header = bytes([
        0xff,  # start_flag
        0x01,  # constant_1
        0x00,  # reserved_1
        len(body),  # message_length
        0x00,  # reserved_2
        0x02,  # constant_2
        *msg.message_type_id,  # message_type_id
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
        message_type_id_1,
        message_type_id_2,
    ) = header

    message_type_id = (message_type_id_1, message_type_id_2)

    if start_flag != 0xff:
        raise HeaderDecodeError(
            f"Expected byte[0](start_flag) = 0xff, got {start_flag}", buffer
        )

    if constant_1 != 0x01:
        raise HeaderDecodeError(
            f"Expected byte[1](constant_1) = 0x01, got {constant_1}", buffer
        )

    if reserved_1 != 0x00:
        raise HeaderDecodeError(
            f"Expected byte[2](reserved_1) = 0x00, got {reserved_1}", buffer
        )

    if reserved_2 != 0x00:
        raise HeaderDecodeError(
            f"Expected byte[4](reserved_2) = 0x00, got {reserved_2}", buffer
        )

    if constant_2 != 0x02:
        raise HeaderDecodeError(
            f"Expected byte[5](constant_2) = 0x02, got {constant_2}", buffer
        )

    if body_length > len(buffer):
        return (None, buffer)

    body = buffer[:body_length]
    buffer = buffer[body_length:]

    for message_type in ALL_HT_MESSAGE_TYPES:
        if message_type_id == message_type.message_type_id:
            return (message_type.from_message_body(body), buffer)

    return (UnknownMessage.from_message_body(body, message_type_id), buffer)


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
