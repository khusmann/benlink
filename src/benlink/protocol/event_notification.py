from __future__ import annotations
from ..bitfield import (
    Bitfield,
    bf_int,
    bf_int_enum,
    bf_dyn,
    bf_bytes,
    bf_lit_int,
    bf_map,
    bf_bitfield,
    Scale,
)
import typing as t
from .settings import RadioSettings

from enum import IntEnum


class EventType(IntEnum):
    UNKNOWN = 0
    HT_STATUS_CHANGED = 1
    DATA_RXD = 2  # Received APRS or BSS Message
    NEW_INQUIRY_DATA = 3
    RESTORE_FACTORY_SETTINGS = 4
    HT_CH_CHANGED = 5
    HT_SETTINGS_CHANGED = 6
    RINGING_STOPPED = 7
    RADIO_STATUS_CHANGED = 8
    USER_ACTION = 9
    SYSTEM_EVENT = 10
    BSS_SETTINGS_CHANGED = 11


class ChannelType(IntEnum):
    OFF = 0
    A = 1
    B = 2


class HTSettingsChanged(Bitfield):
    radio_settings: RadioSettings


class HTStatusChanged(Bitfield):
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType = bf_int_enum(ChannelType, 2)
    is_scan: bool
    is_radio: bool
    curr_ch_id: int = bf_int(4)
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)


class HTStatusChangedExt(Bitfield):
    curr_channel_id: int = bf_int(8)
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType = bf_int_enum(ChannelType, 2)
    is_scan: bool
    is_radio: bool
    # curr_ch_id_lower (reordered; 4)
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)
    rssi: float = bf_map(bf_int(4), Scale(100 / 15))
    curr_region: int = bf_int(6)
    # curr_channel_id_upper (reordered; 4)
    _pad2: t.Literal[0] = bf_lit_int(2, default=0)

    _reorder = [*range(26, 26+4), *range(8, 8+4)]


class UnknownEvent(Bitfield):
    data: bytes = bf_dyn(lambda _, n: bf_bytes(n // 8))


class DataPacket(Bitfield):
    is_final_packet: bool
    with_channel_id: bool
    packet_id: int = bf_int(6)
    data: bytes = bf_dyn(
        lambda x, n: bf_bytes((n - 1 if x.with_channel_id else n) // 8)
    )
    channel_id: int | None = bf_dyn(
        lambda x: bf_int(8) if x.with_channel_id else None
    )


def event_notification_disc(m: EventNotificationBody, n: int):
    match m.event_type:
        case EventType.HT_SETTINGS_CHANGED:
            return HTSettingsChanged
        case EventType.HT_STATUS_CHANGED:
            if n == HTStatusChanged.length():
                return HTStatusChanged
            if n == HTStatusChangedExt.length():
                return HTStatusChangedExt
            raise ValueError(
                f"Unknown size for HT_STATUS_CHANGED event ({n})"
            )
        case EventType.DATA_RXD:
            return bf_bitfield(DataPacket, n)
        case _:
            return bf_bitfield(UnknownEvent, n)


Event = t.Union[
    UnknownEvent,
    DataPacket,
    HTStatusChanged,
    HTSettingsChanged,
    HTStatusChangedExt,
]


class EventNotificationBody(Bitfield):
    event_type: EventType = bf_int_enum(EventType, 8)
    event: Event = bf_dyn(
        event_notification_disc
    )
