from __future__ import annotations
from enum import IntFlag
import typing as t

from ..bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_bitfield
from .message import Message

# GaiaFrames hold messages sent to and from the radio when in Blueooth classic
# mode. After figuring out the GaiaFrame structure, I later found it randomly
# documented here: https://slideplayer.com/slide/12945885/


class GaiaFlags(IntFlag):
    NONE = 0
    CHECKSUM = 1


def checksum_disc(m: GaiaFrame):
    if GaiaFlags.CHECKSUM in m.flags:
        return bf_int(8)
    else:
        return None


class GaiaFrame(Bitfield):
    start: t.Literal[b'\xff'] = b'\xff'
    version: t.Literal[b'\x01'] = b'\x01'
    flags: GaiaFlags = bf_int_enum(GaiaFlags, 8)
    n_bytes_data: int = bf_int(8)
    data: Message = bf_dyn(lambda x: bf_bitfield(
        Message, x.n_bytes_data * 8 + 32)  # 32 for group_id + is_reply + id
    )
    checksum: int | None = bf_dyn(checksum_disc, default=None)
