from __future__ import annotations
from .bitfield import (
    Bitfield,
    bf_int,
    bf_int_enum,
    bf_dyn,
    bf_str,
    bf_lit_int,
    bf_bool,
    bf_map,
    IntScale,
)
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class PacketFormat(IntEnum):
    BSS = 0
    APRS = 1


class BSSSettings(Bitfield):
    max_fwd_times: int = bf_int(4)
    time_to_live: int = bf_int(4)
    ptt_release_send_location: bool
    ptt_release_send_id_info: bool
    ptt_release_send_bss_user_id: bool  # (Applies when BSS is turned on)
    should_share_location: bool
    send_pwr_voltage: bool
    packet_format: PacketFormat = bf_int_enum(PacketFormat, 1)
    allow_position_check: bool
    _unk_bss_0: bool = bf_bool(default=False)
    aprs_ssid: int = bf_int(4)
    smart_beacon_en: bool = bf_bool(default=False)
    mic_e_en: bool = bf_bool(default=False)
    send_id_by_aprs: bool = bf_bool(default=False)  # app also forces ptt_release_send_location on when copying configs
    _unk_bss_1: int = bf_int(1, default=0)
    location_share_interval: int = bf_map(bf_int(8), IntScale(10))
    bss_user_id_lower: int = bf_int(32)
    ptt_release_id_info: str = bf_str(12)
    beacon_message: str = bf_str(18)
    aprs_symbol: str = bf_str(2)
    aprs_callsign: str = bf_str(6)
    bss_user_id_upper: int = bf_int(32)


class BSSSettingsV2(BSSSettings):
    # App gates on soft_ver from DevInfo to pick write size:
    # soft_ver < 50 -> 46 bytes, 50-135 -> 50 bytes (BSSSettings), >= 136 -> 52 bytes (BSSSettingsV2)
    # to_protocol in command.py currently always writes BSSSettingsV2; should be conditioned on soft_ver
    smart_beacon_min_interval: int = bf_int(4, default=0)
    smart_beacon_max_interval: int = bf_int(5, default=0)
    _unk_bss_2: int = bf_int(7, default=0)


class ReadBSSSettingsBody(Bitfield):
    unknown: t.Literal[2] = bf_lit_int(8, default=2)


def bss_settings_reply_disc(reply: ReadBSSSettingsReplyBody, n: int):
    if reply.reply_status != ReplyStatus.SUCCESS:
        return None
    if n == BSSSettings.length():
        return BSSSettings
    if n == BSSSettingsV2.length():
        return BSSSettingsV2
    raise ValueError(f"Unknown size for BSSSettings ({n})")


class ReadBSSSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    bss_settings: BSSSettings | BSSSettingsV2 | None = bf_dyn(bss_settings_reply_disc)


class WriteBSSSettingsBody(Bitfield):
    bss_settings: BSSSettings | BSSSettingsV2 = bf_dyn(
        lambda _, n: BSSSettings if n == BSSSettings.length() else BSSSettingsV2
    )


class WriteBSSSettingsReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
