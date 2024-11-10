from __future__ import annotations
# from dataclasses import dataclass
from packedbits import PackedBits, bitfield, union_bitfield
import typing as t
from enum import IntEnum, IntFlag


class FrameOptions(IntFlag):
    NONE = 0
    CHECKSUM = 1


class FrameTypeGroup(IntEnum):
    BASIC = 2
    EXTENDED = 10


class FrameTypeExtended(IntEnum):
    GET_BT_SIGNAL = 769
    GET_DEV_STATE_VAR = 16387


class FrameTypeBasic(IntEnum):
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


class DevStateVar(IntEnum):
    START = 0
    RSSI_LOW_THRESHOLD = 1
    RSSI_HIGH_THRESHOLD = 2
    BATTERY_LOW_THRESHOLD = 3
    BATTERY_HIGH_THRESHOLD = 4
    DEVICE_STATE_CHANGED = 5
    PIO_CHANGED = 6
    DEBUG_MESSAGE = 7
    BATTERY_CHARGED = 8
    CHARGER_CONNECTION = 9
    CAPSENSE_UPDATE = 10
    USER_ACTION = 11
    SPEECH_RECOGNITION = 12
    AV_COMMAND = 13
    REMOTE_BATTERY_LEVEL = 14
    KEY = 15
    DFU_STATE = 16
    UART_RECEIVED_DATA = 17
    VMU_PACKET = 18


class ReplyStatus(IntEnum):
    SUCCESS = 0
    NOT_SUPPORTED = 1
    NOT_AUTHENTICATED = 2
    INSUFFICIENT_RESOURCES = 3
    AUTHENTICATING = 4
    INVALID_PARAMETER = 5
    INCORRECT_STATE = 6
    IN_PROGRESS = 7


class RadioStatusType(IntEnum):
    UNKNOWN = 0
    BATTERY_LEVEL = 1
    BATTERY_VOLTAGE = 2
    RC_BATTERY_LEVEL = 3
    BATTERY_LEVEL_AS_PERCENTAGE = 4


class ReadStatusBody(PackedBits):
    status_type: RadioStatusType = bitfield(16)


class RadioStatusVoltage(PackedBits):
    voltage: float = bitfield(16, scale=1000)


class RadioStatusBatteryLevel(PackedBits):
    level: int = bitfield(8)


class RadioStatusBatteryLevelPercentage(PackedBits):
    percentage: int = bitfield(8)


class RadioStatusRCBatteryLevel(PackedBits):
    level: int = bitfield(8)


RadioStatus = t.Union[
    RadioStatusVoltage,
    RadioStatusBatteryLevel,
    RadioStatusBatteryLevelPercentage,
    RadioStatusRCBatteryLevel,
]


def radio_status_disc(m: ReadStatusBody):
    match m.status_type:
        case RadioStatusType.BATTERY_VOLTAGE:
            return RadioStatusVoltage
        case RadioStatusType.BATTERY_LEVEL:
            return RadioStatusBatteryLevel
        case RadioStatusType.BATTERY_LEVEL_AS_PERCENTAGE:
            return RadioStatusBatteryLevelPercentage
        case RadioStatusType.RC_BATTERY_LEVEL:
            return RadioStatusRCBatteryLevel
        case RadioStatusType.UNKNOWN:
            raise ValueError("Unknown radio status type")


class ReadStatusReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    status_type: RadioStatusType = bitfield(16)
    value: RadioStatus = union_bitfield(radio_status_disc)


class DevInfo(PackedBits):
    vendor_id: int = bitfield(8)
    product_id: int = bitfield(16)
    hw_ver: int = bitfield(8)
    soft_ver: int = bitfield(16)
    support_radio: bool = bitfield(1)
    support_medium_power: bool = bitfield(1)
    fixed_loc_speaker_vol: bool = bitfield(1)
    not_support_soft_power_ctrl: bool = bitfield(1)
    have_no_speaker: bool = bitfield(1)
    have_hm_speaker: bool = bitfield(1)
    region_count: int = bitfield(6)
    support_noaa: bool = bitfield(1)
    gmrs: bool = bitfield(1)
    support_vfo: bool = bitfield(1)
    support_dmr: bool = bitfield(1)
    channel_count: int = bitfield(8)
    freq_range_count: int = bitfield(4)
    pad: t.Literal[0] = bitfield(4, default=0)


class GetDevInfoBody(PackedBits):
    unknown: t.Literal[3] = bitfield(8, default=3)


class GetDevInfoReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    info: DevInfo | None = union_bitfield((
        lambda x: DevInfo
        if x.reply_status == ReplyStatus.SUCCESS
        else None
    ))


def frame_type_disc(m: MessageFrame):
    match m.type_group:
        case FrameTypeGroup.BASIC:
            return (FrameTypeBasic, 15)
        case FrameTypeGroup.EXTENDED:
            return (FrameTypeExtended, 15)


def checksum_disc(m: MessageFrame):
    if FrameOptions.CHECKSUM in m.options:
        return (int, 8)
    else:
        return (type(None), 0)


def body_disc(m: MessageFrame):
    n_bits = m.n_bytes_body * 8

    match m.type_group:
        case FrameTypeGroup.BASIC:
            match m.type:
                case FrameTypeBasic.GET_DEV_INFO:
                    out = GetDevInfoReplyBody if m.is_reply else GetDevInfoBody
                case FrameTypeBasic.READ_STATUS:
                    out = ReadStatusReplyBody if m.is_reply else ReadStatusBody
                case _:
                    out = bytes
        case FrameTypeGroup.EXTENDED:
            match m.type:
                case _:
                    out = bytes

    return (out, n_bits)


MessageBody = t.Union[
    GetDevInfoBody,
    GetDevInfoReplyBody,
    ReadStatusBody,
    ReadStatusReplyBody,
]


class MessageFrame(PackedBits):
    header: t.Literal[b'\xff\x01'] = bitfield(16, default=b'\xff\x01')
    options: FrameOptions = bitfield(8)
    n_bytes_body: int = bitfield(8)
    type_group: FrameTypeGroup = bitfield(16)
    is_reply: bool = bitfield(1)
    type: FrameTypeBasic | FrameTypeExtended = union_bitfield(frame_type_disc)
    body: MessageBody | bytes = union_bitfield(body_disc)
    checksum: int | None = union_bitfield(checksum_disc, default=None)
