from __future__ import annotations
from .bitfield import Bitfield, bf_lit_int, bf_int_enum, bf_list, bf_bool
import typing as t
from .common import ReplyStatus


class SetPhoneStatusBody(Bitfield):
    is_channel_bonded_lower: t.List[bool] = bf_list(bf_bool(), 16)
    is_linked: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)
    is_channel_bonded_upper: t.List[bool] = bf_list(bf_bool(), 16)
    _pad2: t.Literal[0] = bf_lit_int(14, default=0)


class SetPhoneStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
