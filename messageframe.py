from __future__ import annotations
from bitfield import (
    Bitfield,
    bf_int,
    bf_int_enum,
    bf_dyn,
    bf_bool,
    bf_bytes,
    bf_lit_int,
    bf_map,
    bf_list,
    bf_bitfield,
    Scale,
)
import typing as t
import sys
from enum import IntEnum, IntFlag


class ReplyStatus(IntEnum):
    SUCCESS = 0
    NOT_SUPPORTED = 1
    NOT_AUTHENTICATED = 2
    INSUFFICIENT_RESOURCES = 3
    AUTHENTICATING = 4
    INVALID_PARAMETER = 5
    INCORRECT_STATE = 6
    IN_PROGRESS = 7

#################################################
# EVENT_NOTIFICATION


class EventNotificationType(IntEnum):
    UNKNOWN = 0
    HT_STATUS_CHANGED = 1
    DATA_RXD = 2  # Received APRS or BSS Message
    NEW_INQUIRY_DATA = 3
    RESTORE_FACTORY_SETTINGS = 4
    HT_CH_CHANGED = 5
    HT_SETTINGS_CHANGED = 6
    RINGING_STOPPED = 7
    RADIO_STATUS_CHANGED = 8
    USER_ACTION = 9
    SYSTEM_EVENT = 10
    BSS_SETTINGS_CHANGED = 11


class ChannelType(IntEnum):
    OFF = 0
    A = 1
    B = 2


class EventNotificationHTStatusChanged(Bitfield):
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType = bf_int_enum(ChannelType, 2)
    is_scan: bool
    is_radio: bool
    curr_ch_id_lower: int = bf_int(4)
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)


class EventNotificationHTStatusChangedExt(Bitfield):
    curr_channel_id: int = bf_int(8)
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType = bf_int_enum(ChannelType, 2)
    is_scan: bool
    is_radio: bool
    # curr_ch_id_lower (reordered; 4)
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)
    rssi: float = bf_map(bf_int(4), Scale(100 / 15))
    curr_region: int = bf_int(6)
    # curr_channel_id_upper (reordered; 4)
    _pad2: t.Literal[0] = bf_lit_int(2, default=0)

    _reorder = [*range(26, 26+4), *range(8, 8+4)]


class EventNotificationUnknown(Bitfield):
    data: bytes = bf_dyn(lambda _, __, n: bf_bytes(n // 8))


class DataPacket(Bitfield):
    is_final_packet: bool
    with_channel_id: bool
    packet_id: int = bf_int(6)
    data: bytes = bf_dyn(
        lambda x, n: bf_bytes((n - 1 if x.with_channel_id else n) // 8)
    )
    channel_id: int | None = bf_dyn(
        lambda x: bf_int(8) if x.with_channel_id else None
    )


def event_notification_disc(m: EventNotificationBody, _: None, n: int):
    match m.event_type:
        case EventNotificationType.HT_STATUS_CHANGED:
            if n == EventNotificationHTStatusChanged.length():
                return EventNotificationHTStatusChanged
            if n == EventNotificationHTStatusChangedExt.length():
                return EventNotificationHTStatusChangedExt
            raise ValueError(
                f"Unknown size for HT_STATUS_CHANGED event ({n})"
            )
        case EventNotificationType.DATA_RXD:
            return bf_bitfield(DataPacket, n)
        case _:
            return bf_bitfield(EventNotificationUnknown, n)


class EventNotificationBody(Bitfield):
    event_type: EventNotificationType = bf_int_enum(EventNotificationType, 8)
    event: EventNotificationUnknown | DataPacket | EventNotificationHTStatusChanged | EventNotificationHTStatusChangedExt = bf_dyn(
        event_notification_disc
    )

#################################################
# GET_PF


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


class PFSetting(Bitfield):
    button_id: int = bf_int(4)
    action: PFActionType = bf_int_enum(PFActionType, 4)
    effect: PFEffectType = bf_int_enum(PFEffectType, 8)


class GetPFBody(Bitfield):
    pass


class GetPFReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    pf: t.List[PFSetting] = bf_list(PFSetting, 8)


#################################################
# READ_SETTINGS / WRITE_SETTINGS

class LocChMap:
    def forward(self, x: int) -> int | t.Literal["current"]:
        return x - 1 if x > 0 else "current"

    def back(self, y: int | t.Literal["current"]):
        return 0 if y == "current" else y + 1


class RadioSettings(Bitfield):
    channel_a: int = bf_int(8)
    channel_b: int = bf_int(8)
    scan: bool
    aghfp_call_mode: int = bf_int(1)
    double_channel: int = bf_int(2)
    squelch_level: int = bf_int(4)
    tail_elim: bool
    auto_relay_en: bool
    auto_power_on: bool
    keep_aghfp_link: bool
    mic_gain: int = bf_int(3)
    tx_hold_time: int = bf_int(4)
    tx_time_limit: int = bf_int(5)
    local_speaker: int = bf_int(2)
    bt_mic_gain: int = bf_int(3)
    adaptive_response: bool
    dis_tone: bool
    power_saving_mode: bool
    auto_power_off: int = bf_int(3)
    auto_share_loc_ch: int | t.Literal["current"] = bf_map(
        bf_int(5), LocChMap()
    )
    hm_speaker: int = bf_int(2)
    positioning_system: int = bf_int(4)
    time_offset: int = bf_int(6)
    use_freq_range_2: bool
    ptt_lock: bool
    leading_sync_bit_en: bool
    pairing_at_power_on: bool
    screen_timeout: int = bf_int(5)
    vfo_x: int = bf_int(2)
    imperial_unit: bool
    # channel_a_upper (reordered; 4)
    # channel_b_upper (reordered; 4)
    wx_mode: int = bf_int(2)
    noaa_ch: int = bf_int(4)
    vfol_tx_power_x: int = bf_int(2)
    vfo2_tx_power_x: int = bf_int(2)
    dis_digital_mute: bool
    signaling_ecc_en: bool
    ch_data_lock: bool
    _pad: t.Literal[0] = bf_lit_int(3, default=0)
    vfo1_mod_freq_x: int = bf_int(32)
    vfo2_mod_freq_x: int = bf_int(32)

    _reorder = list(range(72, 72 + 8))


class ReadSettingsBody(Bitfield):
    pass


class ReadSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    settings: RadioSettings


class WriteSettingsBody(Bitfield):
    settings: RadioSettings


class WriteSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)


#################################################
# READ_RF_CHANNEL / WRITE_RF_CHANNEL


class ModulationType(IntEnum):
    FM = 0
    AM = 1
    DMR = 2


class BandwidthType(IntEnum):
    NARROW = 0
    WIDE = 1


class DCS(t.NamedTuple):
    n: int


class SubAudioMap:
    def forward(self, x: int):
        if x == 0:
            return None

        return DCS(x) if x < 6700 else x / 100

    def back(self, y: DCS | float | None):
        match y:
            case None:
                return 0
            case DCS(n=n):
                return n
            case _:
                return round(y*100)


class ChannelSettings(Bitfield):
    tx_mod: ModulationType = bf_int_enum(ModulationType, 2)
    tx_freq: float = bf_map(bf_int(30), Scale(1e-6))
    rx_mod: ModulationType = bf_int_enum(ModulationType, 2)
    rx_freq: float = bf_map(bf_int(30), Scale(1e-6))
    tx_sub_audio: float | DCS | None = bf_map(bf_int(16), SubAudioMap())
    rx_sub_audio: float | DCS | None = bf_map(bf_int(16), SubAudioMap())
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType = bf_int_enum(BandwidthType, 1)
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwith: bool
    fixed_tx_power: bool
    mute: bool
    _pad: t.Literal[0] = bf_lit_int(4, default=0)
    name_str: bytes = bf_bytes(10)


class ChannelSettingsDMR(ChannelSettings):
    tx_color: int = bf_int(4)
    rx_color: int = bf_int(4)
    slot: int = bf_int(1)
    _pad2: t.Literal[0] = bf_lit_int(7, default=0)


def channel_settings_disc(_: ChannelSettings, __: None, n: int):
    # Note: in the app, this is detected via support_dmr in
    # device settings. But for simplicity, I'm just going to
    # use the size of the bitfield.
    if n == ChannelSettings.length():
        return ChannelSettings

    if n == ChannelSettingsDMR.length():
        return ChannelSettingsDMR

    raise ValueError(f"Unknown channel settings type (size {n})")


class ReadRFChBody(Bitfield):
    channel_id: int = bf_int(8)


class ReadRFChReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    channel_id: int = bf_int(8)
    channel_settings: ChannelSettings | ChannelSettingsDMR = bf_dyn(
        channel_settings_disc
    )


class WriteRFChBody(Bitfield):
    channel_id: int = bf_int(8)
    channel_settings: ChannelSettings | ChannelSettingsDMR = bf_dyn(
        channel_settings_disc
    )


class WriteRFChReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    channel_id: int = bf_int(8)


#################################################
# GET_DEV_STATE_VAR


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

# TODO


#################################################
# READ_STATUS


class ReadStatusType(IntEnum):
    UNKNOWN = 0
    BATTERY_LEVEL = 1
    BATTERY_VOLTAGE = 2
    RC_BATTERY_LEVEL = 3
    BATTERY_LEVEL_AS_PERCENTAGE = 4


class ReadStatusBody(Bitfield):
    status_type: ReadStatusType = bf_int_enum(ReadStatusType, 16)


class ReadStatusVoltage(Bitfield):
    voltage: float = bf_map(bf_int(16), Scale(1 / 1000))


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


#################################################
# GET_DEV_INFO


class DevInfo(Bitfield):
    vendor_id: int = bf_int(8)
    product_id: int = bf_int(16)
    hw_ver: int = bf_int(8)
    soft_ver: int = bf_int(16)
    support_radio: bool
    support_medium_power: bool
    fixed_loc_speaker_vol: bool
    not_support_soft_power_ctrl: bool
    have_no_speaker: bool
    have_hm_speaker: bool
    region_count: int = bf_int(6)
    support_noaa: bool
    gmrs: bool
    support_vfo: bool
    support_dmr: bool
    channel_count: int = bf_int(8)
    freq_range_count: int = bf_int(4)
    _pad: t.Literal[0] = bf_lit_int(4, default=0)


class GetDevInfoBody(Bitfield):
    unknown: t.Literal[3] = bf_lit_int(8, default=3)


class GetDevInfoReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    info: DevInfo | None = bf_dyn(
        lambda x: DevInfo
        if x.reply_status == ReplyStatus.SUCCESS
        else None
    )


#################################################
# MessageFrame


class FrameOptions(IntFlag):
    NONE = 0
    CHECKSUM = 1


class FrameTypeGroup(IntEnum):
    BASIC = 2
    EXTENDED = 10


class FrameTypeExtended(IntEnum):
    UNKNOWN = 0
    GET_BT_SIGNAL = 769
    UNKNOWN_01 = 1600
    UNKNOWN_02 = 1601
    UNKNOWN_03 = 1602
    UNKNOWN_04 = 16385
    UNKNOWN_05 = 16386
    GET_DEV_STATE_VAR = 16387
    DEV_REGISTRATION = 1825

    @ classmethod
    def _missing_(cls, value: object):
        print(f"Unknown value for FrameTypeExtended: {value}", file=sys.stderr)
        return cls.UNKNOWN


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


def frame_type_disc(m: MessageFrame):
    match m.type_group:
        case FrameTypeGroup.BASIC:
            return bf_int_enum(FrameTypeBasic, 15)
        case FrameTypeGroup.EXTENDED:
            return bf_int_enum(FrameTypeExtended, 15)


def checksum_disc(m: MessageFrame):
    if FrameOptions.CHECKSUM in m.options:
        return bf_int(8)
    else:
        return None


def body_disc(m: MessageFrame):
    match m.type_group:
        case FrameTypeGroup.BASIC:
            match m.type:
                case FrameTypeBasic.GET_DEV_INFO:
                    out = GetDevInfoReplyBody if m.is_reply else GetDevInfoBody
                case FrameTypeBasic.READ_STATUS:
                    out = ReadStatusReplyBody if m.is_reply else ReadStatusBody
                case FrameTypeBasic.READ_RF_CH:
                    out = ReadRFChReplyBody if m.is_reply else ReadRFChBody
                case FrameTypeBasic.WRITE_RF_CH:
                    out = WriteRFChReplyBody if m.is_reply else WriteRFChBody
                case FrameTypeBasic.READ_SETTINGS:
                    out = ReadSettingsReplyBody if m.is_reply else ReadSettingsBody
                case FrameTypeBasic.WRITE_SETTINGS:
                    out = WriteSettingsReplyBody if m.is_reply else WriteSettingsBody
                case FrameTypeBasic.GET_PF:
                    out = GetPFReplyBody if m.is_reply else GetPFBody
#                case FrameTypeBasic.READ_BSS_SETTINGS:
#                    out = ReadBSSSettingsReplyBody if m.is_reply else ReadBSSSettingsBody
#                case FrameTypeBasic.WRITE_BSS_SETTINGS:
#                    out = WriteBSSSettingsReplyBody if m.is_reply else WriteBSSSettingsBody
                case FrameTypeBasic.EVENT_NOTIFICATION:
                    if m.is_reply:
                        raise ValueError("EventNotification cannot be a reply")
                    out = EventNotificationBody
                case _:
                    return bf_bytes(m.n_bytes_body)
        case FrameTypeGroup.EXTENDED:
            match m.type:
                case _:
                    return bf_bytes(m.n_bytes_body)

    return bf_bitfield(out, m.n_bytes_body * 8)


MessageBody = t.Union[
    GetDevInfoBody,
    GetDevInfoReplyBody,
    ReadStatusBody,
    ReadStatusReplyBody,
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
    # ReadBSSSettingsBody,
    # ReadBSSSettingsReplyBody,
    # WriteBSSSettingsBody,
    # WriteBSSSettingsReplyBody,
    EventNotificationBody,
]


class MessageFrame(Bitfield):
    header: t.Literal[b'\xff\x01'] = b'\xff\x01'
    options: FrameOptions = bf_int_enum(FrameOptions, 8)
    n_bytes_body: int = bf_int(8)
    type_group: FrameTypeGroup = bf_int_enum(FrameTypeGroup, 16)
    is_reply: bool = bf_bool()
    type: FrameTypeBasic | FrameTypeExtended = bf_dyn(frame_type_disc)
    body: MessageBody | bytes = bf_dyn(body_disc)
    checksum: int | None = bf_dyn(checksum_disc, default=None)
