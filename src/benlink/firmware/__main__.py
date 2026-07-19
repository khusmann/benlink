"""Command line interface for `benlink.firmware`.

Run with `python -m benlink.firmware`.
"""

from __future__ import annotations
import typing as t
import argparse
import asyncio
import hashlib
import os
import sys
import tempfile

from . import (
    BASE_IMAGES,
    DEFAULT_PATCH_NAME,
    PRODUCTS,
    FirmwareInfo,
    UpdateInfo,
    assemble,
    check_update,
    download,
    download_firmware,
    extract_base,
    oss_base_url,
    oss_patch_url,
)


#####################
# Output

def _out(message: str = "") -> None:
    print(message, file=sys.stderr)


def _make_progress() -> t.Callable[[str, int, int], None]:
    """Render concurrent downloads as one updating line."""
    state: t.Dict[str, t.Tuple[int, int]] = {}

    def progress(label: str, done: int, total: int) -> None:
        state[label] = (done, total)
        line = "  ".join(
            f"{k} {100 * d // n}%" if n else f"{k} {d}B"
            for k, (d, n) in state.items()
        )
        print(f"\r  {line}", end="", file=sys.stderr, flush=True)

    return progress


def _print_verdict(data: bytes, expected: str, source: str) -> None:
    """Every image this tool produces reports whether it could be checked.

    An unverified image is the failure mode that bricks a radio quietly, so the
    warning is never suppressed.
    """
    md5 = hashlib.md5(data).hexdigest()
    if not expected:
        _out(f"  md5 {md5}  [!] unverified (no reference md5 available)")
    elif md5 == expected:
        _out(f"  md5 {md5}  ok, matches {source}")
    else:
        raise RuntimeError(
            f"md5 mismatch against {source}: expected {expected}, got {md5}"
        )


def _print_update_info(info: UpdateInfo) -> None:
    def show(label: str, entry: FirmwareInfo) -> None:
        # The server populates version for the patch but not for the base image.
        _out(f"  {label} v{entry.version}" if entry.version else f"  {label}")
        _out(f"    url {entry.url}")
        if entry.md5:
            _out(f"    md5 {entry.md5}")

    show("patch", info.firmware)
    show("base", info.base)


def _write(path: str, data: bytes, force: bool) -> None:
    if os.path.exists(path) and not force:
        raise RuntimeError(f"{path} already exists (use --force to overwrite)")
    with open(path, "wb") as f:
        f.write(data)
    print(path)


def _confirm(question: str, default_yes: bool, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return False
    return default_yes if not answer else answer.startswith("y")


#####################
# Radio

def _connection(args: argparse.Namespace):
    # Imported lazily: everything except the radio commands works without a
    # Bluetooth stack.
    from ..command import CommandConnection

    if args.rfcomm is not None:
        channel = "auto" if args.rfcomm == "auto" else int(args.rfcomm)
        _out(f"Connecting over RFCOMM to {args.uuid} (channel {channel})...")
        return CommandConnection.new_rfcomm(args.uuid, channel)

    _out(f"Connecting over BLE to {args.uuid}...")
    return CommandConnection.new_ble(args.uuid)


def _print_device_info(info: t.Any) -> None:
    _out(f"  vendor {info.vendor_id}, product {info.product_id}")
    _out(f"  firmware v{info.firmware_version}"
         f", hardware version {info.hardware_version}")


#####################
# Products

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


#####################
# Commands

async def _cmd_info(args: argparse.Namespace) -> int:
    async with _connection(args) as conn:
        _print_device_info(await conn.get_device_info())
    return 0


async def _cmd_check(args: argparse.Namespace) -> int:
    product_id, _ = _resolve_product(args)
    info = await check_update(_require_product_id(product_id),
                              args.firmware_version)
    if info is None:
        _out("no update available")
        return 2
    _print_update_info(info)
    return 0


async def _cmd_fetch(args: argparse.Namespace) -> int:
    product_id, _ = _resolve_product(args)
    info = await check_update(_require_product_id(product_id),
                              args.firmware_version)
    if info is None:
        _out("no update available")
        return 2

    _print_update_info(info)

    bundle = await download_firmware(info, _make_progress())
    _out()
    _print_verdict(bundle.data, info.firmware.md5, "the update server")

    _write(args.output, bundle.data, args.force)
    return 0


async def _cmd_download_patch(args: argparse.Namespace) -> int:
    _, patch_name = _resolve_product(args)
    url = oss_patch_url(args.version, patch_name)
    _out(f"  url {url}")

    data = await download(url, "patch", _make_progress())
    _out()
    _print_verdict(data, "", "")

    _write(args.output, data, args.force)
    return 0


async def _cmd_download_base(args: argparse.Namespace) -> int:
    url = oss_base_url(args.version)
    _out(f"  url {url}")

    data = await download(url, "base", _make_progress())
    _out()

    extracted = extract_base(data)
    _out(f"  extracted md5 {hashlib.md5(extracted).hexdigest()}")

    _write(args.output, extracted if args.extract else data, args.force)
    return 0


async def _cmd_assemble(args: argparse.Namespace) -> int:
    with open(args.base, "rb") as f:
        base = f.read()
    with open(args.patch, "rb") as f:
        patch = f.read()

    data = assemble(base, patch)
    _print_verdict(data, args.expect_md5 or "", "--expect-md5")

    _write(args.output, data, args.force)
    return 0


async def _cmd_update(args: argparse.Namespace) -> int:
    async with _connection(args) as conn:
        device_info = await conn.get_device_info()
    _print_device_info(device_info)

    _out()
    _out("Checking for updates...")
    info = await check_update(device_info.product_id)
    if info is None:
        _out("  no update available")
        return 2

    installed = device_info.firmware_version
    latest = info.firmware.version
    _out(f"  latest v{latest}   (you have v{installed})")
    _print_update_info(info)

    _out()
    if latest == installed:
        question = f"Already on v{latest}. Download and assemble anyway?"
        if not _confirm(question, False, args.yes):
            return 0
    elif not _confirm("Download and assemble?", True, args.yes):
        return 0

    bundle = await download_firmware(info, _make_progress())
    _out()
    _out(f"  assembled {bundle.size} bytes")
    _print_verdict(bundle.data, info.firmware.md5, "the update server")

    directory = args.keep or tempfile.mkdtemp(prefix="benlink-fw-")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"firmware-v{info.firmware.version}.bin")
    _out()
    _write(path, bundle.data, args.force)

    _out()
    _out("Flashing is not implemented yet, see "
         "https://github.com/khusmann/benlink/issues/10")
    _out(f"The assembled image has been kept at {path}")
    return 0


#####################
# Parser

def _add_radio_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("uuid", help="radio device UUID, e.g. XX:XX:XX:XX:XX:XX")
    parser.add_argument("--rfcomm", nargs="?", const="auto", default=None,
                        metavar="CHANNEL",
                        help="connect over RFCOMM instead of BLE")


def _add_product_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--product", choices=sorted(PRODUCTS))
    group.add_argument("--product-id", type=int,
                       help="from `info`, for radios not listed above")


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing output file")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benlink.firmware",
        description="Download and assemble Benshi radio firmware.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser(
        "update", help="guided upgrade: read the radio, fetch, assemble")
    _add_radio_args(update)
    update.add_argument("--yes", "-y", action="store_true",
                        help="accept all prompts")
    update.add_argument("--keep", metavar="DIR",
                        help="write to DIR instead of a temporary directory")
    update.add_argument("--force", action="store_true")
    update.set_defaults(run=_cmd_update)

    info = subparsers.add_parser(
        "info", help="read product id and versions from a radio")
    _add_radio_args(info)
    info.set_defaults(run=_cmd_info)

    check = subparsers.add_parser(
        "check", help="ask the update server for the latest release")
    _add_product_args(check)
    check.add_argument("--firmware-version", type=int, default=0,
                       help=argparse.SUPPRESS)
    check.set_defaults(run=_cmd_check)

    fetch = subparsers.add_parser(
        "fetch", help="check, download and assemble the latest release")
    _add_product_args(fetch)
    fetch.add_argument("--firmware-version", type=int, default=0,
                       help=argparse.SUPPRESS)
    _add_output_args(fetch)
    fetch.set_defaults(run=_cmd_fetch)

    patch = subparsers.add_parser(
        "download-patch", help="download one patch by version")
    patch.add_argument("--version", type=int, required=True)
    patch_product = patch.add_mutually_exclusive_group(required=True)
    patch_product.add_argument("--product", choices=sorted(PRODUCTS))
    patch_product.add_argument("--patch-name",
                               help=f"e.g. {DEFAULT_PATCH_NAME}")
    _add_output_args(patch)
    patch.set_defaults(run=_cmd_download_patch)

    base = subparsers.add_parser(
        "download-base", help="download a base image")
    # No default: a patch only applies to the base it shipped with, and picking
    # the wrong one corrupts the result silently.
    base.add_argument("--version", choices=sorted(BASE_IMAGES), required=True,
                      help="which base image; patches v120-v128 use 'original', "
                           "v147 uses '1'")
    base.add_argument("--extract", action="store_true",
                      help="unwrap the zip and write the .bin")
    _add_output_args(base)
    base.set_defaults(run=_cmd_download_base)

    assemble_cmd = subparsers.add_parser(
        "assemble", help="combine a base and a patch (offline)")
    assemble_cmd.add_argument("--base", required=True,
                              help="base image, raw or zipped")
    assemble_cmd.add_argument("--patch", required=True)
    assemble_cmd.add_argument("--expect-md5", metavar="MD5",
                              help="verify the assembled image against a known md5")
    _add_output_args(assemble_cmd)
    assemble_cmd.set_defaults(run=_cmd_assemble)

    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    try:
        sys.exit(asyncio.run(args.run(args)))
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, ImportError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
