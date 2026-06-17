from __future__ import annotations
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_lit_int, bf_str, bf_map
from .common import ReplyStatus
import typing as t


class CountdownMapper:
    """16-bit seconds-until-event; 0xFFFF == unknown/none, 0 == now/past."""

    def forward(self, x: int) -> int | None:
        return x if x != 0xFFFF else None

    def back(self, y: int | None) -> int:
        return y if y is not None else 0xFFFF


class SetSatelliteInfoBody(Bitfield):
    # Fixed 30-byte payload. Name occupies the first 20 bytes; the firmware
    # app encodes it as GB2312 (identical to ASCII for names like "ISS",
    # "AO-91"; diverges only for non-ASCII characters). NUL-padded.
    name: str = bf_str(20, "gb2312")

    # Azimuth, integer degrees 0-359 (9 bits), then 7 reserved bits.
    azimuth: int = bf_int(9)
    _pad_az: t.Literal[0] = bf_lit_int(7, default=0)

    # Elevation, integer degrees (8 bits, written unsigned by the app's
    # tracking path), then 8 reserved bits.
    elevation: int = bf_int(8)
    _pad_el: t.Literal[0] = bf_lit_int(8, default=0)

    # Slant range to the satellite, km (firmware clamps >65535 to 0).
    range_km: int = bf_int(16)

    # Satellite orbital altitude, km (firmware clamps >65535 to 0).
    altitude_km: int = bf_int(16)

    # Seconds until the next tracked event; 0xFFFF == unknown.
    countdown_secs: int | None = bf_map(bf_int(16), CountdownMapper())


class SetSatelliteInfoReplyBody(Bitfield):
    # Inferred from the SET_* convention (bare ReplyStatus ack, like
    # SetPhoneStatusReplyBody). No dedicated reply parser is present in the
    # decompile; worth confirming against one on-air capture.
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
