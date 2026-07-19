import io
import zipfile

import pytest

from benlink.firmware import (
    DEFAULT_PATCH_NAME,
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
pytest.importorskip("google.protobuf")

from benlink.firmware import _benshikj_pb2  # noqa: E402


def test_request_field_numbers():
    # The field numbers are the wire contract; the names are ours.
    request = _benshikj_pb2.CheckFirmwareUpdateRequest(product_id=259)
    assert request.SerializeToString() == b"\x08\x83\x02"


def test_update_info_from_protocol():
    result = _benshikj_pb2.CheckFirmwareUpdateResult(
        firmware=_benshikj_pb2.FirmwareInfo(
            version=147,
            url="https://example.invalid/patch.bin",
            md5="0c0d095da50bebe664822adcb244834a",
        ),
        base=_benshikj_pb2.FirmwareInfo(
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
    assert UpdateInfo.from_protocol(_benshikj_pb2.CheckFirmwareUpdateResult()) is None


def test_oss_urls():
    assert oss_patch_url(147).endswith("/firmware/v147/patch_base_to_vr_n76.bin")
    assert oss_patch_url(147, "custom").endswith("/firmware/v147/custom.bin")
    assert oss_base_url("original").endswith("/upgrade_base.bin.zip")
    assert oss_base_url("1").endswith("/upgrade_base_v1.bin.zip")


def test_oss_base_url_rejects_unknown_base():
    with pytest.raises(RuntimeError, match="unknown base image"):
        oss_base_url("2")


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
    ) == (None, DEFAULT_PATCH_NAME)


def test_ga5wb_shares_vr_n76_patch_series():
    # Confirmed against a GA-5WB flash capture; see PRODUCTS docstring.
    assert PRODUCTS["GA_5WB"] == PRODUCTS["VR_N76"]


def test_bundle_md5_tail():
    bundle = FirmwareBundle(data=b"hello", update_info=oss_update_info(1))
    assert bundle.md5 == "5d41402abc4b2a76b9719d911017c592"
    assert bundle.md5_tail == bytes.fromhex("1017c592")
    assert bundle.size == 5
