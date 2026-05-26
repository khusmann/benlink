from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_dyn, bf_int, bf_map
from .common import ReplyStatus
from datetime import datetime, timezone


class TimeMapper:
    def forward(self, x: int) -> datetime:
        return datetime.fromtimestamp(x, tz=timezone.utc)

    def back(self, y: datetime) -> int:
        # If naive datetime, treat as UTC
        if y.tzinfo is None:
            y = y.replace(tzinfo=timezone.utc)
        return int(y.timestamp())


class SignedMapper:
    def __init__(self, bits: int):
        self.bits = bits
        self.max_unsigned = 2 ** bits
        self.max_signed = 2 ** (bits - 1)

    def forward(self, x: int) -> int:
        if x >= self.max_signed:
            return x - self.max_unsigned
        return x

    def back(self, y: int) -> int:
        if y < 0:
            return y + self.max_unsigned
        return y


class DegreesMapper:
    def forward(self, x: int) -> float:
        return x / 60 / 500

    def back(self, y: float) -> int:
        return int(y * 60 * 500)


class OptionalMapper:
    def __init__(self, magic: int):
        self.magic = magic

    def forward(self, x: int) -> int | None:
        return x if x != self.magic else None

    def back(self, y: int | None) -> int:
        return y if y is not None else self.magic


class Position(Bitfield):
    # Note:
    # Firmware < 49 only has Lat and Lon (6 bytes)
    # Firmware < 133 only has Lat, Lon, Alt, Speed, Hdg, and Time (16 bytes)
    latitude: float = bf_map(
        bf_map(bf_int(24), SignedMapper(24)), DegreesMapper()
    )
    longitude: float = bf_map(
        bf_map(bf_int(24), SignedMapper(24)), DegreesMapper()
    )
    altitude: int | None = bf_map(  # meters?
        bf_map(bf_int(16), SignedMapper(24)), OptionalMapper(-32768)
    )
    speed: int | None = bf_map(bf_int(16), OptionalMapper(0xFFFF))  # Km/h?
    heading: int | None = bf_map(  # Degrees?
        bf_int(16), OptionalMapper(0xFFFF)
    )
    time: datetime = bf_map(bf_int(32), TimeMapper())
    # See https://developer.android.com/reference/android/location/Location?utm_source=chatgpt.com#getAccuracy()
    accuracy: int = bf_int(16)  # meters?


def position_desc(body: GetPositionReplyBody):
    return Position if body.reply_status == ReplyStatus.SUCCESS else None


class GetPositionReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    position: Position | None = bf_dyn(position_desc)


class GetPositionBody(Bitfield):
    pass
