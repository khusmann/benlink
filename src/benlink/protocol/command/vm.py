from __future__ import annotations
import typing as t
from .bitfield import Bitfield, bf_int_enum, bf_int, bf_bytes, bf_dyn, bf_map, bf_bitfield, bf_lit_int
from .common import ReplyStatus
from enum import IntEnum

#####################################################################
# Order of events in a firmware update:
#
# 1. VM_CONNECT
# 2. VM_CONTROL:
#    a. UPDATE_SYNC (with last 4 bytes of firmware md5sum)
#    b. UPDATE_START
#    c. UPDATE_DATA_START
#    d. UPDATE_DATA (145 bytes at a time. repeat until all data is sent, except for the last fragment)
#    e. UPDATE_DATA (final fragment with is_final_fragment=True)
#    f. UPDATE_IS_VALIDATION_DONE
#    g. UPDATE_TRANSFER_COMPLETE (triggers reboot?)
#
# Reboot happens?
#
# 3. VM_CONNECT
#    h. UPDATE_SYNC (with last 4 bytes of firmware md5sum)
#    i. UPDATE_START
#    j. UPDATE_IN_PROGRESS
# 4. VM_DISCONNECT

#####################################################################
# Order of events in an aborted firmware update:
#
# 1. VM_CONNECT
# 2. VM_CONTROL:
#    a. UPDATE_SYNC (with last 4 bytes of firmware md5sum)
#    b. UPDATE_START
#    c. UPDATE_DATA_START
#    d. UPDATE_DATA (repeat until all data is sent)
#    e. UPDATE_ABORT
# 3. VM_DISCONNECT


class VmControlType(IntEnum):
    # Regular firmware update flow
    UPDATE_SYNC = 19
    UPDATE_START = 1
    UPDATE_DATA_START = 21
    UPDATE_DATA = 4
    UPDATE_IS_VALIDATION_DONE = 22
    UPDATE_TRANSFER_COMPLETE = 12
    UPDATE_IN_PROGRESS = 14
    UPDATE_ABORT_REQ = 7

    # This looks like a fancy way of aborting when
    # you get an error code in the update process
    # looks like you always just send one after the other
    # with the same error code?
    UPDATE_ABORT_WITH_CODE1 = 31
    UPDATE_ABORT_WITH_CODE2 = 32

    # Not used in regular firmware update?
    # It seems like there's a hidden debug firmware GUI
    # in the app somewhere that can send these commands
    UPDATE_COMMIT = 16
    UPDATE_ERASE_SQIF = 30


class BoolTransform:
    def forward(self, x: int) -> bool:
        return bool(x)

    def back(self, y: bool) -> int:
        return int(y)


bf_bool_byte = bf_map(bf_int(8), BoolTransform())


class VmControlUpdateSync(Bitfield):
    md5sum_tail: bytes = bf_bytes(4)


class VmControlUpdateStart(Bitfield):
    pass


class VmControlUpdateDataStart(Bitfield):
    pass


class VmControlUpdateData(Bitfield):
    is_final_fragment: bool = bf_bool_byte
    data: bytes = bf_dyn(lambda _, n: bf_bytes(n // 8))


class VmControlUpdateIsValidationDone(Bitfield):
    pass


class VmControlUpdateTransferComplete(Bitfield):
    is_complete: bool = bf_bool_byte


class VmControlUpdateInProgress(Bitfield):
    _pad: t.Literal[0] = bf_lit_int(8, default=0)


class VmControlUpdateAbortReq(Bitfield):
    pass


def vm_control_disc(m: VmControlBody):
    match m.vm_control_type:
        case VmControlType.UPDATE_SYNC:
            out = VmControlUpdateSync
        case VmControlType.UPDATE_START:
            out = VmControlUpdateStart
        case VmControlType.UPDATE_DATA_START:
            out = VmControlUpdateDataStart
        case VmControlType.UPDATE_DATA:
            out = VmControlUpdateData
        case VmControlType.UPDATE_IS_VALIDATION_DONE:
            out = VmControlUpdateIsValidationDone
        case VmControlType.UPDATE_TRANSFER_COMPLETE:
            out = VmControlUpdateTransferComplete
        case VmControlType.UPDATE_IN_PROGRESS:
            out = VmControlUpdateInProgress
        case VmControlType.UPDATE_ABORT_REQ:
            out = VmControlUpdateAbortReq
        case _:
            return bf_bytes(m.n_bytes_payload)

    return bf_bitfield(out, m.n_bytes_payload*8)


VmControlCommand = t.Union[
    VmControlUpdateSync,
    VmControlUpdateStart,
    VmControlUpdateDataStart,
    VmControlUpdateData,
    VmControlUpdateIsValidationDone,
    VmControlUpdateTransferComplete,
    VmControlUpdateInProgress,
    VmControlUpdateAbortReq,
]


class VmControlBody(Bitfield):
    vm_control_type: int = bf_int_enum(VmControlType, 8)
    n_bytes_payload: int = bf_int(16)
    command: VmControlCommand | bytes = bf_dyn(vm_control_disc)


class VmControlReplyBody(Bitfield):
    status: ReplyStatus = bf_int_enum(ReplyStatus, 8)


class VmConnectBody(Bitfield):
    pass


class VmConnectReplyBody(Bitfield):
    status: ReplyStatus = bf_int_enum(ReplyStatus, 8)


class VmDisconnectBody(Bitfield):
    pass


class VmDisconnectReplyBody(Bitfield):
    status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
