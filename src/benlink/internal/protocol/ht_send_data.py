from __future__ import annotations
from ..bitfield import Bitfield, bf_int_enum, bf_dyn, bf_bitfield
from .common import ReplyStatus, TNCDataPacket


class HTSendDataBody(Bitfield):
    tnc_data_packet: TNCDataPacket = bf_dyn(
        lambda _, n: bf_bitfield(TNCDataPacket, n)
    )


class HTSendDataReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
