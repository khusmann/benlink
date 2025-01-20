from __future__ import annotations
import typing as t
from enum import IntEnum
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_list
from .common import ReplyStatus


class PFActionType(IntEnum):
    INVALID = 0
    SHORT = 1
    LONG = 2
    VERY_LONG = 3
    DOUBLE = 4
    REPEAT = 5
    LOW_TO_HIGH = 6
    HIGH_TO_LOW = 7
    SHORT_SINGLE = 8
    LONG_RELEASE = 9
    VERY_LONG_RELEASE = 10
    VERY_VERY_LONG = 11
    VERY_VERY_LONG_RELEASE = 12
    TRIPLE = 13


class PFEffectType(IntEnum):
    DISABLE = 0
    ALARM = 1
    ALARM_AND_MUTE = 2
    TOGGLE_OFFLINE = 3
    TOGGLE_RADIO_TX = 4
    TOGGLE_TX_POWER = 5
    TOGGLE_FM = 6
    PREV_CHANNEL = 7
    NEXT_CHANNEL = 8
    T_CALL = 9
    PREV_REGION = 10
    NEXT_REGION = 11
    TOGGLE_CH_SCAN = 12
    MAIN_PTT = 13
    SUB_PTT = 14
    TOGGLE_MONITOR = 15
    BT_PAIRING = 16
    TOGGLE_DOUBLE_CH = 17
    TOGGLE_AB_CH = 18
    SEND_LOCATION = 19
    ONE_CLICK_LINK = 20
    VOL_DOWN = 21
    VOL_UP = 22
    TOGGLE_MUTE = 23


class PF(Bitfield):
    button_id: int = bf_int(4)
    action: PFActionType = bf_int_enum(PFActionType, 4)
    effect: PFEffectType = bf_int_enum(PFEffectType, 8)


class GetPFBody(Bitfield):
    pass


class GetPFReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    pf: t.List[PF] = bf_list(PF, 8)
