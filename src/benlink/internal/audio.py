from __future__ import annotations
import sys
import typing as t
from .rfcomm import RfcommClient


def unescape_audio_frame(b: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(b):
        if b[i] == 0x7d:
            i += 1
            out.append(b[i] ^ 0x20)
        else:
            out.append(b[i])
        i += 1
    return bytes(out)


def read_audio_frame(b: bytes, framing_char: bytes = b'\x7e') -> t.Tuple[bytes | None, bytes]:
    start = b.find(framing_char)

    if start == -1:
        return None, b

    end = b.find(framing_char, start + 1)

    if end == -1:
        return None, b

    if start != 0:
        print("Warning: Discarding garbage data", file=sys.stderr)

    return b[start+1:end], b[end+1:]


def audio_frame_to_message(frame: bytes) -> AudioMessage:
    assert len(frame)
    match frame[0]:
        case 0x00:
            return AudioData(data=frame[1:])
        case 0x01:
            return AudioEnd()
        case 0x02:
            return AudioAck()
        case _:
            return AudioError(f"Unknown frame type: {frame}")


class AudioData(t.NamedTuple):
    data: bytes


class AudioEnd:
    pass


class AudioAck:
    pass


class AudioError(t.NamedTuple):
    error: str


AudioMessage = AudioData | AudioEnd | AudioAck | AudioError


class AudioConnection:
    _client: RfcommClient
    _buffer: bytes

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def __init__(
        self,
        client: RfcommClient,
    ):
        self._client = client
        self._buffer = bytes()

    async def connect(self, callback: t.Callable[[AudioMessage], None]) -> None:
        self._callback = callback

        def on_data(data: bytes) -> None:
            self._buffer = self._buffer + data

            if len(self._buffer) == 0:
                return

            while len(self._buffer):
                frame, self._buffer = read_audio_frame(self._buffer)

                if not frame:
                    return

                unescaped_frame = unescape_audio_frame(frame)

                message = audio_frame_to_message(unescaped_frame)

                self._callback(message)

        await self._client.connect(on_data)

    async def disconnect(self) -> None:
        await self._client.disconnect()

# CommandConnection(client: GaiaClient() | BleClient)

# AudioConnection(client: RfcommClient)
