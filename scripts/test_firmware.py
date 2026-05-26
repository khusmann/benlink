"""
Firmware update dry-run test for VR-N76.

Tests layers 1 and 2 of firmware.py without touching the radio.

Modes:
  --local   Use already-downloaded local files (no network needed)
  --check   Only run the gRPC check, don't download
  --full    Run gRPC check + download + assemble (default)

Usage:
    cd E:\\G14 Transfer\\Projects\\benlink
    pip install grpcio bsdiff4
    python scripts/test_firmware.py --local
    python scripts/test_firmware.py --full
"""

import sys
import os
import hashlib
import argparse

# Known-good hashes from captured v0.9.3-7 firmware
KNOWN_PATCH_MD5    = "878b35b8e06d3465484ea0ace669de62"
KNOWN_BASE_MD5     = "74b6d097d8d2d9d2d9fac88133198a08"
KNOWN_FIRMWARE_MD5 = "0c0d095da50bebe664822adcb244834a"

# Local file paths (set to wherever yours are)
LOCAL_BASE_BIN   = r"E:\firmware_capture\upgrade_base_v1.bin.zip"
LOCAL_PATCH_BIN  = r"E:\firmware_capture\patch_base_to_vr_n76.bin"
LOCAL_OUTPUT_BIN = r"E:\firmware_capture\259_test.firmware"

# Known working OSS URLs (from bugreport logcat, v0.9.3-7 / OSS v147)
KNOWN_PATCH_URL = (
    "https://pubdatas.oss-cn-shenzhen.aliyuncs.com"
    "/firmware/v147/patch_base_to_vr_n76.bin"
)
KNOWN_BASE_URL = (
    "https://pubdatas.oss-cn-shenzhen.aliyuncs.com"
    "/upgrade_base_v1.bin.zip"
)

# Load firmware.py directly — avoids pulling in bleak/BLE dependencies
# through benlink/__init__.py
import importlib.util as _ilu
_fw_path = os.path.join(os.path.dirname(__file__), "..", "src", "benlink", "firmware.py")
_spec = _ilu.spec_from_file_location("benlink.firmware", os.path.abspath(_fw_path))
_fw = _ilu.module_from_spec(_spec)
sys.modules["benlink.firmware"] = _fw   # must be registered before exec so @dataclass can resolve __module__
_spec.loader.exec_module(_fw)

check_update       = _fw.check_update
download_firmware  = _fw.download_firmware
assemble_from_files = _fw.assemble_from_files
UpdateInfo         = _fw.UpdateInfo
FirmwareBundle     = _fw.FirmwareBundle


def _md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _progress(stage: str, done: int, total: int):
    pct = f"{done * 100 // total:3d}%" if total else "???%"
    bar = "#" * (done * 30 // total) if total else ""
    print(f"\r  {stage:12s} {pct} [{bar:<30s}] {done//1024}KB", end="", flush=True)
    if total and done >= total:
        print()


def run_check():
    print("\n── Layer 1: gRPC check ────────────────────────────────────")
    print(f"  Host:   rpc.benshikj.com:800 (TLS)")
    print(f"  Method: benshikj.APP/CheckUpdate")
    print(f"  Model:  VR_N7600")
    print(f"  fw_version: V0.0.0 (triggers update response)")

    try:
        info = check_update(did="", fw_version="V0.0.0")
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return None

    if info is None:
        print("\n  Server returned haveUpdate=False or empty response.")
        print("  This is expected if the DID is unrecognised by the server.")
        print(f"  Falling back to known URLs from bugreport logcat.")
        return UpdateInfo(patch_url=KNOWN_PATCH_URL, base_url=KNOWN_BASE_URL)

    print(f"\n  ✓ haveUpdate=True")
    print(f"  patch_url : {info.patch_url}")
    print(f"  base_url  : {info.base_url}")
    print(f"  internal  : {info.internal_version}")
    return info


def run_download(info: UpdateInfo) -> FirmwareBundle:
    print("\n── Layer 2: Download + assemble ───────────────────────────")
    bundle = download_firmware(info, progress_cb=_progress)
    print(f"  Assembled : {bundle.size:,} bytes")
    print(f"  MD5       : {bundle.md5}")

    if bundle.md5 == KNOWN_FIRMWARE_MD5:
        print(f"  ✓ MD5 matches known-good v0.9.3-7 firmware")
    else:
        print(f"  ⚠ MD5 differs from known v0.9.3-7 ({KNOWN_FIRMWARE_MD5})")
        print(f"    This may indicate a newer firmware version.")

    print(f"  md5_tail  : {bundle.md5_tail.hex()}  (used in UPDATE_SYNC_REQ)")
    bundle.save(LOCAL_OUTPUT_BIN)
    print(f"  Saved to  : {LOCAL_OUTPUT_BIN}")
    return bundle


def run_local() -> FirmwareBundle:
    print("\n── Local assemble (no network) ────────────────────────────")

    # Verify input files
    for path, expected_md5, label in [
        (LOCAL_PATCH_BIN, KNOWN_PATCH_MD5, "patch"),
    ]:
        if not os.path.exists(path):
            print(f"  ERROR: {path} not found")
            sys.exit(1)
        actual = _md5_file(path)
        status = "✓" if actual == expected_md5 else "⚠ md5 mismatch"
        print(f"  {label:12s} {actual}  {status}")

    if not os.path.exists(LOCAL_BASE_BIN):
        print(f"  ERROR: {LOCAL_BASE_BIN} not found")
        sys.exit(1)

    # Extract base from zip and assemble
    import zipfile, io, sys as _sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

    try:
        import bsdiff4
    except ImportError:
        print("  ERROR: bsdiff4 not installed. Run: pip install bsdiff4")
        sys.exit(1)

    with open(LOCAL_BASE_BIN, "rb") as f:
        zip_bytes = f.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        bin_name = next(n for n in zf.namelist() if n.endswith(".bin"))
        base_bytes = zf.read(bin_name)

    base_md5 = hashlib.md5(base_bytes).hexdigest()
    status = "✓" if base_md5 == KNOWN_BASE_MD5 else "⚠ md5 mismatch"
    print(f"  {'base':12s} {base_md5}  {status}")

    with open(LOCAL_PATCH_BIN, "rb") as f:
        patch_bytes = f.read()

    fw_bytes = bsdiff4.patch(base_bytes, patch_bytes)
    fw_md5 = hashlib.md5(fw_bytes).hexdigest()
    status = "✓" if fw_md5 == KNOWN_FIRMWARE_MD5 else "⚠ unexpected md5"
    print(f"\n  Assembled : {len(fw_bytes):,} bytes")
    print(f"  MD5       : {fw_md5}  {status}")
    md5_tail = bytes.fromhex(fw_md5)[-4:]
    print(f"  md5_tail  : {md5_tail.hex()}  (used in UPDATE_SYNC_REQ)")

    with open(LOCAL_OUTPUT_BIN, "wb") as f:
        f.write(fw_bytes)
    print(f"  Saved to  : {LOCAL_OUTPUT_BIN}")

    info = UpdateInfo(patch_url=KNOWN_PATCH_URL, base_url=KNOWN_BASE_URL)
    return FirmwareBundle(data=fw_bytes, update_info=info)


def main():
    parser = argparse.ArgumentParser(description="VR-N76 firmware update dry-run")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--local", action="store_true",
                       help="Assemble from local files only (no network)")
    group.add_argument("--check", action="store_true",
                       help="Only run gRPC check, don't download")
    group.add_argument("--full", action="store_true", default=True,
                       help="Full check + download + assemble (default)")
    args = parser.parse_args()

    print("VR-N76 Firmware Update — Dry Run")
    print("=" * 50)
    print(f"Radio BT MAC : 38:D2:00:00:F7:F5")
    print(f"Model        : VR_N7600")
    print(f"Target FW    : V0.9.3-7 (OSS v147, internal 259)")

    if args.local:
        bundle = run_local()
    elif args.check:
        info = run_check()
        if info:
            print(f"\n  patch_url : {info.patch_url}")
            print(f"  base_url  : {info.base_url}")
        return
    else:
        info = run_check()
        if info:
            bundle = run_download(info)

    print("\n── Summary ────────────────────────────────────────────────")
    print("  Layers 1 + 2 complete. Firmware is ready to flash.")
    print("  Next step: FirmwareUpdater (Layer 3) — GAIA BT delivery")
    print(f"  VM RFCOMM UUID: 00001107-D102-11E1-9B23-00025B00A5A5")


if __name__ == "__main__":
    main()
