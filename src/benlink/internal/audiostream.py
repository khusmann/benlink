import socket
import asyncio
import typing as t


class SocketTask(t.NamedTuple):
    socket: socket.socket
    listen_task: asyncio.Task[None]


class RfcommStream:
    _device_uuid: str
    _channel: int
    _read_size: int
    _on_recv: t.Callable[[bytes], None]
    _on_disconnect: t.Callable[[], None]
    _st: SocketTask | None = None

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
        on_recv: t.Callable[[bytes | None], None],
        on_disconnect: t.Callable[[], None] = lambda: None,
        read_size: int = 1024
    ):
        self._device_uuid = device_uuid
        self._channel = channel
        self._read_size = read_size
        self._on_recv = on_recv
        self._on_disconnect = on_disconnect

    async def connect(self, loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        if self._st is not None:
            raise RuntimeError("Already connected")

        skt = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )

        skt.setblocking(False)

        await loop.sock_connect(skt, (self._device_uuid, self._channel))

        async def listen():
            while True:
                data = await loop.sock_recv(skt, self._read_size)
                if data:
                    self._on_recv(data)
                else:
                    self._on_disconnect()
                    break

        listen_task = loop.create_task(listen())

        self._st = SocketTask(skt, listen_task)

    async def disconnect(self):
        if self._st is None:
            raise RuntimeError("Not connected")

        self._st.listen_task.cancel()
        self._st.socket.close()
