from __future__ import annotations
import typing as t
import socket
import asyncio
import re
import shutil
import subprocess
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from . import protocol as p
from .protocol.command.bitfield import BitStream


# Benshi radios expose the command channel on a Bluetooth Classic
# "Serial Port" (SPP, UUID 0x1101) RFCOMM record and the audio channel on a
# vendor-specific record ("BS AOC", UUID 39144315-32fa-40db-85ed-fbfeba2d86e6).
SPP_SERVICE_UUID_SHORT = "1101"
SPP_SERVICE_UUID_LONG = "00001101-0000-1000-8000-00805f9b34fb"
BENSHI_AUDIO_SERVICE_UUID = "39144315-32fa-40db-85ed-fbfeba2d86e6"


_SHORT_UUID_RE = re.compile(
    r"^0000([0-9a-f]{4})-0000-1000-8000-00805f9b34fb$", re.IGNORECASE
)


def _service_uuid_forms(service_uuid: str) -> list[str]:
    """Return case-normalized forms of a Bluetooth service UUID.

    For the short (16-bit) UUID range we also add the ``0xXXXX`` textual form
    that ``sdptool`` emits inside Class ID lists.
    """
    low = service_uuid.lower()
    forms = [low]
    m = _SHORT_UUID_RE.match(low)
    if m:
        short = m.group(1)
        forms.extend([f"0x{short}", short])
    return forms


def _sdptool_records(device_uuid: str, attempts: int = 4) -> str | None:
    """Run ``sdptool records`` with retries for radios that sleep the BT stack.

    Benshi radios can respond ``Failed to connect to SDP server ...: Host is
    down`` on the first probe after idle, then start answering within a few
    seconds. Retry a handful of times before giving up.
    """
    if shutil.which("sdptool") is None:
        return None
    text = ""
    for i in range(attempts):
        try:
            out = subprocess.run(
                ["sdptool", "records", device_uuid],
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = (out.stdout or "") + "\n" + (out.stderr or "")
        if "Service RecHandle" in text:
            return text
        # Give the radio a moment to wake if we saw a "Host is down" reply.
        import time as _time
        _time.sleep(1.5)
    return text or None


def _sdptool_channel(device_uuid: str, service_uuid: str) -> int | None:
    """Look up the RFCOMM channel for ``service_uuid`` via ``sdptool``.

    Returns ``None`` if ``sdptool`` is unavailable, the device cannot be
    queried, or no matching record is present. Linux/BlueZ only.
    """
    text = _sdptool_records(device_uuid)
    if not text:
        return None
    forms = _service_uuid_forms(service_uuid)
    # sdptool emits one "Service RecHandle:" block per record; scan blocks
    # for the service UUID we care about and grab the RFCOMM channel.
    for block in re.split(r"(?=^Service RecHandle:)", text, flags=re.MULTILINE):
        low = block.lower()
        if not any(f in low for f in forms):
            continue
        m = re.search(r"\bChannel:\s*(\d+)\b", block)
        if m:
            return int(m.group(1))
    return None


def _bluetoothctl_channel(device_uuid: str, service_uuid: str) -> int | None:
    """Best-effort channel probe via ``bluetoothctl info``.

    ``bluetoothctl`` exposes advertised service UUIDs but does not include the
    RFCOMM channel, so this helper only confirms the service is present on the
    device. Returns ``None`` when we can't confirm.
    """
    if shutil.which("bluetoothctl") is None:
        return None
    try:
        out = subprocess.run(
            ["bluetoothctl", "--", "info", device_uuid],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if service_uuid.lower() in (out.stdout or "").lower():
        # We know the record is there; the caller should have already tried
        # ``sdptool``. Fall through to raise a helpful error.
        return None
    return None


def _resolve_rfcomm_channel(device_uuid: str, service_uuid: str) -> int:
    """Resolve the RFCOMM channel for ``service_uuid`` on ``device_uuid``.

    Currently Linux-only; falls back to a clear ``NotImplementedError`` on
    other platforms so callers can supply the channel explicitly.
    """
    ch = _sdptool_channel(device_uuid, service_uuid)
    if ch is not None:
        return ch
    # Confirm the record is at least advertised, to give a better error.
    _bluetoothctl_channel(device_uuid, service_uuid)
    raise NotImplementedError(
        "Auto RFCOMM channel selection requires the Linux ``sdptool`` utility"
        " (from bluez); could not resolve service "
        f"{service_uuid} on {device_uuid}. Pass channel=<int> explicitly."
    )

##################################################
# CommandLink


class CommandLink(t.Protocol):
    def is_connected(self) -> bool:
        ...

    async def send_bytes(self, data: bytes) -> None:
        ...

    async def send(self, msg: p.Message) -> None:
        ...

    async def connect(self, callback: t.Callable[[p.Message], None]) -> None:
        ...

    async def disconnect(self) -> None:
        ...


RADIO_SERVICE_UUID = "00001100-d102-11e1-9b23-00025b00a5a5"
"""@private"""

RADIO_WRITE_UUID = "00001101-d102-11e1-9b23-00025b00a5a5"
"""@private"""

RADIO_INDICATE_UUID = "00001102-d102-11e1-9b23-00025b00a5a5"
"""@private"""


class BleCommandLink:
    _client: BleakClient

    def is_connected(self) -> bool:
        return self._client.is_connected

    def __init__(self, device_uuid: str):
        self._client = BleakClient(device_uuid)

    async def send(self, msg: p.Message):
        await self.send_bytes(msg.to_bytes())

    async def send_bytes(self, data: bytes):
        await self._client.write_gatt_char(RADIO_WRITE_UUID, data, response=True)

    async def connect(self, callback: t.Callable[[p.Message], None]):
        await self._client.connect()

        def on_data(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
            assert characteristic.uuid == RADIO_INDICATE_UUID
            callback(p.Message.from_bytes(data))

        await self._client.start_notify(RADIO_INDICATE_UUID, on_data)

    async def disconnect(self):
        await self._client.stop_notify(RADIO_INDICATE_UUID)
        await self._client.disconnect()


class RfcommCommandLink:
    _client: RfcommClient
    _buffer: BitStream

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def __init__(
        self,
        device_uuid: str,
        channel: int | t.Literal["auto"] = "auto",
        read_size: int = 1024
    ):
        if channel == "auto":
            channel = _resolve_rfcomm_channel(device_uuid, SPP_SERVICE_UUID_LONG)
        self._client = RfcommClient(device_uuid, channel, read_size)
        self._buffer = BitStream()

    async def send(self, msg: p.Message):
        msg_bytes = msg.to_bytes()

        gaia_frame = p.GaiaFrame(
            flags=p.GaiaFlags.NONE,
            # Don't count the command_group and command_id bytes
            n_bytes_payload=len(msg_bytes) - 4,
            data=msg_bytes,
        )

        await self.send_bytes(gaia_frame.to_bytes())

    async def send_bytes(self, data: bytes):
        await self._client.write(data)

    async def connect(self, callback: t.Callable[[p.Message], None]):
        def on_data(data: bytes):
            self._buffer = self._buffer.extend_bytes(data)

            gaia_frames, self._buffer = p.GaiaFrame.from_bitstream_batch(
                self._buffer
            )

            for gaia_frame in gaia_frames:
                callback(p.Message.from_bytes(gaia_frame.data))

        await self._client.connect(on_data)

    async def disconnect(self):
        await self._client.disconnect()

##################################################
# AudioLink


class AudioLink(t.Protocol):
    def is_connected(self) -> bool:
        ...

    async def send(self, msg: p.AudioMessage) -> None:
        ...

    async def connect(self, callback: t.Callable[[p.AudioMessage], None]) -> None:
        ...

    async def disconnect(self) -> None:
        ...


class RfcommAudioLink:
    _client: RfcommClient
    _buffer: bytes

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def __init__(
        self,
        device_uuid: str,
        channel: int | t.Literal["auto"] = "auto",
        read_size: int = 1024
    ):
        if channel == "auto":
            channel = _resolve_rfcomm_channel(device_uuid, BENSHI_AUDIO_SERVICE_UUID)
        self._client = RfcommClient(device_uuid, channel, read_size)
        self._buffer = bytes()

    async def send(self, msg: p.AudioMessage) -> None:
        await self.send_bytes(p.audio_message_to_bytes(msg))

    async def send_bytes(self, data: bytes) -> None:
        await self._client.write(data)

    async def connect(self, callback: t.Callable[[p.AudioMessage], None]):
        def on_data(data: bytes):
            self._buffer = self._buffer + data

            if len(self._buffer) == 0:
                return

            while len(self._buffer):
                message, self._buffer = p.next_audio_message(self._buffer)

                if message is None:
                    break

                callback(message)

        await self._client.connect(on_data)

    async def disconnect(self):
        await self._client.disconnect()

##################################################
# RfcommClient


class SocketTask(t.NamedTuple):
    socket_handle: socket.socket
    listen_task: asyncio.Task[None]


class RfcommClient:
    _device_uuid: str
    _channel: int
    _read_size: int
    _st: SocketTask | None

    @property
    def device_uuid(self) -> str:
        return self._device_uuid

    @property
    def channel(self) -> int:
        return self._channel

    def is_connected(self) -> bool:
        return self._st is not None

    async def write(self, data: bytes):
        if self._st is None:
            raise RuntimeError("Not connected")

        loop = asyncio.get_event_loop()

        await loop.sock_sendall(self._st.socket_handle, data)

    def __init__(
        self,
        device_uuid: str,
        channel: int,
        read_size: int = 1024
    ):
        self._device_uuid = device_uuid
        self._channel = channel
        self._read_size = read_size
        self._st = None

    async def connect(
        self,
        callback: t.Callable[[bytes], None],
    ):
        loop = asyncio.get_event_loop()

        if self._st is not None:
            raise RuntimeError("Already connected")

        socket_handle = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )

        socket_handle.setblocking(False)

        await loop.sock_connect(socket_handle, (self._device_uuid, self._channel))

        async def listen():
            while True:
                data = await loop.sock_recv(socket_handle, self._read_size)
                if not data:
                    self._st = None
                    break
                callback(data)

        listen_task = loop.create_task(listen())

        self._st = SocketTask(socket_handle, listen_task)

    async def disconnect(self):
        if self._st is None:
            raise RuntimeError("Not connected")

        self._st.listen_task.cancel()
        try:
            await self._st.listen_task
        except asyncio.CancelledError:
            pass

        self._st.socket_handle.close()

        self._st = None
