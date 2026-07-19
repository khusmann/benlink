"""
# Disclaimer

**Use this at your own risk. I am not responsible for bricking your radio, or for
any other damage to your equipment.** This module is not endorsed by or affiliated
with Benshi, Vero, RadioOddity, BTech, or any other company.

Downloading and assembling an image is safe. Flashing one is not.

`flash` reproduces the official app's message sequence byte for byte against
packet captures, but **it has not yet been run against a radio**
([issue #10](https://github.com/khusmann/benlink/issues/10)). The commit step is
also known to differ by model: the UV-Pro reboots itself once the image is
staged, while the VR-N76 reportedly does not.

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

from ._fetch import (
    BASE_IMAGES,
    PRODUCTS,
    FirmwareBundle,
    FirmwareInfo,
    ProgressCallback,
    UpdateInfo,
    assemble,
    check_update,
    download,
    download_firmware,
    extract_base,
    fetch_firmware,
    oss_base_url,
    oss_patch_url,
    oss_update_info,
)
from ._flash import FlashError, FlashResult, flash

__all__ = [
    "BASE_IMAGES",
    "PRODUCTS",
    "FirmwareBundle",
    "FirmwareInfo",
    "FlashError",
    "FlashResult",
    "ProgressCallback",
    "UpdateInfo",
    "assemble",
    "check_update",
    "download",
    "download_firmware",
    "extract_base",
    "fetch_firmware",
    "flash",
    "oss_base_url",
    "oss_patch_url",
    "oss_update_info",
]
