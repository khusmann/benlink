"""Command line interface for `benlink.firmware`.

Run with `python -m benlink.firmware`.
"""

from __future__ import annotations
import typing as t
import argparse
import asyncio
import collections
import contextlib
import hashlib
import os
import signal
import sys
import tempfile
import time

if t.TYPE_CHECKING:
    from ..command import CommandConnection, DeviceInfo

from . import (
    BASE_IMAGES,
    PRODUCTS,
    FirmwareInfo,
    UpdateInfo,
    abort_update,
    assemble,
    check_update,
    download,
    download_firmware,
    extract_base,
    flash,
    oss_base_url,
    oss_patch_url,
)

_REBOOT_WAIT = 20.0
"""Seconds to let the radio reboot before trying to reach it again."""

_COMMIT_ATTEMPTS = 5

_RATE_WINDOW = 30.0
"""Seconds of history the transfer rate is averaged over."""


#####################
# Output

def _out(message: str = "") -> None:
    print(message, file=sys.stderr)


def _size(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}MB"
    if n >= 1e3:
        return f"{n / 1e3:.0f}kB"
    return f"{n:.0f}B"


def _duration(seconds: float) -> str:
    total = int(seconds)
    if total >= 3600:
        return f"{total // 3600}h{(total % 3600) // 60:02d}m"
    return f"{total // 60}:{total % 60:02d}"


def _make_progress() -> t.Callable[[str, int, int], None]:
    """Render concurrent transfers as one updating line.

    Flashing over BLE runs for many minutes, so a bare percentage is not enough
    to tell slow from stuck.
    """
    recent: t.Dict[str, t.Deque[t.Tuple[float, int]]] = {}
    state: t.Dict[str, t.Tuple[int, int]] = {}
    width = 0

    def render(label: str, done: int, total: int) -> str:
        if not total:
            return f"{label} {_size(done)}"
        out = f"{label} {100 * done // total}% of {_size(total)}"
        # Rate over a trailing window, not since the start. Connection setup and
        # BLE's opening connection interval are slow enough that a running
        # average reads far below the rate actually being achieved, and the eta
        # derived from it is wrong by minutes.
        window = recent[label]
        elapsed = window[-1][0] - window[0][0]
        moved = done - window[0][1]
        if elapsed > 1.0 and moved > 0:
            rate = moved / elapsed
            out += f"  {_size(rate)}/s  eta {_duration((total - done) / rate)}"
        return out

    def progress(label: str, done: int, total: int) -> None:
        nonlocal width
        now = time.monotonic()
        window = recent.setdefault(label, collections.deque(maxlen=512))
        window.append((now, done))
        while len(window) > 2 and now - window[0][0] > _RATE_WINDOW:
            window.popleft()
        state[label] = (done, total)
        line = "  ".join(render(k, d, n) for k, (d, n) in state.items())
        # Pad to the widest line so far, or a shrinking eta leaves debris behind.
        width = max(width, len(line))
        print(f"\r  {line:<{width}}", end="", file=sys.stderr, flush=True)

    return progress


def _print_verdict(data: bytes, expected: str | None, source: str) -> None:
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
    def show(label: str, entry: FirmwareInfo, md5_covers: str) -> None:
        # The server populates version for the patch but not for the base image.
        _out(f"  {label} v{entry.version}" if entry.version else f"  {label}")
        _out(f"    url {entry.url}")
        if entry.md5:
            # Neither md5 describes the file at the url above, which is easy to
            # assume and wrong.
            _out(f"    md5 {entry.md5}  ({md5_covers})")

    show("patch", info.firmware, "of the assembled image")
    show("base", info.base, "of the extracted .bin")


def _write(path: str, data: bytes, force: bool) -> None:
    if os.path.exists(path) and not force:
        raise RuntimeError(f"{path} already exists (use --force to overwrite)")
    with open(path, "wb") as f:
        f.write(data)
    print(path)


@contextlib.contextmanager
def _graceful_interrupt() -> t.Generator[None, None, None]:
    """Say something the moment Ctrl+C lands.

    `flash` tells the radio to abort on the way out, which takes a moment. With
    no message the transfer just appears to hang after the keypress.
    """
    def handler(*_: t.Any) -> None:
        _out()
        _out("Interrupted. Telling the radio to abort "
             "(press Ctrl+C again to quit without waiting)...")
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


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

@contextlib.asynccontextmanager
async def _radio(
    args: argparse.Namespace,
) -> t.AsyncGenerator[CommandConnection, None]:
    """Connect, and tolerate the radio vanishing on the way out.

    A firmware update ends with the radio rebooting, which drops the link before
    anything gets to close it. Raising from the teardown would turn a completed
    transfer into a crash.
    """
    conn = _connection(args)
    await conn.connect()
    try:
        yield conn
    finally:
        with contextlib.suppress(Exception):
            await conn.disconnect()


def _connection(args: argparse.Namespace) -> CommandConnection:
    # Imported lazily: everything except the radio commands works without a
    # Bluetooth stack.
    from ..command import CommandConnection

    if args.rfcomm is not None:
        channel = "auto" if args.rfcomm == "auto" else int(args.rfcomm)
        _out(f"Connecting over RFCOMM to {args.uuid} (channel {channel})...")
        return CommandConnection.new_rfcomm(args.uuid, channel)

    _out(f"Connecting over BLE to {args.uuid}...")
    return CommandConnection.new_ble(args.uuid)


def _print_device_info(info: DeviceInfo) -> None:
    _out(f"  vendor {info.vendor_id}, product {info.product_id}")
    _out(f"  firmware v{info.firmware_version}"
         f", hardware version {info.hardware_version}")


#####################
# Products

def _resolve_product(
    args: argparse.Namespace,
) -> t.Tuple[int | None, str | None]:
    """Resolve `--product` into a product id and patch name, letting the explicit
    `--product-id` / `--patch-name` flags override either half."""
    product_id, patch_name = None, None

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
    assert patch_name is not None  # the parser requires --product or --patch-name
    url = oss_patch_url(args.version, patch_name)
    _out(f"  url {url}")

    data = await download(url, "patch", _make_progress())
    _out()
    _print_verdict(data, None, "")

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
    _print_verdict(data, args.expect_md5, "--expect-md5")

    _write(args.output, data, args.force)
    return 0


async def _cmd_update(args: argparse.Namespace) -> int:
    # The connection is held for the whole flow: the radio is needed at the start
    # to identify it, and again at the end to flash.
    async with _radio(args) as conn:
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
        path = os.path.join(directory, f"firmware-v{latest}.bin")
        _out()
        _write(path, bundle.data, args.force)

        _out()
        if not _confirm(f"Flash v{latest} to this radio?", False, args.yes):
            _out(f"The assembled image has been kept at {path}")
            return 0

        _out("Do not power off the radio until this finishes.")
        try:
            with _graceful_interrupt():
                result = await flash(conn, bundle.data, _make_progress())
        except KeyboardInterrupt:
            _out("Stopped. The radio was told to discard the transfer; "
                 "re-run to start over, as it does not resume.")
            _out(f"The assembled image has been kept at {path}")
            return 130
        except Exception as e:
            _out()
            _out(f"error: {e}")
            _out(f"The assembled image has been kept at {path}")
            return 1
        _out()

        if result == "COMPLETE":
            _out("Firmware update complete.")
            return 0

    _out("  image staged, radio is rebooting")
    return await _commit_after_reboot(args, bundle.data, path)


async def _commit_after_reboot(
    args: argparse.Namespace, image: bytes, path: str
) -> int:
    """Reconnect to the rebooted radio and finish the update.

    The radio drops the connection when it reboots and comes back needing only
    the commit handshake. It stays in that state until it gets one, so a failed
    attempt can simply be retried.
    """
    for attempt in range(1, _COMMIT_ATTEMPTS + 1):
        await asyncio.sleep(_REBOOT_WAIT)
        try:
            async with _radio(args) as conn:
                if await flash(conn, image) == "COMPLETE":
                    _out()
                    _out("Firmware update complete.")
                    return 0
        except Exception as e:
            _out(f"  attempt {attempt}/{_COMMIT_ATTEMPTS} failed: {e}")

    _out()
    _out("error: the radio did not come back to finish the update.")
    _out("The image is already staged, so re-running `update` will resume "
         f"from here. The assembled image has been kept at {path}")
    return 1


async def _cmd_abort(args: argparse.Namespace) -> int:
    _out("This discards whatever update the radio has in progress.")
    if not _confirm("Abort it?", False, args.yes):
        return 0

    async with _radio(args) as conn:
        _print_device_info(await conn.get_device_info())
        await abort_update(conn)

    _out()
    _out("Aborted. The radio is still running its current firmware.")
    return 0


async def _cmd_flash(args: argparse.Namespace) -> int:
    with open(args.image, "rb") as f:
        image = f.read()

    _out(f"  image {args.image} ({len(image)} bytes)")
    _print_verdict(image, args.expect_md5, "--expect-md5")

    async with _radio(args) as conn:
        _print_device_info(await conn.get_device_info())

        _out()
        question = f"Flash {os.path.basename(args.image)} to this radio?"
        if not _confirm(question, False, args.yes):
            return 0

        _out("Do not power off the radio until this finishes.")
        try:
            with _graceful_interrupt():
                result = await flash(conn, image, _make_progress())
        except KeyboardInterrupt:
            _out("Stopped. The radio was told to discard the transfer; "
                 "re-run to start over, as it does not resume.")
            return 130
        except Exception as e:
            _out()
            _out(f"error: {e}")
            return 1
        _out()

        if result == "COMPLETE":
            _out("Firmware update complete.")
            return 0

    _out("  image staged, radio is rebooting")
    return await _commit_after_reboot(args, image, args.image)


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

    flash_cmd = subparsers.add_parser(
        "flash", help="flash an already-assembled image to a radio")
    _add_radio_args(flash_cmd)
    flash_cmd.add_argument("--image", required=True,
                           help="assembled firmware image to flash")
    flash_cmd.add_argument("--expect-md5", metavar="MD5",
                           help="verify the image against a known md5 first")
    flash_cmd.add_argument("--yes", "-y", action="store_true",
                           help="accept all prompts")
    flash_cmd.set_defaults(run=_cmd_flash)

    abort_cmd = subparsers.add_parser(
        "abort-update", help="discard an update the radio is partway through")
    _add_radio_args(abort_cmd)
    abort_cmd.add_argument("--yes", "-y", action="store_true",
                           help="accept all prompts")
    abort_cmd.set_defaults(run=_cmd_abort)

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
                               help="e.g. patch_base_to_vr_n76")
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
