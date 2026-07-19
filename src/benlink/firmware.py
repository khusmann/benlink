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

RPC_TIMEOUT = 10.0
"""@private"""

PRODUCTS: t.Dict[str, t.Tuple[int, str]] = {
    "VR_N76": (259, "patch_base_to_vr_n76"),
    "GA_5WB": (259, "patch_base_to_vr_n76"),
    "UV_PRO": (260, "patch_base_to_vr_n76_m"),
    "VR_N75": (261, "patch_base_to_vr_n75_h2"),
}
"""Known radios, as `name: (product_id, patch_name)`.

Every patch name here was returned by the update server for the corresponding product
id. Note that 259 covers both the VR-N76 and the GA-5WB — they share a patch series,
confirmed by a GA-5WB flash capture whose `md5sum_tail` matches
`patch_base_to_vr_n76.v120` assembled against the shared base.
"""

DEFAULT_PATCH_NAME = PRODUCTS["VR_N76"][1]
"""@private"""

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
# Data

class FirmwareInfo(t.NamedTuple):
    """One downloadable artifact (either the patch or the base image)."""
    version: int
    url: str
    md5: str

    @classmethod
    def from_protocol(cls, info: t.Any) -> FirmwareInfo:
        """@private (Protocol helper)"""
        return cls(version=info.version, url=info.url, md5=info.md5)


class UpdateInfo(t.NamedTuple):
    """The patch and base image that together make up a firmware release."""
    firmware: FirmwareInfo
    base: FirmwareInfo

    @classmethod
    def from_protocol(cls, result: t.Any) -> UpdateInfo | None:
        """@private (Protocol helper)"""
        if not result.firmware.url or not result.base.url:
            return None
        return cls(
            firmware=FirmwareInfo.from_protocol(result.firmware),
            base=FirmwareInfo.from_protocol(result.base),
        )


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

async def check_update(
    product_id: int,
    firmware_version: int = 0,
) -> UpdateInfo | None:
    """Ask the update server for the latest release for `product_id`.

    `firmware_version` is the currently installed internal version. The server
    returns the latest release regardless of its value, so it has no effect in
    practice. Returns `None` if the server reports no update.

    Requires `grpcio` and `protobuf`.
    """
    grpc = _require("grpc", "grpcio")
    from . import _benshikj_pb2, _benshikj_pb2_grpc

    request = _benshikj_pb2.CheckFirmwareUpdateRequest(
        product_id=product_id,
        firmware_version=firmware_version,
    )

    credentials = grpc.ssl_channel_credentials()
    async with grpc.aio.secure_channel(RPC_HOST, credentials) as channel:
        stub = _benshikj_pb2_grpc.DeviceManagementStub(channel)
        try:
            result = await stub.CheckFirmwareUpdate(request, timeout=RPC_TIMEOUT)
        except grpc.aio.AioRpcError as e:
            raise RuntimeError(f"update check failed: {e.code()} {e.details()}")

    return UpdateInfo.from_protocol(result)


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
    base: bytes | None = None,
) -> FirmwareBundle:
    """Download the patch and base image and assemble them.

    The base image is shared across radios and releases, so pass `base` to reuse a
    local copy instead of downloading it again.

    Downloaded artifacts are checked against the server's md5s when available.

    Requires `bsdiff4`.
    """
    if base is None:
        patch, base = await asyncio.gather(
            asyncio.to_thread(
                _download, update_info.firmware.url, "patch", progress),
            asyncio.to_thread(_download, update_info.base.url, "base", progress),
        )
        _verify(base, update_info.base.md5, "base")
    else:
        patch = await asyncio.to_thread(
            _download, update_info.firmware.url, "patch", progress)

    _verify(patch, update_info.firmware.md5, "patch")

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


def _print_firmware_info(label: str, info: FirmwareInfo) -> None:
    # The server populates version for the patch but not for the base image.
    print(f"{label} v{info.version}" if info.version else label)
    print(f"  url {info.url}")
    if info.md5:
        print(f"  md5 {info.md5}")


def _print_update_info(info: UpdateInfo) -> None:
    _print_firmware_info("firmware", info.firmware)
    _print_firmware_info("base", info.base)


def _resolve_product(args: argparse.Namespace) -> t.Tuple[int | None, str]:
    """Resolve `--product` into a product id and patch name, letting the explicit
    `--product-id` / `--patch-name` flags override either half."""
    product_id, patch_name = None, DEFAULT_PATCH_NAME

    if getattr(args, "product", None):
        product_id, patch_name = PRODUCTS[args.product]

    if getattr(args, "product_id", None) is not None:
        product_id = args.product_id
    if getattr(args, "patch_name", None) is not None:
        patch_name = args.patch_name

    return product_id, patch_name


def _require_product_id(product_id: int | None) -> int:
    if product_id is None:
        raise RuntimeError(
            "a product is required: pass --product "
            f"({', '.join(PRODUCTS)}) or --product-id"
        )
    return product_id


async def _cmd_check(args: argparse.Namespace) -> int:
    product_id, _ = _resolve_product(args)
    info = await check_update(_require_product_id(product_id),
                              args.firmware_version)
    if info is None:
        print("no update available")
        return 1
    _print_update_info(info)
    return 0


async def _cmd_fetch(args: argparse.Namespace) -> int:
    product_id, patch_name = _resolve_product(args)

    if args.version is None:
        info = await check_update(_require_product_id(product_id),
                                  args.firmware_version)
        if info is None:
            print("no update available")
            return 1
    else:
        info = oss_update_info(args.version, patch_name, args.base_version)

    base = None
    if args.base:
        with open(args.base, "rb") as f:
            base = f.read()

    _print_update_info(info)
    sys.stdout.flush()

    bundle = await download_firmware(info, _print_progress, base)
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
    check_product = check.add_mutually_exclusive_group(required=True)
    check_product.add_argument("--product", choices=sorted(PRODUCTS))
    check_product.add_argument("--product-id", type=int,
                               help="from GET_DEV_INFO, for radios not listed above")
    check.add_argument("--firmware-version", type=int, default=0,
                       help="currently installed internal version (default: 0)")
    check.set_defaults(run=_cmd_check)

    fetch = subparsers.add_parser(
        "fetch", help="download and assemble a firmware image")
    source = fetch.add_mutually_exclusive_group(required=True)
    source.add_argument("--product", choices=sorted(PRODUCTS),
                        help="ask the update server for this radio's latest release")
    source.add_argument("--product-id", type=int,
                        help="as --product, for radios not listed above")
    source.add_argument("--version", type=int,
                        help="fetch a known version directly, without the server")
    fetch.add_argument("--firmware-version", type=int, default=0)
    fetch.add_argument("--patch-name",
                       help=f"only used with --version (default: "
                            f"{DEFAULT_PATCH_NAME})")
    fetch.add_argument("--base-version", type=int, default=DEFAULT_BASE_VERSION,
                       help=f"default: {DEFAULT_BASE_VERSION}")
    fetch.add_argument("--base",
                       help="local base image to reuse instead of downloading it")
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
