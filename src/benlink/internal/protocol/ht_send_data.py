from __future__ import annotations
from ..bitfield import Bitfield, bf_int_enum, bf_dyn, bf_bitfield
from .common import ReplyStatus, MessagePacket


class HTSendDataBody(Bitfield):
    message_packet: MessagePacket = bf_dyn(
        lambda _, n: bf_bitfield(MessagePacket, n)
    )


class HTSendDataReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
