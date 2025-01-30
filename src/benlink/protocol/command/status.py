from __future__ import annotations
from .bitfield import (
    Bitfield,
    bf_int,
    bf_int_enum,
    bf_lit_int,
    bf_map,
    bf_dyn,
    Scale,
)
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class ChannelType(IntEnum):
    OFF = 0
    A = 1
    B = 2


class Status(Bitfield):
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


class StatusExt(Status):
    rssi: float = bf_map(bf_int(4), Scale(100 / 15))
    curr_region: int = bf_int(6)
    curr_channel_id_upper: int = bf_int(4)
    _pad2: t.Literal[0] = bf_lit_int(2, default=0)


def status_disc(m: GetHtStatusReplyBody, n: int):
    if m.reply_status != ReplyStatus.SUCCESS:
        return None

    if n == StatusExt.length():
        return StatusExt
    if n == Status.length():
        return Status

    raise ValueError(f"Unknown size for status type: {n}")


class GetHtStatusBody(Bitfield):
    pass


class GetHtStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    status: Status | StatusExt | None = bf_dyn(status_disc)
