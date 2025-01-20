from enum import IntEnum
from .bitfield import Bitfield, bf_int, bf_dyn, bf_bytes


class ReplyStatus(IntEnum):
    SUCCESS = 0
    NOT_SUPPORTED = 1
    NOT_AUTHENTICATED = 2
    INSUFFICIENT_RESOURCES = 3
    AUTHENTICATING = 4
    INVALID_PARAMETER = 5
    INCORRECT_STATE = 6
    IN_PROGRESS = 7


class TncDataFragment(Bitfield):
    is_final_fragment: bool
    with_channel_id: bool
    fragment_id: int = bf_int(6)
    data: bytes = bf_dyn(
        lambda x, n: bf_bytes((n - 1 if x.with_channel_id else n) // 8)
    )
    channel_id: int | None = bf_dyn(
        lambda x: bf_int(8) if x.with_channel_id else None
    )
