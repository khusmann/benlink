from __future__ import annotations
from .bitfield import Bitfield, bf_lit_int, bf_int_enum, bf_list, bf_bool, bf_dyn, bf_bytes
import typing as t
from .common import ReplyStatus


class PhoneStatus(Bitfield):
    is_channel_bonded_lower: t.List[bool] = bf_list(bf_bool(), 16)
    is_linked: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)
    is_channel_bonded_upper: t.List[bool] = bf_list(bf_bool(), 16)
    _pad2: t.Literal[0] = bf_lit_int(14, default=0)


def phone_status_disc(_: SetPhoneStatusBody, n: int):
    if n == PhoneStatus.length():
        return PhoneStatus

    # TODO: There's a 32 bit version of phone status that popped up in
    # uv-pro 0.7.9-32 upgrade firmware. I'll need to see what it is...
    return bf_bytes(n // 8)


class SetPhoneStatusBody(Bitfield):
    phone_status: PhoneStatus | bytes = bf_dyn(phone_status_disc)


class SetPhoneStatusReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
