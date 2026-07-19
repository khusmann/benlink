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
import asyncio
import hashlib
import io
import urllib.request
import zipfile

from ..common import ImmutableBaseModel

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

class FirmwareInfo(ImmutableBaseModel):
    """One downloadable artifact (either the patch or the base image)."""
    version: int
    url: str
    md5: str

    @classmethod
    def from_protocol(cls, info: t.Any) -> FirmwareInfo:
        """@private (Protocol helper)"""
        return cls(version=info.version, url=info.url, md5=info.md5)


class UpdateInfo(ImmutableBaseModel):
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


class FirmwareBundle(ImmutableBaseModel):
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


def extract_base(base: bytes) -> bytes:
    """Return the base image, unwrapping the zip it ships in if needed."""
    if base[:2] != b"PK":
        return base

    with zipfile.ZipFile(io.BytesIO(base)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".bin")]
        if not names:
            raise RuntimeError("no .bin found in base zip")
        return zf.read(names[0])


def assemble(base: bytes, patch: bytes) -> bytes:
    """Apply a BSDIFF40 patch to a base image.

    `base` may be either the raw base image or the zip it ships in.

    A patch carries no checksum of the base it was built against, so applying it to
    the wrong base succeeds and silently yields a corrupt image. Patches are only
    valid against the base image released alongside them — compare the result
    against `UpdateInfo.firmware.md5` whenever it is known.
    """
    bsdiff4 = _require("bsdiff4", "bsdiff4")

    if patch[:8] != b"BSDIFF40":
        raise RuntimeError(
            f"unexpected patch magic {patch[:8]!r}, expected b'BSDIFF40'"
        )

    return bsdiff4.patch(extract_base(base), patch)


async def download_firmware(
    update_info: UpdateInfo,
    progress: ProgressCallback | None = None,
    base: bytes | None = None,
) -> FirmwareBundle:
    """Download the patch and base image and assemble them.

    Pass `base` to reuse a local copy instead of downloading it again. Note that
    base images are revised over time and a patch only applies to the one released
    with it, so a stale local copy will produce a corrupt image — which is caught
    here only because the assembled result is checked against the server's md5.

    Requires `bsdiff4`.
    """
    if base is None:
        patch, base = await asyncio.gather(
            asyncio.to_thread(
                _download, update_info.firmware.url, "patch", progress),
            asyncio.to_thread(_download, update_info.base.url, "base", progress),
        )
    else:
        patch = await asyncio.to_thread(
            _download, update_info.firmware.url, "patch", progress)

    # The server's md5s describe the extracted base and the assembled firmware —
    # neither the base zip nor the patch file as downloaded.
    base = extract_base(base)
    _verify(base, update_info.base.md5, "base image")

    data = await asyncio.to_thread(assemble, base, patch)
    _verify(data, update_info.firmware.md5, "assembled firmware")

    return FirmwareBundle(data=data, update_info=update_info)


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
