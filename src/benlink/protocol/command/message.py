from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_dyn, bf_bitfield, bf_bool, bf_bytes
import typing as t
import sys
from enum import IntEnum

from .dev_info import GetDevInfoBody, GetDevInfoReplyBody
from .notification import EventNotificationBody, RegisterNotificationBody
from .settings import (
    ReadSettingsBody,
    ReadSettingsReplyBody,
    WriteSettingsBody,
    WriteSettingsReplyBody,
)
from .power_status import ReadPowerStatusBody, ReadPowerStatusReplyBody
from .rf_ch import (
    ReadRFChBody,
    ReadRFChReplyBody,
    WriteRFChBody,
    WriteRFChReplyBody,
)
from .pf import GetPFBody, GetPFReplyBody
from .ht_send_data import HTSendDataBody, HTSendDataReplyBody
from .bss_settings import (
    ReadBSSSettingsBody,
    ReadBSSSettingsReplyBody,
    WriteBSSSettingsBody,
    WriteBSSSettingsReplyBody,
)
from .phone_status import SetPhoneStatusBody, SetPhoneStatusReplyBody
from .status import GetHtStatusBody, GetHtStatusReplyBody


class CommandGroup(IntEnum):
    BASIC = 2
    EXTENDED = 10


class ExtendedCommand(IntEnum):
    UNKNOWN = 0
    GET_BT_SIGNAL = 769
    UNKNOWN_01 = 1600
    UNKNOWN_02 = 1601
    UNKNOWN_03 = 1602
    UNKNOWN_04 = 16385
    UNKNOWN_05 = 16386
    GET_DEV_STATE_VAR = 16387
    DEV_REGISTRATION = 1825

    @classmethod
    def _missing_(cls, value: object):
        print(f"Unknown value for {cls.__name__}: {value}", file=sys.stderr)
        return cls.UNKNOWN


class BasicCommand(IntEnum):
    UNKNOWN = 0
    GET_DEV_ID = 1
    SET_REG_TIMES = 2
    GET_REG_TIMES = 3
    GET_DEV_INFO = 4
    READ_STATUS = 5
    REGISTER_NOTIFICATION = 6
    CANCEL_NOTIFICATION = 7
    GET_NOTIFICATION = 8
    EVENT_NOTIFICATION = 9
    READ_SETTINGS = 10
    WRITE_SETTINGS = 11
    STORE_SETTINGS = 12
    READ_RF_CH = 13
    WRITE_RF_CH = 14
    GET_IN_SCAN = 15
    SET_IN_SCAN = 16
    SET_REMOTE_DEVICE_ADDR = 17
    GET_TRUSTED_DEVICE = 18
    DEL_TRUSTED_DEVICE = 19
    GET_HT_STATUS = 20
    SET_HT_ON_OFF = 21
    GET_VOLUME = 22
    SET_VOLUME = 23
    RADIO_GET_STATUS = 24
    RADIO_SET_MODE = 25
    RADIO_SEEK_UP = 26
    RADIO_SEEK_DOWN = 27
    RADIO_SET_FREQ = 28
    READ_ADVANCED_SETTINGS = 29
    WRITE_ADVANCED_SETTINGS = 30
    HT_SEND_DATA = 31
    SET_POSITION = 32
    READ_BSS_SETTINGS = 33
    WRITE_BSS_SETTINGS = 34
    FREQ_MODE_SET_PAR = 35
    FREQ_MODE_GET_STATUS = 36
    READ_RDA1846S_AGC = 37
    WRITE_RDA1846S_AGC = 38
    READ_FREQ_RANGE = 39
    WRITE_DE_EMPH_COEFFS = 40
    STOP_RINGING = 41
    SET_TX_TIME_LIMIT = 42
    SET_IS_DIGITAL_SIGNAL = 43
    SET_HL = 44
    SET_DID = 45
    SET_IBA = 46
    GET_IBA = 47
    SET_TRUSTED_DEVICE_NAME = 48
    SET_VOC = 49
    GET_VOC = 50
    SET_PHONE_STATUS = 51
    READ_RF_STATUS = 52
    PLAY_TONE = 53
    GET_DID = 54
    GET_PF = 55
    SET_PF = 56
    RX_DATA = 57
    WRITE_REGION_CH = 58
    WRITE_REGION_NAME = 59
    SET_REGION = 60
    SET_PP_ID = 61
    GET_PP_ID = 62
    READ_ADVANCED_SETTINGS2 = 63
    WRITE_ADVANCED_SETTINGS2 = 64
    UNLOCK = 65
    DO_PROG_FUNC = 66
    SET_MSG = 67
    GET_MSG = 68
    BLE_CONN_PARAM = 69
    SET_TIME = 70
    SET_APRS_PATH = 71
    GET_APRS_PATH = 72
    READ_REGION_NAME = 73
    SET_DEV_ID = 74
    GET_PF_ACTIONS = 75


def frame_type_disc(m: Message):
    match m.command_group:
        case CommandGroup.BASIC:
            return bf_int_enum(BasicCommand, 15)
        case CommandGroup.EXTENDED:
            return bf_int_enum(ExtendedCommand, 15)


def body_disc(m: Message, n: int):
    assert n % 8 == 0
    match m.command_group:
        case CommandGroup.BASIC:
            match m.command:
                case BasicCommand.GET_DEV_INFO:
                    out = GetDevInfoReplyBody if m.is_reply else GetDevInfoBody
                case BasicCommand.READ_STATUS:
                    out = ReadPowerStatusReplyBody if m.is_reply else ReadPowerStatusBody
                case BasicCommand.READ_RF_CH:
                    out = ReadRFChReplyBody if m.is_reply else ReadRFChBody
                case BasicCommand.WRITE_RF_CH:
                    out = WriteRFChReplyBody if m.is_reply else WriteRFChBody
                case BasicCommand.READ_SETTINGS:
                    out = ReadSettingsReplyBody if m.is_reply else ReadSettingsBody
                case BasicCommand.WRITE_SETTINGS:
                    out = WriteSettingsReplyBody if m.is_reply else WriteSettingsBody
                case BasicCommand.GET_PF:
                    out = GetPFReplyBody if m.is_reply else GetPFBody
                case BasicCommand.READ_BSS_SETTINGS:
                    out = ReadBSSSettingsReplyBody if m.is_reply else ReadBSSSettingsBody
                case BasicCommand.WRITE_BSS_SETTINGS:
                    out = WriteBSSSettingsReplyBody if m.is_reply else WriteBSSSettingsBody
                case BasicCommand.EVENT_NOTIFICATION:
                    if m.is_reply:
                        raise ValueError("EventNotification cannot be a reply")
                    out = EventNotificationBody
                case BasicCommand.REGISTER_NOTIFICATION:
                    if m.is_reply:
                        raise ValueError(
                            "RegisterNotification cannot be a reply"
                        )
                    out = RegisterNotificationBody
                case BasicCommand.HT_SEND_DATA:
                    out = HTSendDataReplyBody if m.is_reply else HTSendDataBody
                case BasicCommand.SET_PHONE_STATUS:
                    out = SetPhoneStatusReplyBody if m.is_reply else SetPhoneStatusBody
                case BasicCommand.GET_HT_STATUS:
                    out = GetHtStatusReplyBody if m.is_reply else GetHtStatusBody
                case _:
                    return bf_bytes(n // 8)
        case CommandGroup.EXTENDED:
            match m.command:
                case _:
                    return bf_bytes(n // 8)

    return bf_bitfield(out, n)


MessageBody = t.Union[
    GetDevInfoBody,
    GetDevInfoReplyBody,
    ReadPowerStatusBody,
    ReadPowerStatusReplyBody,
    ReadRFChBody,
    ReadRFChReplyBody,
    WriteRFChBody,
    WriteRFChReplyBody,
    ReadSettingsBody,
    ReadSettingsReplyBody,
    WriteSettingsBody,
    WriteSettingsReplyBody,
    GetPFBody,
    GetPFReplyBody,
    ReadBSSSettingsBody,
    ReadBSSSettingsReplyBody,
    WriteBSSSettingsBody,
    WriteBSSSettingsReplyBody,
    EventNotificationBody,
    HTSendDataBody,
    HTSendDataReplyBody,
    RegisterNotificationBody,
    SetPhoneStatusBody,
    SetPhoneStatusReplyBody,
    GetHtStatusBody,
    GetHtStatusReplyBody,
]


class Message(Bitfield):
    command_group: CommandGroup = bf_int_enum(CommandGroup, 16)
    is_reply: bool = bf_bool()
    command: BasicCommand | ExtendedCommand = bf_dyn(frame_type_disc)
    body: MessageBody | bytes = bf_dyn(body_disc)
