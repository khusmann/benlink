import io
import zipfile

import pytest

from benlink.firmware import (
    FirmwareBundle,
    FirmwareInfo,
    UpdateInfo,
    _decode_fields,
    _encode_varint,
    _encode_varint_field,
    _parse_check_result,
    assemble,
    oss_update_info,
)

bsdiff4 = pytest.importorskip("bsdiff4")


def test_encode_varint():
    assert _encode_varint(0) == b"\x00"
    assert _encode_varint(1) == b"\x01"
    assert _encode_varint(127) == b"\x7f"
    assert _encode_varint(128) == b"\x80\x01"
    assert _encode_varint(259) == b"\x83\x02"


def test_encode_varint_field():
    # field 1, wire type 0, value 259
    assert _encode_varint_field(1, 259) == b"\x08\x83\x02"


def test_decode_fields_roundtrip():
    data = _encode_varint_field(1, 259) + _encode_varint_field(2, 147)
    assert [(f, w) for f, w, _ in _decode_fields(data)] == [(1, 0), (2, 0)]


def _string_field(field: int, value: str) -> bytes:
    raw = value.encode()
    return _encode_varint(field << 3 | 2) + _encode_varint(len(raw)) + raw


def _message_field(field: int, value: bytes) -> bytes:
    return _encode_varint(field << 3 | 2) + _encode_varint(len(value)) + value


def test_parse_check_result():
    firmware = (
        _encode_varint_field(1, 147)
        + _string_field(2, "https://example.invalid/patch.bin")
        + _string_field(3, "0c0d095da50bebe664822adcb244834a")
    )
    base = (
        _encode_varint_field(1, 1)
        + _string_field(2, "https://example.invalid/base.zip")
        + _string_field(3, "74b6d097d8d2d9d2d9fac88133198a08")
    )

    result = _parse_check_result(
        _message_field(1, firmware) + _message_field(2, base)
    )

    assert result == UpdateInfo(
        firmware=FirmwareInfo(
            version=147,
            url="https://example.invalid/patch.bin",
            md5="0c0d095da50bebe664822adcb244834a",
        ),
        base=FirmwareInfo(
            version=1,
            url="https://example.invalid/base.zip",
            md5="74b6d097d8d2d9d2d9fac88133198a08",
        ),
    )


def test_parse_check_result_empty_means_no_update():
    assert _parse_check_result(b"") is None


def test_oss_update_info():
    info = oss_update_info(147)
    assert info.firmware.url.endswith("/firmware/v147/patch_base_to_vr_n76.bin")
    assert info.base.url.endswith("/upgrade_base_v1.bin.zip")
    assert info.firmware.md5 == ""


def test_assemble_raw_base():
    base = b"the quick brown fox" * 100
    expected = b"the slow brown fox" * 100
    assert assemble(base, bsdiff4.diff(base, expected)) == expected


def test_assemble_zipped_base():
    base = b"the quick brown fox" * 100
    expected = b"the slow brown fox" * 100

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("upgrade_base.bin", base)

    assert assemble(buf.getvalue(), bsdiff4.diff(base, expected)) == expected


def test_assemble_rejects_bad_patch_magic():
    with pytest.raises(RuntimeError, match="unexpected patch magic"):
        assemble(b"base", b"NOTAPATCH" + b"\x00" * 32)


def test_bundle_md5_tail():
    bundle = FirmwareBundle(data=b"hello", update_info=oss_update_info(1))
    assert bundle.md5 == "5d41402abc4b2a76b9719d911017c592"
    assert bundle.md5_tail == bytes.fromhex("1017c592")
    assert bundle.size == 5
