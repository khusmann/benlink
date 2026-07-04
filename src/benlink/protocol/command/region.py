"""Region (channel-bank / group) opcodes — verified on VR-N76 fw=147, 2026-07-04.

SET_REGION (60):
- Request body: 1 byte  region_id  (0-based; N76 UI shows 1-based groups)
- Reply body:   1 byte  reply_status (0 = SUCCESS)

READ_REGION_NAME (73):
- Request body: 1 byte  region_id
- Reply body:   1 byte  reply_status
                + 1 byte region_id (echoed)
                + 10 bytes name (null-padded fixed-width string)
  Total 12 bytes on success. If the region_id is out of range the
  radio returns just `05` (INVALID_PARAMETER); parser handles the
  short-reply case in body_disc.

Still unmapped: WRITE_REGION_CH (58), WRITE_REGION_NAME (59).
"""
from __future__ import annotations
from .bitfield import Bitfield, bf_int, bf_int_enum, bf_str, bf_dyn
from .common import ReplyStatus


class SetRegionBody(Bitfield):
    region_id: int = bf_int(8)


class SetRegionReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)


class ReadRegionNameBody(Bitfield):
    region_id: int = bf_int(8)


class _ReadRegionNameSuccessBody(Bitfield):
    region_id: int = bf_int(8)
    name: str = bf_str(10)


def _read_region_name_reply_disc(m: ReadRegionNameReplyBody, n: int):
    if m.reply_status != ReplyStatus.SUCCESS:
        return None
    return _ReadRegionNameSuccessBody


class ReadRegionNameReplyBody(Bitfield):
    reply_status: ReplyStatus = bf_int_enum(ReplyStatus, 8)
    payload: _ReadRegionNameSuccessBody | None = bf_dyn(_read_region_name_reply_disc)
