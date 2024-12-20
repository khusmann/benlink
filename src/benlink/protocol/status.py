from __future__ import annotations
from ..bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_map, bf_bitfield, Scale
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class ReadStatusType(IntEnum):
    UNKNOWN = 0
    BATTERY_LEVEL = 1
    BATTERY_VOLTAGE = 2
    RC_BATTERY_LEVEL = 3
    BATTERY_LEVEL_AS_PERCENTAGE = 4


class BatteryVoltageStatus(Bitfield):
    voltage: float = bf_map(bf_int(16), Scale(1 / 1000, 3))


class BatteryLevelStatus(Bitfield):
    level: int = bf_int(8)


class BatteryLevelPercentageStatus(Bitfield):
    percentage: int = bf_int(8)


class RCBatteryLevelStatus(Bitfield):
    level: int = bf_int(8)


StatusValue = t.Union[
    BatteryVoltageStatus,
    BatteryLevelStatus,
    BatteryLevelPercentageStatus,
    RCBatteryLevelStatus,
]


def status_value_desc(m: Status):
    match m.status_type:
        case ReadStatusType.BATTERY_VOLTAGE:
            return BatteryVoltageStatus
        case ReadStatusType.BATTERY_LEVEL:
            return BatteryLevelStatus
        case ReadStatusType.BATTERY_LEVEL_AS_PERCENTAGE:
            return BatteryLevelPercentageStatus
        case ReadStatusType.RC_BATTERY_LEVEL:
            return RCBatteryLevelStatus
        case ReadStatusType.UNKNOWN:
            raise ValueError("Unknown radio status type")


class Status(Bitfield):
    status_type: ReadStatusType = bf_int_enum(ReadStatusType, 16)
    value: StatusValue = bf_dyn(status_value_desc)


def status_reply_desc(m: ReadStatusReplyBody, n: int):
    if m.reply_status != ReplyStatus.SUCCESS:
        return None

    return bf_bitfield(Status, n)


class ReadStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    status: Status | None = bf_dyn(status_reply_desc)


class ReadStatusBody(Bitfield):
    status_type: ReadStatusType = bf_int_enum(ReadStatusType, 16)
