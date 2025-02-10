from __future__ import annotations
from .bitfield import Bitfield, bf_int_enum, bf_int, bf_bytes, bf_dyn, bf_map, bf_bitfield
from .common import ReplyStatus
from enum import IntEnum

# Order of events in a firmware update:
# 1. VM_CONNECTION
# 2. VM_CONTROL:
#    a. UPDATE_SYNC_REQ (with last 4 bytes of firmware md5sum)
#    b. UPDATE_START_REQ
#    c. UPDATE_DATA_START_REQ
#    d. UPDATE_DATA (repeat until all data is sent)
#    e. UPDATE_DATA (final fragment with is_final_fragment=True)
#    f. UPDATE_IS_VALIDATION_DONE_REQ
#    g. UPDATE_TRANSFER_COMPLETE_RES
# Reboot?
# 3. VM_CONNECT
#    h. UPDATE_SYNC_REQ (with last 4 bytes of firmware md5sum)
#    i. UPDATE_START_REQ
#    j. UPDATE_IN_PROGRESS_RES
# 4. VM_DISCONNECT


class VmControlType(IntEnum):
    # Regular firmware update flow
    UPDATE_SYNC_REQ = 19
    UPDATE_START_REQ = 1
    UPDATE_DATA_START_REQ = 21
    UPDATE_DATA = 4
    UPDATE_IS_VALIDATION_DONE_REQ = 22
    UPDATE_TRANSFER_COMPLETE_RES = 12
    UPDATE_IN_PROGRESS_RES = 14
    UPDATE_ABORT_REQ = 7

    # This looks like a fancy way of aborting when
    # you get an error code in the update process
    # looks like you always just send one after the other
    # with the same error code?
    UPDATE_ABORT_REQ_WITH_CODE1 = 31
    UPDATE_ABORT_REQ_WITH_CODE2 = 32

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


class VmControlUpdateData(Bitfield):
    is_final_fragment: bool = bf_map(bf_int(8), BoolTransform())
    data: bytes = bf_dyn(lambda _, n: bf_bytes(n // 8))


def vm_control_disc(m: VmControlBody):
    match m.vm_control_type:
        case VmControlType.UPDATE_DATA:
            out = VmControlUpdateData
        case _:
            return bf_bytes(m.n_bytes_payload)

    return bf_bitfield(out, m.n_bytes_payload*8)


class VmControlBody(Bitfield):
    vm_control_type: int = bf_int_enum(VmControlType, 8)
    n_bytes_payload: int = bf_int(16)
    data: VmControlUpdateData | bytes = bf_dyn(vm_control_disc)


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
