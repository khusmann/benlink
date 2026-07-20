"""Wire format for the vendor's firmware update RPC.

The update server speaks gRPC, but only one method matters and its messages are
small, so they are encoded by hand rather than through protoc. That keeps the
schema readable in source, avoids a protobuf runtime dependency, and avoids
checked-in generated code that stops working on a future protobuf major release.

The `DeviceManagement` service has three methods (`CheckFirmwareUpdate`,
`GetRegTimes`, `SetRegTimes`); only the firmware check is modelled here. Field
numbers are the contract, and the names follow the vendor's.

    syntax = "proto3";

    package benshikj;

    message CheckFirmwareUpdateRequest {
      int32 product_id       = 1;
      int32 firmware_version = 2;
      bool  beta             = 3;
      int64 user_id          = 4;
      int32 invite_code      = 5;
    }

    message FirmwareInfo {
      int32  version       = 1;
      string url           = 2;
      string md5           = 3;
      string release_notes = 4;
      string release_date  = 5;
    }

    message CheckFirmwareUpdateResult {
      FirmwareInfo firmware = 1;
      FirmwareInfo base     = 2;
    }

    service DeviceManagement {
      rpc CheckFirmwareUpdate(CheckFirmwareUpdateRequest)
          returns (CheckFirmwareUpdateResult);
    }

Note that `md5` does not describe the file at `url`: for the patch it is the md5
of the *assembled* firmware, and for the base it is the md5 of the `.bin` inside
the zip.
"""

from __future__ import annotations
import typing as t

METHOD = "/benshikj.DeviceManagement/CheckFirmwareUpdate"

WIRE_VARINT = 0
"""@private"""

WIRE_BYTES = 2
"""@private"""


class FirmwareInfo(t.NamedTuple):
    """A decoded `benshikj.FirmwareInfo`."""
    version: int = 0
    url: str = ""
    md5: str = ""


class CheckFirmwareUpdateResult(t.NamedTuple):
    """A decoded `benshikj.CheckFirmwareUpdateResult`."""
    firmware: FirmwareInfo = FirmwareInfo()
    base: FirmwareInfo = FirmwareInfo()


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _encode_varint_field(field: int, value: int) -> bytes:
    return _encode_varint(field << 3 | WIRE_VARINT) + _encode_varint(value)


def _read_varint(data: bytes, pos: int) -> t.Tuple[int, int]:
    value = shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return value, pos


def _walk(data: bytes) -> t.Iterator[t.Tuple[int, int, int, bytes]]:
    """Yield `(field_number, wire_type, varint_value, delimited_value)`.

    Only one of the two values is meaningful, according to the wire type.
    Unrecognised wire types end the walk, since their length is unknown.
    """
    pos = 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field, wire = tag >> 3, tag & 0x7

        if wire == WIRE_VARINT:
            value, pos = _read_varint(data, pos)
            yield field, wire, value, b""
        elif wire == WIRE_BYTES:
            length, pos = _read_varint(data, pos)
            yield field, wire, 0, data[pos:pos + length]
            pos += length
        elif wire == 5:
            pos += 4
        elif wire == 1:
            pos += 8
        else:
            return


def encode_check_request(product_id: int, firmware_version: int = 0) -> bytes:
    """Encode a `CheckFirmwareUpdateRequest`.

    proto3 omits zero-valued fields, so a request carrying only a product id asks
    for the latest release.
    """
    out = b""
    if product_id:
        out += _encode_varint_field(1, product_id)
    if firmware_version:
        out += _encode_varint_field(2, firmware_version)
    return out


def _decode_firmware_info(data: bytes) -> FirmwareInfo:
    version, url, md5 = 0, "", ""
    for field, wire, varint, delimited in _walk(data):
        if field == 1 and wire == WIRE_VARINT:
            version = varint
        elif field == 2 and wire == WIRE_BYTES:
            url = delimited.decode("utf-8", "replace")
        elif field == 3 and wire == WIRE_BYTES:
            md5 = delimited.decode("utf-8", "replace")
    return FirmwareInfo(version=version, url=url, md5=md5)


def decode_check_result(data: bytes) -> CheckFirmwareUpdateResult:
    """Decode a `CheckFirmwareUpdateResult`. Absent fields decode as empty."""
    firmware = base = FirmwareInfo()
    for field, wire, _, delimited in _walk(data):
        if wire != WIRE_BYTES:
            continue
        if field == 1:
            firmware = _decode_firmware_info(delimited)
        elif field == 2:
            base = _decode_firmware_info(delimited)
    return CheckFirmwareUpdateResult(firmware=firmware, base=base)
