from __future__ import annotations
from enum import IntFlag
import typing as t

from .bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_bytes

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
    n_bytes_payload: int = bf_int(8)
    data: bytes = bf_dyn(lambda x: bf_bytes(
        x.n_bytes_data + 4  # Full data length is 4 command bytes + n_bytes_payload
    ))
    checksum: int | None = bf_dyn(checksum_disc, default=None)
