import socket
import asyncio
import typing as t


class SocketTask(t.NamedTuple):
    socket_handle: socket.socket
    listen_task: asyncio.Task[None]


class RfcommStream:
    _device_uuid: str
    _channel: int
    _read_size: int
    _callback: t.Callable[[bytes], None]
    _st: SocketTask | None

    @property
    def device_uuid(self) -> str:
        return self._device_uuid

    @property
    def channel(self) -> int:
        return self._channel

    def is_connected(self) -> bool:
        return self._st is not None

    def __init__(
        self,
        device_uuid: str,
        channel: int,
        callback: t.Callable[[bytes], None],
        read_size: int = 1024
    ):
        self._device_uuid = device_uuid
        self._channel = channel
        self._read_size = read_size
        self._callback = callback
        self._st = None

    async def connect(self, loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
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
                self._callback(data)

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
