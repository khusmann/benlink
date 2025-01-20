from __future__ import annotations
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_dyn, bf_map, bf_lit_int, Scale, bf_str
import typing as t
from enum import IntEnum
from .common import ReplyStatus


class ModulationType(IntEnum):
    FM = 0
    AM = 1
    DMR = 2


class BandwidthType(IntEnum):
    NARROW = 0
    WIDE = 1


class DCS(t.NamedTuple):
    n: int


class SubAudioMap:
    def forward(self, x: int):
        if x == 0:
            return None

        return DCS(x) if x < 6700 else x / 100

    def back(self, y: DCS | float | None):
        match y:
            case None:
                return 0
            case DCS(n=n):
                if n >= 6700 or n <= 0:
                    raise ValueError(f"Invalid DCS value: {n}")
                return n
            case _:
                if y < 67 or y > 254.1:
                    raise ValueError(f"Invalid subaudio value: {y}")
                return round(y*100)


class RfCh(Bitfield):
    channel_id: int = bf_int(8)
    tx_mod: ModulationType = bf_int_enum(ModulationType, 2)
    tx_freq: float = bf_map(bf_int(30), Scale(1e-6, 6))
    rx_mod: ModulationType = bf_int_enum(ModulationType, 2)
    rx_freq: float = bf_map(bf_int(30), Scale(1e-6, 6))
    tx_sub_audio: float | DCS | None = bf_map(bf_int(16), SubAudioMap())
    rx_sub_audio: float | DCS | None = bf_map(bf_int(16), SubAudioMap())
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType = bf_int_enum(BandwidthType, 1)
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwidth: bool
    fixed_tx_power: bool
    mute: bool
    _pad: t.Literal[0] = bf_lit_int(4, default=0)
    name_str: str = bf_str(10)


class RfChDMR(RfCh):
    tx_color: int = bf_int(4)
    rx_color: int = bf_int(4)
    slot: int = bf_int(1)
    _pad2: t.Literal[0] = bf_lit_int(7, default=0)


def channel_settings_reply_disc(body: ReadRFChReplyBody, n: int):
    if body.reply_status != ReplyStatus.SUCCESS:
        return None
    return channel_settings_disc(body, n)


def channel_settings_disc(_: ReadRFChReplyBody | WriteRFChBody, n: int):
    # Note: in the app, this is detected via support_dmr in
    # device settings. But for simplicity, I'm just going to
    # use the size of the bitfield.
    if n == RfCh.length():
        return RfCh

    if n == RfChDMR.length():
        return RfChDMR

    raise ValueError(f"Unknown channel settings type (size {n})")


class ReadRFChBody(Bitfield):
    channel_id: int = bf_int(8)


class ReadRFChReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    rf_ch: RfCh | RfChDMR | None = bf_dyn(
        channel_settings_reply_disc
    )


class WriteRFChBody(Bitfield):
    rf_ch: RfCh | RfChDMR = bf_dyn(
        channel_settings_disc
    )


class WriteRFChReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    channel_id: int = bf_int(8)
