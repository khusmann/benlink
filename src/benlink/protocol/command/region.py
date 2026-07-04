"""SET_REGION protocol body — verified on VR-N76 fw=147, 2026-07-04.

Wire shape (as confirmed by scripts/t3_1_set_region_probe.py):
- Command:      SET_REGION (60)
- Request body: 1 byte  region_id  (0-based; N76 UI shows 1-based groups)
- Reply body:   1 byte  reply_status (0 = SUCCESS)

The corresponding channel-table opcodes (READ_REGION_NAME=73,
WRITE_REGION_CH=58, WRITE_REGION_NAME=59) are still unmapped and will
land in follow-up commits.
"""
from __future__ import annotations
from .bitfield import Bitfield, bf_int, bf_int_enum
from .common import ReplyStatus


class SetRegionBody(Bitfield):
    region_id: int = bf_int(8)


class SetRegionReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
