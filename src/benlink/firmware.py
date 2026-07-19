"""
# Overview

Firmware update support for Benshi radios.

This module is deliberately excluded from `benlink`'s default namespace. Flashing
firmware can brick a radio, so it must be imported explicitly:

```python
import benlink.firmware
```

Firmware is distributed as a shared **base image** plus a per-release **patch** in
BSDIFF40 format. Assembling the two yields the image the radio expects. Neither is
redistributed by benlink — both are fetched from the vendor's servers at the user's
request.

Two ways to find an image:

1. Ask the vendor's update server what the latest release is for a given product id
   (`check_update`). Requires `grpcio`, and returns md5s that let the assembled image
   be verified.
2. Address the object store directly by version number (`oss_update_info`). Needs no
   RPC and no product id, which keeps this module working if the update server
   changes.

# CLI

```bash
python -m benlink.firmware check    --product-id 259
python -m benlink.firmware fetch    --product-id 259 -o fw.bin
python -m benlink.firmware fetch    --version 147 -o fw.bin
python -m benlink.firmware assemble --base upgrade_base.bin --patch patch.bin -o fw.bin
```

`assemble` is fully offline. `check` and `fetch --product-id` contact the update
server; `fetch --version` contacts only the object store.

# Notes

The product id is read from the radio via `GET_DEV_INFO` (`DeviceInfo.product_id`).
It is not unique across vendors — the VR-N76 and GA-5WB both report 259.
"""

from __future__ import annotations
import typing as t
import argparse
import asyncio
import hashlib
import io
import sys
import urllib.request
import zipfile

OSS_BASE_URL = "https://pubdatas.oss-cn-shenzhen.aliyuncs.com"
"""@private"""

RPC_HOST = "rpc.benshikj.com:800"
"""@private"""

RPC_METHOD = "/benshikj.DeviceManagement/CheckFirmwareUpdate"
"""@private"""

RPC_TIMEOUT = 10.0
"""@private"""

DEFAULT_PATCH_NAME = "patch_base_to_vr_n76"
"""Patch filename for the VR-N76 / GA-5WB. The UV-Pro uses `patch_base_to_vr_n76_m`."""

DEFAULT_BASE_VERSION = 1
"""Base image version. Independent of the firmware version; shared across releases."""


def _require(module: str, package: str):
    try:
        return __import__(module)
    except ImportError:
        raise ImportError(
            f"{package} is required for this operation. "
            f"Install with: pip install benlink[firmware]"
        )


#####################
# proto3 wire format
#
# The update server speaks gRPC, but only two message shapes are needed, so they are
# encoded by hand rather than taking a protoc dependency:
#
#   CheckFirmwareUpdateRequest { productId=1, firmwareVersion=2, beta=3,
#                                userId=4, inviteCode=5 }
#   CheckFirmwareUpdateResult  { firmware:FirmwareInfo=1, base:FirmwareInfo=2 }
#   FirmwareInfo               { version=1, url=2, md5=3,
#                                releaseNotes=4, releaseDate=5 }
#
# proto3 omits zero-valued fields, so sending productId alone requests the latest
# release.

def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _encode_varint_field(field: int, value: int) -> bytes:
    return _encode_varint(field << 3) + _encode_varint(value)


def _decode_fields(data: bytes) -> t.Iterator[t.Tuple[int, int, bytes]]:
    pos = 0

    def read_varint() -> int:
        nonlocal pos
        value = shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                break
            shift += 7
        return value

    while pos < len(data):
        tag = read_varint()
        field, wire_type = tag >> 3, tag & 0x7
        match wire_type:
            case 0:
                yield field, wire_type, _encode_varint(read_varint())
            case 1:
                yield field, wire_type, data[pos:pos + 8]
                pos += 8
            case 2:
                length = read_varint()
                yield field, wire_type, data[pos:pos + length]
                pos += length
            case 5:
                yield field, wire_type, data[pos:pos + 4]
                pos += 4
            case _:
                return


def _decode_varint(data: bytes) -> int:
    value = shift = 0
    for byte in data:
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return value


#####################
# Data

class FirmwareInfo(t.NamedTuple):
    """One downloadable artifact (either the patch or the base image)."""
    version: int
    url: str
    md5: str


class UpdateInfo(t.NamedTuple):
    """The patch and base image that together make up a firmware release."""
    firmware: FirmwareInfo
    base: FirmwareInfo


class FirmwareBundle(t.NamedTuple):
    """An assembled, ready-to-flash firmware image."""
    data: bytes
    update_info: UpdateInfo

    @property
    def md5(self) -> str:
        return hashlib.md5(self.data).hexdigest()

    @property
    def md5_tail(self) -> bytes:
        """Last 4 bytes of the md5 digest, as sent in `UPDATE_SYNC_REQ`."""
        return bytes.fromhex(self.md5)[-4:]

    @property
    def size(self) -> int:
        return len(self.data)

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.data)


ProgressCallback = t.Callable[[str, int, int], None]
"""`progress(label, bytes_done, bytes_total)`. `bytes_total` is 0 if unknown."""


#####################
# Finding an update

def _parse_firmware_info(data: bytes) -> FirmwareInfo:
    version, url, md5 = 0, "", ""
    for field, _, value in _decode_fields(data):
        match field:
            case 1:
                version = _decode_varint(value)
            case 2:
                url = value.decode("utf-8")
            case 3:
                md5 = value.decode("utf-8")
    return FirmwareInfo(version=version, url=url, md5=md5)


def _parse_check_result(data: bytes) -> UpdateInfo | None:
    firmware = base = None
    for field, _, value in _decode_fields(data):
        match field:
            case 1:
                firmware = _parse_firmware_info(value)
            case 2:
                base = _parse_firmware_info(value)
    if firmware is None or base is None or not firmware.url or not base.url:
        return None
    return UpdateInfo(firmware=firmware, base=base)


async def check_update(
    product_id: int,
    firmware_version: int = 0,
) -> UpdateInfo | None:
    """Ask the update server for the latest release for `product_id`.

    `firmware_version` is the currently installed internal version; leaving it at 0
    always returns the latest. Returns `None` if the server reports no update.

    Requires `grpcio`.
    """
    grpc = _require("grpc", "grpcio")

    request = _encode_varint_field(1, product_id)
    if firmware_version:
        request += _encode_varint_field(2, firmware_version)

    credentials = grpc.ssl_channel_credentials()
    async with grpc.aio.secure_channel(RPC_HOST, credentials) as channel:
        call = channel.unary_unary(
            RPC_METHOD,
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        try:
            response: bytes = await call(request, timeout=RPC_TIMEOUT)
        except grpc.aio.AioRpcError as e:
            raise RuntimeError(f"update check failed: {e.code()} {e.details()}")

    if not response:
        return None

    return _parse_check_result(response)


def oss_update_info(
    version: int,
    patch_name: str = DEFAULT_PATCH_NAME,
    base_version: int = DEFAULT_BASE_VERSION,
) -> UpdateInfo:
    """Construct object-store URLs for a known version, without contacting the
    update server.

    No md5s are available this way, so an image assembled from these URLs cannot be
    verified against the vendor's own checksums.
    """
    return UpdateInfo(
        firmware=FirmwareInfo(
            version=version,
            url=f"{OSS_BASE_URL}/firmware/v{version}/{patch_name}.bin",
            md5="",
        ),
        base=FirmwareInfo(
            version=base_version,
            url=f"{OSS_BASE_URL}/upgrade_base_v{base_version}.bin.zip",
            md5="",
        ),
    )


#####################
# Downloading and assembling

def _download(url: str, label: str, progress: ProgressCallback | None) -> bytes:
    with urllib.request.urlopen(url) as response:
        total = int(response.headers.get("Content-Length", 0))
        chunks: t.List[bytes] = []
        received = 0
        while chunk := response.read(65536):
            chunks.append(chunk)
            received += len(chunk)
            if progress:
                progress(label, received, total)
    return b"".join(chunks)


def _verify(data: bytes, expected_md5: str, label: str) -> None:
    if not expected_md5:
        return
    actual = hashlib.md5(data).hexdigest()
    if actual != expected_md5:
        raise RuntimeError(
            f"{label} md5 mismatch: expected {expected_md5}, got {actual}"
        )


def assemble(base: bytes, patch: bytes) -> bytes:
    """Apply a BSDIFF40 patch to a base image.

    `base` may be either the raw base image or the zip it ships in.
    """
    bsdiff4 = _require("bsdiff4", "bsdiff4")

    if base[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(base)) as zf:
            names = [n for n in zf.namelist() if n.endswith(".bin")]
            if not names:
                raise RuntimeError("no .bin found in base zip")
            base = zf.read(names[0])

    if patch[:8] != b"BSDIFF40":
        raise RuntimeError(
            f"unexpected patch magic {patch[:8]!r}, expected b'BSDIFF40'"
        )

    return bsdiff4.patch(base, patch)


async def download_firmware(
    update_info: UpdateInfo,
    progress: ProgressCallback | None = None,
) -> FirmwareBundle:
    """Download the patch and base image and assemble them.

    Downloaded artifacts are checked against the server's md5s when available.

    Requires `bsdiff4`.
    """
    patch, base = await asyncio.gather(
        asyncio.to_thread(_download, update_info.firmware.url, "patch", progress),
        asyncio.to_thread(_download, update_info.base.url, "base", progress),
    )

    _verify(patch, update_info.firmware.md5, "patch")
    _verify(base, update_info.base.md5, "base")

    return FirmwareBundle(
        data=await asyncio.to_thread(assemble, base, patch),
        update_info=update_info,
    )


async def fetch_firmware(
    product_id: int,
    firmware_version: int = 0,
    progress: ProgressCallback | None = None,
) -> FirmwareBundle | None:
    """Check for an update and download it if one is available."""
    update_info = await check_update(product_id, firmware_version)
    if update_info is None:
        return None
    return await download_firmware(update_info, progress)


#####################
# CLI

def _print_progress(label: str, done: int, total: int) -> None:
    pct = f"{100 * done // total}%" if total else f"{done} bytes"
    print(f"\r{label}: {pct}", end="", file=sys.stderr, flush=True)


def _print_update_info(info: UpdateInfo) -> None:
    print(f"firmware v{info.firmware.version}")
    print(f"  url {info.firmware.url}")
    print(f"  md5 {info.firmware.md5}")
    print(f"base v{info.base.version}")
    print(f"  url {info.base.url}")
    print(f"  md5 {info.base.md5}")


async def _cmd_check(args: argparse.Namespace) -> int:
    info = await check_update(args.product_id, args.firmware_version)
    if info is None:
        print("no update available")
        return 1
    _print_update_info(info)
    return 0


async def _cmd_fetch(args: argparse.Namespace) -> int:
    if args.product_id is not None:
        info = await check_update(args.product_id, args.firmware_version)
        if info is None:
            print("no update available")
            return 1
    else:
        info = oss_update_info(args.version, args.patch_name, args.base_version)

    _print_update_info(info)
    bundle = await download_firmware(info, _print_progress)
    print(file=sys.stderr)

    bundle.save(args.output)
    print(f"wrote {args.output} ({bundle.size} bytes, md5 {bundle.md5})")
    return 0


async def _cmd_assemble(args: argparse.Namespace) -> int:
    with open(args.base, "rb") as f:
        base = f.read()
    with open(args.patch, "rb") as f:
        patch = f.read()

    data = assemble(base, patch)
    with open(args.output, "wb") as f:
        f.write(data)

    print(f"wrote {args.output} ({len(data)} bytes, "
          f"md5 {hashlib.md5(data).hexdigest()})")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benlink.firmware",
        description="Download and assemble Benshi radio firmware.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check", help="ask the update server for the latest release")
    check.add_argument("--product-id", type=int, required=True,
                       help="from GET_DEV_INFO, e.g. 259 for VR-N76 / GA-5WB")
    check.add_argument("--firmware-version", type=int, default=0,
                       help="currently installed internal version (default: 0)")
    check.set_defaults(run=_cmd_check)

    fetch = subparsers.add_parser(
        "fetch", help="download and assemble a firmware image")
    source = fetch.add_mutually_exclusive_group(required=True)
    source.add_argument("--product-id", type=int,
                        help="ask the update server for the latest release")
    source.add_argument("--version", type=int,
                        help="fetch a known version directly, without the server")
    fetch.add_argument("--firmware-version", type=int, default=0)
    fetch.add_argument("--patch-name", default=DEFAULT_PATCH_NAME,
                       help=f"default: {DEFAULT_PATCH_NAME}")
    fetch.add_argument("--base-version", type=int, default=DEFAULT_BASE_VERSION,
                       help=f"default: {DEFAULT_BASE_VERSION}")
    fetch.add_argument("-o", "--output", required=True)
    fetch.set_defaults(run=_cmd_fetch)

    assemble_cmd = subparsers.add_parser(
        "assemble", help="assemble from local files (offline)")
    assemble_cmd.add_argument("--base", required=True,
                              help="base image, raw or zipped")
    assemble_cmd.add_argument("--patch", required=True)
    assemble_cmd.add_argument("-o", "--output", required=True)
    assemble_cmd.set_defaults(run=_cmd_assemble)

    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    try:
        sys.exit(asyncio.run(args.run(args)))
    except (RuntimeError, ImportError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
