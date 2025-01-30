from __future__ import annotations
from .bitfield import (
    Bitfield,
    bf_int_enum,
    bf_dyn,
    bf_bytes,
    bf_bitfield,
)
import typing as t
from .settings import Settings
from .rf_ch import RfCh
from .common import TncDataFragment
from .status import Status, StatusExt

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


class HTSettingsChangedEvent(Bitfield):
    settings: Settings


class DataRxdEvent(Bitfield):
    tnc_data_fragment: TncDataFragment = bf_dyn(
        lambda _, n: bf_bitfield(TncDataFragment, n)
    )


def status_disc(_: HTSettingsChangedEvent, n: int):
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
