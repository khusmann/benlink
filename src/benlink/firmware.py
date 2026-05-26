"""
# VR-N76 Firmware Update Support

This module provides three layers of firmware update support:

1. **Check** — query `rpc.benshikj.com:800` (gRPC, TLS) for available updates
2. **Download** — fetch patch + base zip from Alibaba Cloud OSS, assemble via bsdiff4
3. **Flash** — deliver assembled firmware to the radio over the GAIA VM RFCOMM channel
   (UUID `00001107-D102-11E1-9B23-00025B00A5A5`)

Layer 3 (FirmwareUpdater) is a work-in-progress — layers 1 and 2 are fully implemented.

## Quick start

```python
from benlink.firmware import fetch_firmware

bundle = fetch_firmware(fw_version="V0.9.2-7")
if bundle:
    print(f"Update available: {bundle.size} bytes, md5={bundle.md5}")
    # bundle.data contains the assembled .firmware bytes ready to flash
```

## Notes on the gRPC endpoint

- Host: `rpc.benshikj.com:800` (TLS on port 800, not 443)
- Service: `benshikj.APP`, method: `CheckUpdate`
- The `did` field is the factory device ID (from radio Status menu S/N).
  The server returns URLs regardless of whether `did` is recognized —
  it returns `haveUpdate=False` only when the model+version combo has no update.
- Both the patch URL and base zip URL are returned in the response.

## OSS URL structure (as of v0.9.3-7)

- Patch: `https://pubdatas.oss-cn-shenzhen.aliyuncs.com/firmware/v{N}/patch_base_to_vr_n76.bin`
- Base:  `https://pubdatas.oss-cn-shenzhen.aliyuncs.com/upgrade_base_v{N}.bin.zip`

The internal version `N` (e.g. 147) differs from the user-facing version string (e.g. V0.9.3-7).
The base image version (v1 as of 2025-04-28) is independent of the firmware version —
the same base is shared across multiple firmware releases.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
import typing as t
from dataclasses import dataclass, field

# ── Optional dependency guards ──────────────────────────────────────────────

def _require_grpc():
    try:
        import grpc
        return grpc
    except ImportError:
        raise ImportError(
            "grpcio is required for firmware update checks. "
            "Install with: pip install grpcio"
        )


def _require_bsdiff4():
    try:
        import bsdiff4
        return bsdiff4
    except ImportError:
        raise ImportError(
            "bsdiff4 is required to assemble firmware. "
            "Install with: pip install bsdiff4"
        )


# ── gRPC / proto constants ───────────────────────────────────────────────────

_GRPC_HOST    = "rpc.benshikj.com:800"
_GRPC_METHOD  = "/benshikj.APP/CheckUpdate"
_MODEL        = "VR_N7600"


# ── Minimal proto3 wire-format encoder / decoder ────────────────────────────
# Avoids grpcio-tools / protoc as a runtime dependency.

def _varint(n: int) -> bytes:
    out = []
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n & 0x7F)
    return bytes(out) if out else b'\x00'


def _encode_string_field(field_num: int, s: str) -> bytes:
    b = s.encode("utf-8")
    tag = (field_num << 3) | 2          # wire type 2 = length-delimited
    return bytes([tag]) + _varint(len(b)) + b


def _encode_check_request(did: str, fw_version: str, model: str) -> bytes:
    """Encode CheckFirmwareUpdateRequest { did=1, firmwareVersion=2, model=3 }"""
    return (
        _encode_string_field(1, did)
        + _encode_string_field(2, fw_version)
        + _encode_string_field(3, model)
    )


def _decode_proto_fields(data: bytes) -> t.List[t.Tuple[int, int, bytes]]:
    """
    Decode proto3 wire fields.
    Returns list of (field_number, wire_type, raw_value_bytes).
    wire_type 0 = varint, wire_type 2 = length-delimited (string/bytes/message).
    """
    out: t.List[t.Tuple[int, int, bytes]] = []
    pos = 0
    n = len(data)

    def read_varint() -> int:
        nonlocal pos
        val = shift = 0
        while pos < n:
            b = data[pos]; pos += 1
            val |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                return val
        return val

    while pos < n:
        tag = read_varint()
        field_num = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 0:          # varint
            val = read_varint()
            out.append((field_num, wire_type, _varint(val)))
        elif wire_type == 2:        # length-delimited
            length = read_varint()
            out.append((field_num, wire_type, data[pos: pos + length]))
            pos += length
        elif wire_type == 5:        # 32-bit fixed
            out.append((field_num, wire_type, data[pos: pos + 4]))
            pos += 4
        elif wire_type == 1:        # 64-bit fixed
            out.append((field_num, wire_type, data[pos: pos + 8]))
            pos += 8
        else:
            break                   # unknown — stop gracefully

    return out


def _extract_urls(data: bytes) -> t.List[str]:
    """
    Recursively walk proto fields and collect all HTTPS URL strings.
    Works regardless of whether the server puts URLs in one or two sub-messages.
    """
    urls: t.List[str] = []
    for _, wire_type, value in _decode_proto_fields(data):
        if wire_type == 2:
            # Try to decode as UTF-8 string first
            try:
                s = value.decode("utf-8")
                if s.startswith("https://"):
                    urls.append(s)
                    continue
            except UnicodeDecodeError:
                pass
            # Otherwise recurse — might be a nested message
            urls.extend(_extract_urls(value))
    return urls


def _decode_have_update(data: bytes) -> bool:
    """Extract field 1 (bool haveUpdate) from CheckFirmwareUpdateResult."""
    for field_num, wire_type, value in _decode_proto_fields(data):
        if field_num == 1 and wire_type == 0:
            return bool(int.from_bytes(value[:1], "little"))
    return False


# ── Public data types ────────────────────────────────────────────────────────

@dataclass
class UpdateInfo:
    """URLs returned by the server for an available firmware update."""
    patch_url: str
    base_url: str

    @property
    def internal_version(self) -> str:
        """Best-effort parse of OSS internal version (e.g. 'v147')."""
        import re
        m = re.search(r"/firmware/(v\d+)/", self.patch_url)
        return m.group(1) if m else "unknown"


@dataclass
class FirmwareBundle:
    """Assembled, ready-to-flash firmware image."""
    data: bytes
    update_info: UpdateInfo
    base_md5: str = field(init=False)

    def __post_init__(self):
        self.base_md5 = hashlib.md5(self.data).hexdigest()

    @property
    def md5(self) -> str:
        return self.base_md5

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def md5_tail(self) -> bytes:
        """Last 4 bytes of md5 digest — used in UPDATE_SYNC_REQ."""
        return bytes.fromhex(self.base_md5)[-4:]

    def save(self, path: str) -> None:
        """Write assembled firmware to disk."""
        with open(path, "wb") as f:
            f.write(self.data)


ProgressCallback = t.Callable[[str, int, int], None]
"""progress_cb(stage: str, bytes_done: int, bytes_total: int)"""


# ── Layer 1: Check ───────────────────────────────────────────────────────────

def check_update(
    did: str = "",
    fw_version: str = "V0.0.0",
) -> t.Optional[UpdateInfo]:
    """
    Query the Benshikj gRPC endpoint for an available firmware update.

    Args:
        did: Device ID from radio Status menu (S/N field). Optional — the
             server currently returns URLs regardless of DID value.
        fw_version: Current firmware version string (e.g. "V0.9.2-7").
                    Use "V0.0.0" to always trigger an update response.

    Returns:
        UpdateInfo with patch_url and base_url if an update is available,
        None if the server says haveUpdate=False or returns an empty response.

    Raises:
        ImportError: if grpcio is not installed.
        RuntimeError: on gRPC transport errors.
    """
    grpc = _require_grpc()

    creds = grpc.ssl_channel_credentials()
    channel = grpc.secure_channel(_GRPC_HOST, creds)

    try:
        req_bytes = _encode_check_request(did, fw_version, _MODEL)
        resp_bytes: bytes = channel.unary_unary(
            _GRPC_METHOD,
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )(req_bytes, timeout=10)
    except Exception as exc:
        grpc_module = _require_grpc()
        if isinstance(exc, grpc_module.RpcError):
            raise RuntimeError(
                f"gRPC error: {exc.code()} — {exc.details()}"
            ) from exc
        raise
    finally:
        channel.close()

    if not resp_bytes:
        return None

    if not _decode_have_update(resp_bytes):
        return None

    urls = _extract_urls(resp_bytes)
    if len(urls) < 2:
        return None

    patch_url = next((u for u in urls if "patch" in u), urls[0])
    base_url  = next((u for u in urls if "base"  in u and "patch" not in u),
                     next((u for u in urls if u != patch_url), None))

    if not base_url:
        return None

    return UpdateInfo(patch_url=patch_url, base_url=base_url)


# ── Layer 2: Download + assemble ─────────────────────────────────────────────

def download_firmware(
    update_info: UpdateInfo,
    progress_cb: t.Optional[ProgressCallback] = None,
) -> FirmwareBundle:
    """
    Download patch + base zip from OSS and assemble the final firmware image.

    Args:
        update_info: URLs returned by check_update().
        progress_cb: Optional progress callback (stage, bytes_done, bytes_total).

    Returns:
        FirmwareBundle with assembled firmware bytes and md5.

    Raises:
        ImportError: if bsdiff4 is not installed.
        RuntimeError: on download or patch errors.
    """
    import urllib.request

    bsdiff4 = _require_bsdiff4()

    def _fetch(url: str, label: str) -> bytes:
        with urllib.request.urlopen(url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            chunks: t.List[bytes] = []
            received = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)
                if progress_cb:
                    progress_cb(label, received, total)
        return b"".join(chunks)

    patch_bytes    = _fetch(update_info.patch_url, "patch")
    base_zip_bytes = _fetch(update_info.base_url,  "base_zip")

    # Extract upgrade_base.bin from the zip
    with zipfile.ZipFile(io.BytesIO(base_zip_bytes)) as zf:
        bin_names = [n for n in zf.namelist() if n.endswith(".bin")]
        if not bin_names:
            raise RuntimeError("No .bin file found inside base zip")
        base_bytes = zf.read(bin_names[0])

    # Apply BSDIFF40 patch
    if not patch_bytes[:8] == b"BSDIFF40":
        raise RuntimeError(
            f"Unexpected patch magic: {patch_bytes[:8]!r} (expected b'BSDIFF40')"
        )

    firmware_bytes = bsdiff4.patch(base_bytes, patch_bytes)

    return FirmwareBundle(data=firmware_bytes, update_info=update_info)


# ── Layer 2 (offline): assemble from local files ─────────────────────────────

def assemble_from_files(
    base_bin_path: str,
    patch_bin_path: str,
) -> bytes:
    """
    Assemble firmware locally from already-downloaded files.
    Useful for testing without hitting the network.

    Args:
        base_bin_path: Path to upgrade_base.bin (extracted from zip).
        patch_bin_path: Path to patch_base_to_vr_n76.bin.

    Returns:
        Assembled firmware bytes.
    """
    bsdiff4 = _require_bsdiff4()

    with open(base_bin_path, "rb") as f:
        base_bytes = f.read()
    with open(patch_bin_path, "rb") as f:
        patch_bytes = f.read()

    if patch_bytes[:8] != b"BSDIFF40":
        raise RuntimeError(
            f"Unexpected patch magic: {patch_bytes[:8]!r}"
        )

    return bsdiff4.patch(base_bytes, patch_bytes)


# ── Layer 1+2 combined ───────────────────────────────────────────────────────

def fetch_firmware(
    did: str = "",
    fw_version: str = "V0.0.0",
    progress_cb: t.Optional[ProgressCallback] = None,
) -> t.Optional[FirmwareBundle]:
    """
    Check for an update and, if one is available, download and assemble it.

    Args:
        did: Device ID (radio S/N). Optional.
        fw_version: Current firmware version. Use "V0.0.0" to always fetch.
        progress_cb: Optional (stage, bytes_done, bytes_total) callback.

    Returns:
        FirmwareBundle if an update is available and downloaded, else None.
    """
    info = check_update(did=did, fw_version=fw_version)
    if info is None:
        return None
    return download_firmware(info, progress_cb=progress_cb)


# ── Layer 3: GAIA BT delivery ─────────────────────────────────────────────────
# TODO: implement FirmwareUpdater state machine
#
# The GAIA firmware update uses a SEPARATE RFCOMM channel from the main
# command channel:
#   VM UUID: 00001107-D102-11E1-9B23-00025B00A5A5
#
# Protocol flow (from vm.py):
#   VM_CONNECT
#   → UPDATE_SYNC_REQ (md5_tail = bundle.md5_tail)
#   ← UPDATE_SYNC_CFM
#   → UPDATE_START_REQ
#   ← UPDATE_START_CFM  (code=OK → continue, code=GOTO_NEXT_STATE → jump to reconnect)
#   → UPDATE_DATA_START_REQ
#   ← UPDATE_DATA_BYTES_REQ (device requests N bytes at offset skip)
#   → UPDATE_DATA (145-byte chunks, is_final_fragment=True on last)
#   → UPDATE_IS_VALIDATION_DONE_REQ
#   ← UPDATE_TRANSFER_COMPLETE_IND
#   → UPDATE_TRANSFER_COMPLETE_RES(is_complete=True)
#   [radio reboots]
#   VM_CONNECT
#   → UPDATE_SYNC_REQ
#   ← UPDATE_SYNC_CFM
#   → UPDATE_START_REQ
#   ← UPDATE_START_CFM (GOTO_NEXT_STATE)
#   → UPDATE_IN_PROGRESS_RES
#   ← UPDATE_COMPLETE_IND
#   VM_DISCONNECT
