from __future__ import annotations
from .bitfield import (
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
from .settings import Settings
from .rf_ch import RfCh
from .common import TncDataFragment

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


class HTSettingsChangedEvent(Bitfield):
    settings: Settings


class DataRxdEvent(Bitfield):
    tnc_data_fragment: TncDataFragment = bf_dyn(
        lambda _, n: bf_bitfield(TncDataFragment, n)
    )


class Status(Bitfield):
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType = bf_int_enum(ChannelType, 2)
    is_scan: bool
    is_radio: bool
    curr_ch_id_lower: int = bf_int(4)
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    _pad: t.Literal[0] = bf_lit_int(1, default=0)


class StatusExt(Status):
    rssi: float = bf_map(bf_int(4), Scale(100 / 15))
    curr_region: int = bf_int(6)
    curr_channel_id_upper: int = bf_int(4)
    _pad2: t.Literal[0] = bf_lit_int(2, default=0)


def status_disc(m: Status, n: int):
    if n == StatusExt.length():
        return StatusExt
    if n == Status.length():
        return Status
    raise ValueError(f"Unknown size for status type: {n}")


class HTStatusChangedEvent(Bitfield):
    status: Status | StatusExt = bf_dyn(status_disc)


class UnknownEvent(Bitfield):
    data: bytes = bf_dyn(lambda _, n: bf_bytes(n // 8))


class HTChChangedEvent(Bitfield):
    rf_ch: RfCh


def event_notification_disc(m: EventNotificationBody, n: int):
    match m.event_type:
        case EventType.HT_SETTINGS_CHANGED:
            return HTSettingsChangedEvent
        case EventType.HT_STATUS_CHANGED:
            return bf_bitfield(HTStatusChangedEvent, n)
        case EventType.DATA_RXD:
            return bf_bitfield(DataRxdEvent, n)
        case EventType.HT_CH_CHANGED:
            return HTChChangedEvent
        case _:
            return bf_bitfield(UnknownEvent, n)


Event = t.Union[
    UnknownEvent,
    DataRxdEvent,
    HTStatusChangedEvent,
    HTSettingsChangedEvent,
    HTChChangedEvent,
]


class EventNotificationBody(Bitfield):
    event_type: EventType = bf_int_enum(EventType, 8)
    event: Event = bf_dyn(
        event_notification_disc
    )


class RegisterNotificationBody(Bitfield):
    event_type: EventType = bf_int_enum(EventType, 8)
