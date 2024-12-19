from __future__ import annotations
from . import protocol as p
from .common import DCS, ImmutableBaseModel

import typing as t


def radio_message_from_bytes(data: t.ByteString) -> RadioMessage:
    return radio_message_from_protocol(p.Message.from_bytes(data))


def client_message_to_bytes(m: ClientMessage) -> bytes:
    return client_message_to_protocol(m).to_bytes()


def client_message_to_protocol(m: ClientMessage) -> p.Message:
    match m:
        case GetDeviceInfo():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.GET_DEV_INFO,
                body=p.GetDevInfoBody()
            )
        case GetChannelSettings(channel_id=channel_id):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_RF_CH,
                body=p.ReadRFChBody(channel_id=channel_id)
            )
        case SetChannelSettings(channel_settings=channel_settings):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.WRITE_RF_CH,
                body=p.WriteRFChBody(
                    rf_ch=channel_settings.to_protocol()
                )
            )
        case GetRadioSettings():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_SETTINGS,
                body=p.ReadSettingsBody()
            )


def radio_message_from_protocol(mf: p.Message) -> RadioMessage:
    match mf.body:
        case p.EventNotificationBody(
            event=p.HTSettingsChanged(
                settings=settings
            )
        ):
            return EventNotificationHTSettingsChanged(radio_settings=RadioSettings.from_protocol(settings))
        case p.ReadSettingsReplyBody(
            reply_status=reply_status,
            settings=settings
        ):
            if settings is None:
                return MessageReplyError(
                    message_type=GetRadioSettingsReply,
                    reason=reply_status.name,
                )
            return GetRadioSettingsReply(radio_settings=RadioSettings.from_protocol(settings))
        case p.GetDevInfoReplyBody(
            reply_status=reply_status,
            dev_info=dev_info
        ):
            if dev_info is None:
                return MessageReplyError(
                    message_type=GetDeviceInfoReply,
                    reason=reply_status.name,
                )
            return GetDeviceInfoReply(device_info=DeviceInfo.from_protocol(dev_info))
        case p.ReadRFChReplyBody(
            reply_status=reply_status,
            rf_ch=rf_ch
        ):
            if rf_ch is None:
                return MessageReplyError(
                    message_type=GetChannelSettingsReply,
                    reason=reply_status.name,
                )
            return GetChannelSettingsReply(channel_settings=ChannelSettings.from_protocol(rf_ch))
        case p.WriteRFChReplyBody(
            reply_status=reply_status,
        ):
            if reply_status != p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    message_type=SetChannelSettingsReply,
                    reason=reply_status.name,
                )
            return SetChannelSettingsReply()

        case _:
            return UnknownProtocolMessage(message=mf)


"""
        case p.Message(
            body=p.EventNotificationBody(
                event_type=p.EventType.HT_SETTINGS_CHANGED,
                event=p.HTSettingsChanged(
                    settings=settings
                )
            )
        ):
            return EventNotificationHTSettingsChanged(radio_settings=RadioSettings.from_protocol(settings))
        case p.Message(
            command_group=command_group,
            command=command,
            body=p.ReadSettingsReplyBody(
                reply_status=reply_status,
                settings=settings
            )
        ):
            if settings is None:
                return MessageReplyError(
                    command_group=command_group.name,
                    command=command.name,
                    reason=reply_status.name,
                )
            return GetRadioSettingsReply(radio_settings=RadioSettings.from_protocol(settings))
        case p.Message(
            command_group=command_group,
            command=command,
            body=p.WriteRFChReplyBody(
                reply_status=reply_status,
            )
        ):
            if reply_status is not p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    command_group=command_group.name,
                    command=command.name,
                    reason=reply_status.name,
                )
            return SetChannelSettingsReply()
        case p.Message(
            command_group=command_group,
            command=command,
            body=p.GetDevInfoReplyBody(
                reply_status=reply_status,
                info=info
            )
        ):
            if info is None:
                return MessageReplyError(
                    command_group=command_group.name,
                    command=command.name,
                    reason=reply_status.name,
                )
            return GetDeviceInfoReply(device_info=DeviceInfo.from_protocol(info))
        case p.Message(
            command_group=command_group,
            command=command,
            body=p.ReadRFChReplyBody(
                reply_status=reply_status,
                rf_ch=rf_ch
            )
        ):
            if rf_ch is None:
                return MessageReplyError(
                    command_group=command_group.name,
                    command=command.name,
                    reason=reply_status.name,
                )
            return GetChannelSettingsReply(channel_settings=ChannelSettings.from_protocol(rf_ch))
        case _:
            return UnknownProtocolMessage(message=mf)
"""


class GetDeviceInfo(t.NamedTuple):
    pass


class GetChannelSettings(t.NamedTuple):
    channel_id: int


class SetChannelSettings(t.NamedTuple):
    channel_settings: ChannelSettings


class GetRadioSettings(t.NamedTuple):
    pass


ClientMessage = t.Union[
    GetDeviceInfo,
    GetChannelSettings,
    SetChannelSettings,
    GetRadioSettings,


]


class GetDeviceInfoReply(t.NamedTuple):
    device_info: DeviceInfo


class GetChannelSettingsReply(t.NamedTuple):
    channel_settings: ChannelSettings


class SetChannelSettingsReply(t.NamedTuple):
    pass


class GetRadioSettingsReply(t.NamedTuple):
    radio_settings: RadioSettings


class EventNotificationHTSettingsChanged(t.NamedTuple):
    radio_settings: RadioSettings


ReplyStatus = t.Literal[
    "SUCCESS",
    "NOT_SUPPORTED",
    "NOT_AUTHENTICATED",
    "INSUFFICIENT_RESOURCES",
    "AUTHENTICATING",
    "INVALID_PARAMETER",
    "INCORRECT_STATE",
    "IN_PROGRESS",
]


class MessageReplyError(t.NamedTuple):
    message_type: t.Type[t.Any]
    reason: ReplyStatus

    def as_exception(self):
        return ValueError(f"{self.message_type.__name__} failed: {self.reason}")


class UnknownProtocolMessage(t.NamedTuple):
    message: p.Message


RadioMessage = t.Union[
    EventNotificationHTSettingsChanged,
    GetDeviceInfoReply,
    GetChannelSettingsReply,
    SetChannelSettingsReply,
    GetRadioSettingsReply,
    UnknownProtocolMessage,
    MessageReplyError,
]

RadioMessageT = t.TypeVar("RadioMessageT", bound=RadioMessage)

#####################
# Protocol to Message conversions


ModulationType = t.Literal["AM", "FM", "DMR"]

BandwidthType = t.Literal["NARROW", "WIDE"]


class ChannelSettingsArgs(t.TypedDict, total=False):
    tx_mod: ModulationType
    tx_freq: float
    rx_mod: ModulationType
    rx_freq: float
    tx_sub_audio: float | DCS | None
    rx_sub_audio: float | DCS | None
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwidth: bool
    fixed_tx_power: bool
    mute: bool
    name: str


class ChannelSettings(ImmutableBaseModel):
    channel_id: int
    tx_mod: ModulationType
    tx_freq: float
    rx_mod: ModulationType
    rx_freq: float
    tx_sub_audio: float | DCS | None
    rx_sub_audio: float | DCS | None
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwidth: bool
    fixed_tx_power: bool
    mute: bool
    name: str

    @ staticmethod
    def from_protocol(cs: p.RfCh) -> ChannelSettings:
        return ChannelSettings(
            channel_id=cs.channel_id,
            tx_mod=cs.tx_mod.name,
            tx_freq=cs.tx_freq,
            rx_mod=cs.rx_mod.name,
            rx_freq=cs.rx_freq,
            tx_sub_audio=cs.tx_sub_audio,
            rx_sub_audio=cs.rx_sub_audio,
            scan=cs.scan,
            tx_at_max_power=cs.tx_at_max_power,
            talk_around=cs.talk_around,
            bandwidth=cs.bandwidth.name,
            pre_de_emph_bypass=cs.pre_de_emph_bypass,
            sign=cs.sign,
            tx_at_med_power=cs.tx_at_med_power,
            tx_disable=cs.tx_disable,
            fixed_freq=cs.fixed_freq,
            fixed_bandwidth=cs.fixed_bandwidth,
            fixed_tx_power=cs.fixed_tx_power,
            mute=cs.mute,
            name=cs.name_str
        )

    def to_protocol(self) -> p.RfCh:
        return p.RfCh(
            channel_id=self.channel_id,
            tx_mod=p.ModulationType[self.tx_mod],
            tx_freq=self.tx_freq,
            rx_mod=p.ModulationType[self.rx_mod],
            rx_freq=self.rx_freq,
            tx_sub_audio=self.tx_sub_audio,
            rx_sub_audio=self.rx_sub_audio,
            scan=self.scan,
            tx_at_max_power=self.tx_at_max_power,
            talk_around=self.talk_around,
            bandwidth=p.BandwidthType[self.bandwidth],
            pre_de_emph_bypass=self.pre_de_emph_bypass,
            sign=self.sign,
            tx_at_med_power=self.tx_at_med_power,
            tx_disable=self.tx_disable,
            fixed_freq=self.fixed_freq,
            fixed_bandwidth=self.fixed_bandwidth,
            fixed_tx_power=self.fixed_tx_power,
            mute=self.mute,
            name_str=self.name
        )


class RadioSettings(ImmutableBaseModel):
    channel_a: int
    channel_b: int
    scan: bool
    aghfp_call_mode: int
    double_channel: int
    squelch_level: int
    tail_elim: bool
    auto_relay_en: bool
    auto_power_on: bool
    keep_aghfp_link: bool
    mic_gain: int
    tx_hold_time: int
    tx_time_limit: int
    local_speaker: int
    bt_mic_gain: int
    adaptive_response: bool
    dis_tone: bool
    power_saving_mode: bool
    auto_power_off: int
    auto_share_loc_ch: int | t.Literal["current"]
    hm_speaker: int
    positioning_system: int
    time_offset: int
    use_freq_range_2: bool
    ptt_lock: bool
    leading_sync_bit_en: bool
    pairing_at_power_on: bool
    screen_timeout: int
    vfo_x: int
    imperial_unit: bool
    wx_mode: int
    noaa_ch: int
    vfol_tx_power_x: int
    vfo2_tx_power_x: int
    dis_digital_mute: bool
    signaling_ecc_en: bool
    ch_data_lock: bool
    vfo1_mod_freq_x: int
    vfo2_mod_freq_x: int

    @staticmethod
    def from_protocol(rs: p.Settings) -> RadioSettings:
        return RadioSettings(
            channel_a=rs.channel_a,
            channel_b=rs.channel_b,
            scan=rs.scan,
            aghfp_call_mode=rs.aghfp_call_mode,
            double_channel=rs.double_channel,
            squelch_level=rs.squelch_level,
            tail_elim=rs.tail_elim,
            auto_relay_en=rs.auto_relay_en,
            auto_power_on=rs.auto_power_on,
            keep_aghfp_link=rs.keep_aghfp_link,
            mic_gain=rs.mic_gain,
            tx_hold_time=rs.tx_hold_time,
            tx_time_limit=rs.tx_time_limit,
            local_speaker=rs.local_speaker,
            bt_mic_gain=rs.bt_mic_gain,
            adaptive_response=rs.adaptive_response,
            dis_tone=rs.dis_tone,
            power_saving_mode=rs.power_saving_mode,
            auto_power_off=rs.auto_power_off,
            auto_share_loc_ch=rs.auto_share_loc_ch,
            hm_speaker=rs.hm_speaker,
            positioning_system=rs.positioning_system,
            time_offset=rs.time_offset,
            use_freq_range_2=rs.use_freq_range_2,
            ptt_lock=rs.ptt_lock,
            leading_sync_bit_en=rs.leading_sync_bit_en,
            pairing_at_power_on=rs.pairing_at_power_on,
            screen_timeout=rs.screen_timeout,
            vfo_x=rs.vfo_x,
            imperial_unit=rs.imperial_unit,
            wx_mode=rs.wx_mode,
            noaa_ch=rs.noaa_ch,
            vfol_tx_power_x=rs.vfol_tx_power_x,
            vfo2_tx_power_x=rs.vfo2_tx_power_x,
            dis_digital_mute=rs.dis_digital_mute,
            signaling_ecc_en=rs.signaling_ecc_en,
            ch_data_lock=rs.ch_data_lock,
            vfo1_mod_freq_x=rs.vfo1_mod_freq_x,
            vfo2_mod_freq_x=rs.vfo2_mod_freq_x
        )

    def to_protocol(self):
        return p.Settings(
            channel_a=self.channel_a,
            channel_b=self.channel_b,
            scan=self.scan,
            aghfp_call_mode=self.aghfp_call_mode,
            double_channel=self.double_channel,
            squelch_level=self.squelch_level,
            tail_elim=self.tail_elim,
            auto_relay_en=self.auto_relay_en,
            auto_power_on=self.auto_power_on,
            keep_aghfp_link=self.keep_aghfp_link,
            mic_gain=self.mic_gain,
            tx_hold_time=self.tx_hold_time,
            tx_time_limit=self.tx_time_limit,
            local_speaker=self.local_speaker,
            bt_mic_gain=self.bt_mic_gain,
            adaptive_response=self.adaptive_response,
            dis_tone=self.dis_tone,
            power_saving_mode=self.power_saving_mode,
            auto_power_off=self.auto_power_off,
            auto_share_loc_ch=self.auto_share_loc_ch,
            hm_speaker=self.hm_speaker,
            positioning_system=self.positioning_system,
            time_offset=self.time_offset,
            use_freq_range_2=self.use_freq_range_2,
            ptt_lock=self.ptt_lock,
            leading_sync_bit_en=self.leading_sync_bit_en,
            pairing_at_power_on=self.pairing_at_power_on,
            screen_timeout=self.screen_timeout,
            vfo_x=self.vfo_x,
            imperial_unit=self.imperial_unit,
            wx_mode=self.wx_mode,
            noaa_ch=self.noaa_ch,
            vfol_tx_power_x=self.vfol_tx_power_x,
            vfo2_tx_power_x=self.vfo2_tx_power_x,
            dis_digital_mute=self.dis_digital_mute,
            signaling_ecc_en=self.signaling_ecc_en,
            ch_data_lock=self.ch_data_lock,
            vfo1_mod_freq_x=self.vfo1_mod_freq_x,
            vfo2_mod_freq_x=self.vfo2_mod_freq_x
        )


class DeviceInfo(ImmutableBaseModel):
    vendor_id: int
    product_id: int
    hardware_version: int
    firmware_version: int
    supports_radio: bool
    supports_medium_power: bool
    fixed_location_speaker_volume: bool
    has_speaker: bool
    has_hand_microphone_speaker: bool
    region_count: int
    supports_noaa: bool
    supports_gmrs: bool
    supports_vfo: bool
    supports_dmr: bool
    supports_software_power_control: bool
    channel_count: int
    frequency_range_count: int

    @staticmethod
    def from_protocol(info: p.DevInfo) -> DeviceInfo:
        return DeviceInfo(
            vendor_id=info.vendor_id,
            product_id=info.product_id,
            hardware_version=info.hw_ver,
            firmware_version=info.soft_ver,
            supports_radio=info.support_radio,
            supports_medium_power=info.support_medium_power,
            fixed_location_speaker_volume=info.fixed_loc_speaker_vol,
            supports_software_power_control=not info.not_support_soft_power_ctrl,
            has_speaker=not info.have_no_speaker,
            has_hand_microphone_speaker=info.have_hm_speaker,
            region_count=info.region_count,
            supports_noaa=info.support_noaa,
            supports_gmrs=info.gmrs,
            supports_vfo=info.support_vfo,
            supports_dmr=info.support_dmr,
            channel_count=info.channel_count,
            frequency_range_count=info.freq_range_count
        )

    def to_protocol(self) -> p.DevInfo:
        return p.DevInfo(
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            hw_ver=self.hardware_version,
            soft_ver=self.firmware_version,
            support_radio=self.supports_radio,
            support_medium_power=self.supports_medium_power,
            fixed_loc_speaker_vol=self.fixed_location_speaker_volume,
            not_support_soft_power_ctrl=not self.supports_software_power_control,
            have_no_speaker=not self.has_speaker,
            have_hm_speaker=self.has_hand_microphone_speaker,
            region_count=self.region_count,
            support_noaa=self.supports_noaa,
            gmrs=self.supports_gmrs,
            support_vfo=self.supports_vfo,
            support_dmr=self.supports_dmr,
            channel_count=self.channel_count,
            freq_range_count=self.frequency_range_count
        )
