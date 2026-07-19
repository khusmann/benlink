"""
# Disclaimer

**Use this at your own risk. I am not responsible for bricking your radio, or for
any other damage to your equipment.** This module is not endorsed by or affiliated
with Benshi, Vero, RadioOddity, BTech, or any other company.

Downloading and assembling an image is safe. Flashing one is not, and is not
implemented yet ([issue #10](https://github.com/khusmann/benlink/issues/10)).

# The intended flow

Firmware ships as a shared **base image** plus a per-release **patch** in BSDIFF40
format; assembling the two yields the image the radio expects. benlink
redistributes neither, and fetches both on request.

One command walks the whole upgrade, prompting as it goes:

```bash
python -m benlink.firmware update XX:XX:XX:XX:XX:XX
```

It reads the product id and installed version from the radio, asks the update
server for the latest release, downloads the patch and base, assembles them, and
checks the result against the server's md5. Because the server names both
artifacts, this path cannot pair a patch with the wrong base.

Add `--rfcomm CHANNEL` for RFCOMM instead of BLE, `--keep DIR` to write somewhere
durable, `-y` to accept prompts.

# The pieces

Each step is also available alone, for archiving old releases or working away from
the radio. Everything but `info` avoids the Bluetooth stack.

```bash
# which radio is this?
python -m benlink.firmware info XX:XX:XX:XX:XX:XX

# what is the latest release?
python -m benlink.firmware check --product UV_PRO

# that release, downloaded and assembled, without a radio
python -m benlink.firmware fetch --product UV_PRO -o fw.bin

# one artifact at a time, for any version
python -m benlink.firmware download-patch --version 128 --product UV_PRO -o patch.bin
python -m benlink.firmware download-base --version original -o base.zip

# combine them offline
python -m benlink.firmware assemble --base base.zip --patch patch.bin -o fw.bin
```

`--product` is a shorthand for the radios in `PRODUCTS`; `--product-id` works for
any radio, and `info` tells you yours. If yours isn't listed, please
[open an issue](https://github.com/khusmann/benlink/issues) with what `info`
reports so it can be added.

# Verification

A BSDIFF40 patch carries no checksum of the base it was built against, so pairing
a patch with the wrong base **succeeds silently** and produces a corrupt image of
plausible length. See `BASE_IMAGES` for the known pairings.

The server publishes an md5 of the *assembled* image for the current release, so
`update` and `fetch` are checked end to end. Older releases have none; for those,
`assemble --expect-md5` accepts one from elsewhere, such as the `md5sum_tail` in a
packet capture of an official flash. Every command that writes an image says
whether it could be verified.

# Notes

The product id comes from `GET_DEV_INFO` (`DeviceInfo.product_id`) and is not
unique across vendors: the VR-N76 and GA-5WB both report 259.
`DeviceInfo.firmware_version` shares the update server's numbering, so installed
and available versions compare directly.
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
id. Note that 259 covers both the VR-N76 and the GA-5WB, which share a patch series,
confirmed by a GA-5WB flash capture whose `md5sum_tail` matches
`patch_base_to_vr_n76.v120` assembled against the shared base.
"""

DEFAULT_PATCH_NAME = PRODUCTS["VR_N76"][1]
"""@private"""

BASE_IMAGES: t.Dict[str, str] = {
    "original": "upgrade_base.bin.zip",
    "1": "upgrade_base_v1.bin.zip",
}
"""The base images a patch can be built against, as `name: filename`.

A patch carries no checksum of its source, so pairing it with the wrong base produces
a corrupt image with no error (see `assemble`). Known pairings, from flash captures and
from the update server: patch v120, v121 and v128 use `original`; v147 uses `1`. Where
the changeover happened is not known, because the server only publishes metadata for
the current release.
"""

DEFAULT_BASE_IMAGE = "1"
"""@private"""


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
            raise RuntimeError(
                f"update check failed: {e.code()} {e.details()}")

    return UpdateInfo.from_protocol(result)


def oss_patch_url(version: int, patch_name: str = DEFAULT_PATCH_NAME) -> str:
    """URL of a patch in the object store."""
    return f"{OSS_BASE_URL}/firmware/v{version}/{patch_name}.bin"


def oss_base_url(base_image: str = DEFAULT_BASE_IMAGE) -> str:
    """URL of a base image in the object store. `base_image` is a key of
    `BASE_IMAGES`."""
    if base_image not in BASE_IMAGES:
        raise RuntimeError(
            f"unknown base image {base_image!r}, expected one of "
            f"{', '.join(BASE_IMAGES)}"
        )
    return f"{OSS_BASE_URL}/{BASE_IMAGES[base_image]}"


def oss_update_info(
    version: int,
    patch_name: str = DEFAULT_PATCH_NAME,
    base_image: str = DEFAULT_BASE_IMAGE,
) -> UpdateInfo:
    """Construct object-store URLs for a known version, without contacting the
    update server.

    No md5s are available this way, so the result cannot be verified. Since a patch
    only applies to the base it shipped with, picking the wrong `base_image` yields a
    corrupt image silently. See `BASE_IMAGES`.
    """
    return UpdateInfo(
        firmware=FirmwareInfo(
            version=version,
            url=oss_patch_url(version, patch_name),
            md5="",
        ),
        base=FirmwareInfo(version=0, url=oss_base_url(base_image), md5=""),
    )


#####################
# Downloading and assembling

async def download(
    url: str,
    label: str = "download",
    progress: ProgressCallback | None = None,
) -> bytes:
    """Download a single artifact."""
    return await asyncio.to_thread(_download, url, label, progress)


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
    valid against the base image released alongside them. Compare the result against
    `UpdateInfo.firmware.md5` whenever it is known.
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
) -> FirmwareBundle:
    """Download the patch and base image named by `update_info` and assemble them.

    Both are always fetched fresh. Base images are revised over time and a patch
    only applies to the one released with it, so reusing a local copy risks pairing
    a patch with a base it was never built against.

    Requires `bsdiff4`.
    """
    patch, base = await asyncio.gather(
        asyncio.to_thread(_download, update_info.firmware.url,
                          "patch", progress),
        asyncio.to_thread(_download, update_info.base.url, "base", progress),
    )

    # The server's md5s describe the extracted base and the assembled firmware,
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
