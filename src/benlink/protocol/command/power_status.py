from __future__ import annotations
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_map, bf_bitfield, Scale
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class PowerStatusType(IntEnum):
    UNKNOWN = 0
    BATTERY_LEVEL = 1
    BATTERY_VOLTAGE = 2
    RC_BATTERY_LEVEL = 3
    BATTERY_LEVEL_AS_PERCENTAGE = 4


class BatteryVoltageStatus(Bitfield):
    battery_voltage: float = bf_map(bf_int(16), Scale(1 / 1000, 3))


class BatteryLevelStatus(Bitfield):
    battery_level: int = bf_int(8)


class BatteryLevelPercentageStatus(Bitfield):
    battery_level_as_percentage: int = bf_int(8)


class RCBatteryLevelStatus(Bitfield):
    rc_battery_level: int = bf_int(8)


StatusValue = t.Union[
    BatteryVoltageStatus,
    BatteryLevelStatus,
    BatteryLevelPercentageStatus,
    RCBatteryLevelStatus,
]


def status_value_desc(m: PowerStatus):
    match m.power_status_type:
        case PowerStatusType.BATTERY_VOLTAGE:
            return BatteryVoltageStatus
        case PowerStatusType.BATTERY_LEVEL:
            return BatteryLevelStatus
        case PowerStatusType.BATTERY_LEVEL_AS_PERCENTAGE:
            return BatteryLevelPercentageStatus
        case PowerStatusType.RC_BATTERY_LEVEL:
            return RCBatteryLevelStatus
        case PowerStatusType.UNKNOWN:
            raise ValueError("Unknown radio status type")


class PowerStatus(Bitfield):
    power_status_type: PowerStatusType = bf_int_enum(
        PowerStatusType, 16)
    value: StatusValue = bf_dyn(status_value_desc)


def power_status_reply_desc(m: ReadPowerStatusReplyBody, n: int):
    if m.reply_status != ReplyStatus.SUCCESS:
        return None

    return bf_bitfield(PowerStatus, n)


class ReadPowerStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    status: PowerStatus | None = bf_dyn(power_status_reply_desc)


class ReadPowerStatusBody(Bitfield):
    status_type: PowerStatusType = bf_int_enum(PowerStatusType, 16)
