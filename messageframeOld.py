from __future__ import annotations
# from dataclasses import dataclass
from packedbits import PackedBits, bitfield, union_bitfield
import typing as t
from enum import IntEnum, IntFlag
import sys


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
# READ_BSS_SETTINGS / WRITE_BSS_SETTINGS


class BSSSettings(PackedBits):
    max_fwd_times: int = bitfield(4)
    time_to_live: int = bitfield(4)
    ptt_release_send_location: bool = bitfield(1)
    ptt_release_send_id_info: bool = bitfield(1)
    # The below applies when bss is turned on
    ptt_release_send_bss_user_id: bool = bitfield(1)
    should_share_location: bool = bitfield(1)
    send_pwr_voltage: bool = bitfield(1)
    use_aprs_format: bool = bitfield(1)
    allow_position_check: bool = bitfield(1)
    _pad: t.Literal[0] = bitfield(1)
    aprs_ssid: int = bitfield(4)
    _pad2: t.Literal[0] = bitfield(4)
    location_share_interval: int = bitfield(8)
    bss_user_id_lower: int = bitfield(32)
    ptt_release_id_info: bytes = bitfield(8 * 12)
    beacon_message: bytes = bitfield(8 * 18)
    aprs_symbol: bytes = bitfield(8 * 2)
    aprs_callsign: bytes = bitfield(8 * 6)


class BSSSettingsExt(BSSSettings):
    bss_user_id_upper: int = bitfield(32)


class ReadBSSSettingsBody(PackedBits):
    unknown: int = bitfield(8)


class ReadBSSSettingsReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    bss_settings: BSSSettings | BSSSettingsExt = union_bitfield(
        lambda x, _: BSSSettingsExt  # TODO: Switch based on response size
    )


class WriteBSSSettingsBody(PackedBits):
    bss_settings: BSSSettings | BSSSettingsExt = union_bitfield(
        lambda x, _: BSSSettingsExt  # TODO: Switch based on response size
    )


class WriteBSSSettingsReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)


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


class EventNotificationHTStatusChanged(PackedBits):
    is_power_on: bool = bitfield(1)
    is_in_tx: bool = bitfield(1)
    is_sq: bool = bitfield(1)
    is_in_rx: bool = bitfield(1)
    double_channel: ChannelType = bitfield(2)
    is_scan: bool = bitfield(1)
    is_radio: bool = bitfield(1)
    curr_ch_id_lower: int = bitfield(4)
    is_gps_locked: bool = bitfield(1)
    is_hfp_connected: bool = bitfield(1)
    is_aoc_connected: bool = bitfield(1)
    _pad: t.Literal[0] = bitfield(1, default=0)


class EventNotificationHTStatusChangedExt(EventNotificationHTStatusChanged):
    rssi: int = bitfield(4)  # scale: value * 100 / 15
    curr_region: int = bitfield(6)
    curr_channel_id_upper: int = bitfield(4)
    _pad2: t.Literal[0] = bitfield(2, default=0)


class EventNotificationUnknown(PackedBits):
    data: bytes = bitfield(lambda _, n: n)


class DataPacket(PackedBits):
    is_final_packet: bool = bitfield(1)
    with_channel_id: bool = bitfield(1)
    packet_id: int = bitfield(6)
    data: bytes = bitfield(
        lambda x, n: n - 1 if x.with_channel_id else n
    )
    channel_id: int | None = union_bitfield(
        lambda x, _: (int, 8) if x.with_channel_id else None
    )


def event_notification_disc(m: EventNotificationBody, n_bits_available: int):
    match m.event_type:
        case EventNotificationType.HT_STATUS_CHANGED:
            return EventNotificationHTStatusChangedExt
        case EventNotificationType.DATA_RXD:
            return (DataPacket, n_bits_available)
        case _:
            return (EventNotificationUnknown, n_bits_available)


class EventNotificationBody(PackedBits):
    event_type: EventNotificationType = bitfield(8)
    event: EventNotificationUnknown | DataPacket | EventNotificationHTStatusChangedExt = union_bitfield(
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


class PFSetting(PackedBits):
    button_id: int = bitfield(4)
    action: PFActionType = bitfield(4)
    effect: PFEffectType = bitfield(8)


class GetPFBody(PackedBits):
    pass


class GetPFReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    # TODO: Support array bitfields
    pf00: PFSetting = bitfield()
    pf01: PFSetting = bitfield()
    pf02: PFSetting = bitfield()
    pf03: PFSetting = bitfield()
    pf04: PFSetting = bitfield()
    pf05: PFSetting = bitfield()
    pf06: PFSetting = bitfield()
    pf07: PFSetting = bitfield()

#################################################
# READ_SETTINGS / WRITE_SETTINGS


class RadioSettings(PackedBits):
    channel_a_lower: int = bitfield(4)
    channel_b_lower: int = bitfield(4)
    scan: bool = bitfield(1)
    aghfp_call_mode: int = bitfield(1)
    double_channel: int = bitfield(2)
    squelch_level: int = bitfield(4)
    tail_elim: bool = bitfield(1)
    auto_relay_en: bool = bitfield(1)
    auto_power_on: bool = bitfield(1)
    keep_aghfp_link: bool = bitfield(1)
    mic_gain: int = bitfield(3)
    tx_hold_time: int = bitfield(4)
    tx_time_limit: int = bitfield(5)
    local_speaker: int = bitfield(2)
    bt_mic_gain: int = bitfield(3)
    adaptive_response: bool = bitfield(1)
    dis_tone: bool = bitfield(1)
    power_saving_mode: bool = bitfield(1)
    auto_power_off: int = bitfield(3)
    # Note: auto_share_loc_ch is 1 higher than the actual channel
    # so that a 0 here means "current channel" and 1 is channel 0, etc.
    auto_share_loc_ch: int = bitfield(5)
    hm_speaker: int = bitfield(2)
    positioning_system: int = bitfield(4)
    time_offset: int = bitfield(6)
    use_freq_range_2: bool = bitfield(1)
    ptt_lock: bool = bitfield(1)
    leading_sync_bit_en: bool = bitfield(1)
    pairing_at_power_on: bool = bitfield(1)
    screen_timeout: int = bitfield(5)
    vfo_x: int = bitfield(2)
    imperial_unit: bool = bitfield(1)
    channel_a_upper: int = bitfield(4)
    channel_b_upper: int = bitfield(4)
    wx_mode: int = bitfield(2)
    noaa_ch: int = bitfield(4)
    vfol_tx_power_x: int = bitfield(2)
    vfo2_tx_power_x: int = bitfield(2)
    dis_digital_mute: bool = bitfield(1)
    signaling_ecc_en: bool = bitfield(1)
    ch_data_lock: bool = bitfield(1)
    _pad: t.Literal[0] = bitfield(3)
    vfo1_mod_freq_x: int = bitfield(32)
    vfo2_mod_freq_x: int = bitfield(32)


class ReadSettingsBody(PackedBits):
    pass


class ReadSettingsReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    settings: RadioSettings = bitfield()


class WriteSettingsBody(PackedBits):
    settings: RadioSettings = bitfield()


class WriteSettingsReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)

#################################################
# READ_RF_CHANNEL / WRITE_RF_CHANNEL


class ModulationType(IntEnum):
    FM = 0
    AM = 1
    DMR = 2


class BandwidthType(IntEnum):
    NARROW = 0
    WIDE = 1


class ChannelSettings(PackedBits):
    tx_mod: ModulationType = bitfield(2)
    tx_freq: int = bitfield(30)
    rx_mod: ModulationType = bitfield(2)
    rx_freq: int = bitfield(30)
    tx_sub_audio: int = bitfield(16)
    rx_sub_audio: int = bitfield(16)
    scan: bool = bitfield(1)
    tx_at_max_power: bool = bitfield(1)
    talk_around: bool = bitfield(1)
    bandwidth: BandwidthType = bitfield(1)
    pre_de_emph_bypass: bool = bitfield(1)
    sign: bool = bitfield(1)
    tx_at_med_power: bool = bitfield(1)
    tx_disable: bool = bitfield(1)
    fixed_freq: bool = bitfield(1)
    fixed_bandwith: bool = bitfield(1)
    fixed_tx_power: bool = bitfield(1)
    mute: bool = bitfield(1)
    _pad: t.Literal[0] = bitfield(4, default=0)
    name_str: bytes = bitfield(80)


class ChannelSettingsDMR(ChannelSettings):
    tx_color: int = bitfield(4)
    rx_color: int = bitfield(4)
    slot: int = bitfield(1)
    _pad2: t.Literal[0] = bitfield(7)


class ReadRFChBody(PackedBits):
    channel_id: int = bitfield(8)


class ReadRFChReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    channel_id: int = bitfield(8)
    # In the app, this is detected via support_dmr in
    # device settings. ... I need to figure out how to
    # pass context to union bitfields...
    # Or, I guess I could just use bits available?
    channel_settings: ChannelSettings | ChannelSettingsDMR = union_bitfield(
        lambda _, __: ChannelSettings
    )


class WriteRFChBody(PackedBits):
    channel_id: int = bitfield(8)
    channel_settings: ChannelSettings = bitfield()


class WriteRFChReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    channel_id: int = bitfield(8)


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


class ReadStatusBody(PackedBits):
    status_type: ReadStatusType = bitfield(16)


class ReadStatusVoltage(PackedBits):
    voltage: int = bitfield(16)  # Scale: value / 1000


class ReadStatusBatteryLevel(PackedBits):
    level: int = bitfield(8)


class ReadStatusBatteryLevelPercentage(PackedBits):
    percentage: int = bitfield(8)


class ReadStatusRCBatteryLevel(PackedBits):
    level: int = bitfield(8)


RadioStatus = t.Union[
    ReadStatusVoltage,
    ReadStatusBatteryLevel,
    ReadStatusBatteryLevelPercentage,
    ReadStatusRCBatteryLevel,
]


def radio_status_disc(m: ReadStatusBody, _: int):
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


class ReadStatusReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    status_type: ReadStatusType = bitfield(16)
    value: RadioStatus = union_bitfield(radio_status_disc)

#################################################
# GET_DEV_INFO


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
    _pad: t.Literal[0] = bitfield(4, default=0)


class GetDevInfoBody(PackedBits):
    unknown: t.Literal[3] = bitfield(8, default=3)


class GetDevInfoReplyBody(PackedBits):
    reply_status: ReplyStatus = bitfield(8)
    info: DevInfo | None = union_bitfield((
        lambda x, _: DevInfo
        if x.reply_status == ReplyStatus.SUCCESS
        else None
    ))

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


def frame_type_disc(m: MessageFrame, _: int):
    match m.type_group:
        case FrameTypeGroup.BASIC:
            return (FrameTypeBasic, 15)
        case FrameTypeGroup.EXTENDED:
            return (FrameTypeExtended, 15)


def checksum_disc(m: MessageFrame, _: int):
    if FrameOptions.CHECKSUM in m.options:
        return (int, 8)
    else:
        return None


def body_disc(m: MessageFrame, _: int):
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
                case FrameTypeBasic.READ_BSS_SETTINGS:
                    out = ReadBSSSettingsReplyBody if m.is_reply else ReadBSSSettingsBody
                case FrameTypeBasic.WRITE_BSS_SETTINGS:
                    out = WriteBSSSettingsReplyBody if m.is_reply else WriteBSSSettingsBody
                case FrameTypeBasic.EVENT_NOTIFICATION:
                    if m.is_reply:
                        raise ValueError("EventNotification cannot be a reply")
                    out = EventNotificationBody
                case _:
                    out = bytes
        case FrameTypeGroup.EXTENDED:
            match m.type:
                case _:
                    out = bytes

    return (out, m.n_bytes_body * 8)


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
    ReadBSSSettingsBody,
    ReadBSSSettingsReplyBody,
    WriteBSSSettingsBody,
    WriteBSSSettingsReplyBody,
    EventNotificationBody,
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
