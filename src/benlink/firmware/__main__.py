"""Command line interface for `benlink.firmware`.

Run with `python -m benlink.firmware`.
"""

from __future__ import annotations
import typing as t
import argparse
import asyncio
import hashlib
import sys

from . import (
    DEFAULT_BASE_VERSION,
    DEFAULT_PATCH_NAME,
    PRODUCTS,
    FirmwareInfo,
    UpdateInfo,
    assemble,
    check_update,
    download_firmware,
    oss_update_info,
)


def _make_progress() -> t.Callable[[str, int, int], None]:
    """Render concurrent downloads as one updating line."""
    state: t.Dict[str, t.Tuple[int, int]] = {}

    def progress(label: str, done: int, total: int) -> None:
        state[label] = (done, total)
        line = "  ".join(
            f"{k} {100 * d // n}%" if n else f"{k} {d}B"
            for k, (d, n) in state.items()
        )
        print(f"\r{line}", end="", file=sys.stderr, flush=True)

    return progress


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

    bundle = await download_firmware(info, _make_progress(), base)
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
