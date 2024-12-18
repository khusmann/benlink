from __future__ import annotations
from ..bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_map, Scale
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class ReadStatusType(IntEnum):
    UNKNOWN = 0
    BATTERY_LEVEL = 1
    BATTERY_VOLTAGE = 2
    RC_BATTERY_LEVEL = 3
    BATTERY_LEVEL_AS_PERCENTAGE = 4


class ReadStatusBody(Bitfield):
    status_type: ReadStatusType = bf_int_enum(ReadStatusType, 16)


class ReadStatusVoltage(Bitfield):
    voltage: float = bf_map(bf_int(16), Scale(1 / 1000, 3))


class ReadStatusBatteryLevel(Bitfield):
    level: int = bf_int(8)


class ReadStatusBatteryLevelPercentage(Bitfield):
    percentage: int = bf_int(8)


class ReadStatusRCBatteryLevel(Bitfield):
    level: int = bf_int(8)


RadioStatus = t.Union[
    ReadStatusVoltage,
    ReadStatusBatteryLevel,
    ReadStatusBatteryLevelPercentage,
    ReadStatusRCBatteryLevel,
]


def radio_status_disc(m: ReadStatusBody):
    match m.status_type:
        case ReadStatusType.BATTERY_VOLTAGE:
            return ReadStatusVoltage
        case ReadStatusType.BATTERY_LEVEL:
            return ReadStatusBatteryLevel
        case ReadStatusType.BATTERY_LEVEL_AS_PERCENTAGE:
            return ReadStatusBatteryLevelPercentage
        case ReadStatusType.RC_BATTERY_LEVEL:
            return ReadStatusRCBatteryLevel
        case ReadStatusType.UNKNOWN:
            raise ValueError("Unknown radio status type")


class ReadStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    status_type: ReadStatusType = bf_int_enum(ReadStatusType, 16)
    value: RadioStatus = bf_dyn(radio_status_disc)
