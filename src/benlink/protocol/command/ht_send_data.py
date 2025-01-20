from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_dyn, bf_bitfield
from .common import ReplyStatus, TncDataFragment


class HTSendDataBody(Bitfield):
    tnc_data_fragment: TncDataFragment = bf_dyn(
        lambda _, n: bf_bitfield(TncDataFragment, n)
    )


class HTSendDataReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
