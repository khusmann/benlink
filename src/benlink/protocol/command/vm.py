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
    UPDATE_SYNC_REQ = 19
    UPDATE_START_REQ = 1
    UPDATE_START_DATA_REQ = 21
    UPDATE_DATA = 4
    UPDATE_IS_VALIDATION_DONE_REQ = 22
    UPDATE_TRANSFER_COMPLETE_RES = 12
    UPDATE_IN_PROGRESS_RES = 14
    UPDATE_ABORT_REQ = 7

    # Replies via VMU_PACKET
    UPDATE_START_CFM = 2
    UPDATE_DATA_BYTES_REQ = 3
    UPDATE_ABORT_CFM = 8
    UPDATE_TRANSFER_COMPLETE_IND = 11
    UPDATE_COMMIT_RES = 15
    UPDATE_SYNC_CFM = 20
    UPDATE_IS_VALIDATION_DONE_CFM = 23
    UPDATE_COMMIT_RES_2 = 29
    VM_UPDATE_ERRORS = 17
    UPDATE_COMPLETE_IND = 18

    # This looks like a fancy way of aborting when
    # you get an error code in the update process
    # looks like you always just send one after the other
    # with the same error code?
    UPDATE_ABORT_WITH_CODE_1_REQ = 31
    UPDATE_ABORT_WITH_CODE_2_REQ = 32

    # Not used in regular firmware update?
    # It seems like there's a hidden debug firmware GUI
    # in the app somewhere that can send these commands
    UPDATE_COMMIT_CFM = 16
    UPDATE_ERASE_SQIF_CFM = 30


class BoolTransform:
    def forward(self, x: int) -> bool:
        return bool(x)

    def back(self, y: bool) -> int:
        return int(y)


bf_bool_byte = bf_map(bf_int(8), BoolTransform())


class VmControlUpdateSyncReq(Bitfield):
    md5sum_tail: bytes = bf_bytes(4)


class VmControlUpdateStartReq(Bitfield):
    pass


class VmControlUpdateDataStartReq(Bitfield):
    pass


class VmControlUpdateData(Bitfield):
    is_final_fragment: bool = bf_bool_byte
    data: bytes = bf_dyn(lambda _, n: bf_bytes(n // 8))


class VmControlUpdateIsValidationDoneReq(Bitfield):
    pass


class VmControlUpdateTransferCompleteRes(Bitfield):
    is_complete: bool = bf_bool_byte


class VmControlUpdateInProgressRes(Bitfield):
    _pad: t.Literal[0] = bf_lit_int(8, default=0)


class VmControlUpdateAbortReq(Bitfield):
    pass


# Messages from VMU_PACKET
class VmControlUpdateDataBytesReq(Bitfield):
    # The max bytes requested that the HT app allows is 250
    n_bytes_requested: int = bf_int(32)
    # Skip allows for resuming a firmware update maybe?
    # I don't see it used in any of my logs
    n_bytes_skip: int = bf_int(32)


def vm_control_disc(m: VmControlBody):
    match m.vm_control_type:
        case VmControlType.UPDATE_SYNC_REQ:
            out = VmControlUpdateSyncReq
        case VmControlType.UPDATE_START_REQ:
            out = VmControlUpdateStartReq
        case VmControlType.UPDATE_START_DATA_REQ:
            out = VmControlUpdateDataStartReq
        case VmControlType.UPDATE_DATA:
            out = VmControlUpdateData
        case VmControlType.UPDATE_IS_VALIDATION_DONE_REQ:
            out = VmControlUpdateIsValidationDoneReq
        case VmControlType.UPDATE_TRANSFER_COMPLETE_RES:
            out = VmControlUpdateTransferCompleteRes
        case VmControlType.UPDATE_IN_PROGRESS_RES:
            out = VmControlUpdateInProgressRes
        case VmControlType.UPDATE_ABORT_REQ:
            out = VmControlUpdateAbortReq
        case VmControlType.UPDATE_DATA_BYTES_REQ:
            out = VmControlUpdateDataBytesReq
        case _:
            return bf_bytes(m.n_bytes_payload)

    return bf_bitfield(out, m.n_bytes_payload*8)


VmControlCommand = t.Union[
    VmControlUpdateSyncReq,
    VmControlUpdateStartReq,
    VmControlUpdateDataStartReq,
    VmControlUpdateData,
    VmControlUpdateIsValidationDoneReq,
    VmControlUpdateTransferCompleteRes,
    VmControlUpdateInProgressRes,
    VmControlUpdateAbortReq,
    VmControlUpdateDataBytesReq,
]


class VmControlBody(Bitfield):
    vm_control_type: VmControlType = bf_int_enum(VmControlType, 8)
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
