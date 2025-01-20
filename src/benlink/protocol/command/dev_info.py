from __future__ import annotations
import typing as t
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_lit_int
from .common import ReplyStatus


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
    dev_info: DevInfo | None = bf_dyn(
        lambda x: DevInfo
        if x.reply_status == ReplyStatus.SUCCESS
        else None
    )
