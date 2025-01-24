from __future__ import annotations
import typing as t
import socket
import asyncio
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from . import protocol as p
from .protocol.command.bitfield import BitStream

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
            raise NotImplementedError(
                "Auto channel selection not implemented yet"
            )
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
            raise NotImplementedError(
                "Auto channel selection not implemented yet"
            )
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
