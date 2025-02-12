from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_dyn, bf_bytes, bf_bitfield
from enum import IntEnum
from .vm import VmuPacket

#################################################
# BT_EVENT_NOTIFICATION


class BtEventType(IntEnum):
    START = 0
    RSSI_LOW_THRESHOLD = 1
    RSSI_HIGH_THRESHOLD = 2
    BATTERY_LOW_THRESHOLD = 3
    BATTERY_HIGH_THRESHOLD = 4
    DEVICE_STATE_CHANGED = 5
    PIO_CHANGED = 6
    DEBUG_MESSAGE = 7
    BATTERY_CHARGED = 8
    CHARGER_CONNECTION = 9
    CAPSENSE_UPDATE = 10
    USER_ACTION = 11
    SPEECH_RECOGNITION = 12
    AV_COMMAND = 13
    REMOTE_BATTERY_LEVEL = 14
    KEY = 15
    DFU_STATE = 16
    UART_RECEIVED_DATA = 17
    VMU_PACKET = 18


def bt_event_disc(m: BtEventNotificationBody, n: int):
    match m.bt_event_type:
        case BtEventType.VMU_PACKET:
            out = VmuPacket
        case _:
            return bf_bytes(n // 8)

    return bf_bitfield(out, n)


class BtEventNotificationBody(Bitfield):
    bt_event_type: BtEventType = bf_int_enum(BtEventType, 8)
    bt_event: VmuPacket | bytes = bf_dyn(bt_event_disc)
