import io
import zipfile

import pytest

from benlink.firmware import _benshikj
from benlink.firmware import (
    PRODUCTS,
    FirmwareBundle,
    FirmwareInfo,
    UpdateInfo,
    assemble,
    extract_base,
    oss_base_url,
    oss_patch_url,
    oss_update_info,
)

bsdiff4 = pytest.importorskip("bsdiff4")


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _delimited(field: int, payload: bytes) -> bytes:
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def _firmware_info_bytes(info: _benshikj.FirmwareInfo) -> bytes:
    return (
        _varint(1 << 3) + _varint(info.version)
        + _delimited(2, info.url.encode())
        + _delimited(3, info.md5.encode())
    )


def test_encode_check_request():
    # Field numbers are the wire contract: product_id is field 1, varint.
    assert _benshikj.encode_check_request(259) == b"\x08\x83\x02"
    assert _benshikj.encode_check_request(259, 147) == b"\x08\x83\x02\x10\x93\x01"
    # proto3 omits zero-valued fields
    assert _benshikj.encode_check_request(0) == b""


def test_encode_decode_roundtrip():
    info = _benshikj.FirmwareInfo(147, "https://example.invalid/p.bin", "abc")
    encoded = _delimited(1, _firmware_info_bytes(info))
    decoded = _benshikj.decode_check_result(encoded)
    assert decoded.firmware == info
    assert decoded.base == _benshikj.FirmwareInfo()


def test_decode_stops_on_unknown_wire_type():
    # tag with wire type 7 (invalid); the walk must not loop or raise
    assert _benshikj.decode_check_result(b"\x0f\x01\x02") == (
        _benshikj.CheckFirmwareUpdateResult()
    )


def test_update_info_from_protocol():
    result = _benshikj.CheckFirmwareUpdateResult(
        firmware=_benshikj.FirmwareInfo(
            version=147,
            url="https://example.invalid/patch.bin",
            md5="0c0d095da50bebe664822adcb244834a",
        ),
        base=_benshikj.FirmwareInfo(
            url="https://example.invalid/base.zip",
            md5="74b6d097d8d2d9d2d9fac88133198a08",
        ),
    )

    assert UpdateInfo.from_protocol(result) == UpdateInfo(
        firmware=FirmwareInfo(
            version=147,
            url="https://example.invalid/patch.bin",
            md5="0c0d095da50bebe664822adcb244834a",
        ),
        base=FirmwareInfo(
            version=0,
            url="https://example.invalid/base.zip",
            md5="74b6d097d8d2d9d2d9fac88133198a08",
        ),
    )


def test_update_info_from_protocol_empty_means_no_update():
    empty = _benshikj.CheckFirmwareUpdateResult()
    assert UpdateInfo.from_protocol(empty) is None


def test_oss_urls():
    assert oss_patch_url(147, "patch_base_to_vr_n76").endswith(
        "/firmware/v147/patch_base_to_vr_n76.bin")
    assert oss_patch_url(147, "custom").endswith("/firmware/v147/custom.bin")
    assert oss_base_url("original").endswith("/upgrade_base.bin.zip")
    assert oss_base_url("1").endswith("/upgrade_base_v1.bin.zip")


def test_oss_base_url_rejects_unknown_base():
    with pytest.raises(RuntimeError, match="unknown base image"):
        oss_base_url("2")


def test_oss_update_info():
    info = oss_update_info(147, "patch_base_to_vr_n76", "1")
    assert info.firmware.url.endswith("/firmware/v147/patch_base_to_vr_n76.bin")
    assert info.base.url.endswith("/upgrade_base_v1.bin.zip")
    assert info.firmware.md5 is None


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


def test_extract_base():
    raw = b"not a zip"
    assert extract_base(raw) == raw

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("upgrade_base.bin", b"inner")
    assert extract_base(buf.getvalue()) == b"inner"


def test_extract_base_rejects_zip_without_bin():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"nope")
    with pytest.raises(RuntimeError, match="no .bin found"):
        extract_base(buf.getvalue())


def test_assemble_against_wrong_base_is_not_detected():
    # BSDIFF40 carries no checksum of its source, so the wrong base yields a
    # plausible but corrupt image. Callers must verify the assembled result.
    base = b"the quick brown fox" * 100
    other = b"a completely different base" * 100
    patch = bsdiff4.diff(base, b"target" * 100)

    assert assemble(other, patch) != b"target" * 100


def test_assemble_rejects_bad_patch_magic():
    with pytest.raises(RuntimeError, match="unexpected patch magic"):
        assemble(b"base", b"NOTAPATCH" + b"\x00" * 32)


def test_resolve_product():
    from argparse import Namespace

    from benlink.firmware.__main__ import _resolve_product

    assert _resolve_product(
        Namespace(product="UV_PRO", product_id=None, patch_name=None)
    ) == PRODUCTS["UV_PRO"]

    # explicit flags override either half of --product
    assert _resolve_product(
        Namespace(product="UV_PRO", product_id=999, patch_name=None)
    ) == (999, PRODUCTS["UV_PRO"][1])

    assert _resolve_product(
        Namespace(product="UV_PRO", product_id=None, patch_name="custom")
    ) == (PRODUCTS["UV_PRO"][0], "custom")

    assert _resolve_product(
        Namespace(product=None, product_id=None, patch_name=None)
    ) == (None, None)


def test_ga5wb_shares_vr_n76_patch_series():
    # Confirmed against a GA-5WB flash capture; see PRODUCTS docstring.
    assert PRODUCTS["GA_5WB"] == PRODUCTS["VR_N76"]


def test_bundle_md5_tail():
    bundle = FirmwareBundle(
        data=b"hello",
        update_info=oss_update_info(1, "patch_base_to_vr_n76", "1"),
    )
    assert bundle.md5 == "5d41402abc4b2a76b9719d911017c592"
    assert bundle.md5_tail == bytes.fromhex("1017c592")
    assert bundle.size == 5
