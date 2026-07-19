from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_int, bf_dyn
from .common import ReplyStatus
import typing as t


class LocChMap:
    def forward(self, x: int) -> int | t.Literal["current"]:
        return x - 1 if x > 0 else "current"

    def back(self, y: int | t.Literal["current"]):
        return 0 if y == "current" else y + 1


class Settings(Bitfield):
    channel_a_lower: int = bf_int(4)
    channel_b_lower: int = bf_int(4)
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
    auto_share_loc_ch: int = bf_int(5)
    hm_speaker: int = bf_int(2)
    positioning_system: int = bf_int(4)
    time_offset: int = bf_int(6)
    use_freq_range_2: bool
    ptt_lock: bool
    leading_sync_bit_en: bool
    pairing_at_power_on: bool
    screen_timeout: int = bf_int(5)
    kiss_upload_tx_msg: bool
    kiss_en: bool
    imperial_unit: bool
    channel_a_upper: int = bf_int(4)
    channel_b_upper: int = bf_int(4)
    wx_mode: int = bf_int(2)
    noaa_ch: int = bf_int(4)
    vfol_tx_power_x: int = bf_int(2)
    vfo2_tx_power_x: int = bf_int(2)
    dis_digital_mute: bool
    signaling_ecc_en: bool
    ch_data_lock: bool
    auto_share_loc_ch_upper: int = bf_int(3)
    kiss_tx_delay: int = bf_int(8)
    kiss_tx_tail: int = bf_int(8)
    vox_en: bool
    vox_level: int = bf_int(3)
    dis_bt_mic: bool
    vox_delay: int = bf_int(3)
    ns_en: bool
    alarm_volume: int = bf_int(4)
    use_custom_location: bool
    gpwpl_upload_en: bool
    vfo1_mod_freq_x: int = bf_int(1)
    custom_location_lat: int = bf_int(24)
    custom_location_lon: int = bf_int(24)


class ReadSettingsBody(Bitfield):
    pass


class ReadSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    settings: Settings | None = bf_dyn(
        lambda x: Settings if x.reply_status == ReplyStatus.SUCCESS else None
    )


class WriteSettingsBody(Bitfield):
    settings: Settings


class WriteSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
