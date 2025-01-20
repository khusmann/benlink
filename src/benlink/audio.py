from __future__ import annotations
import typing as t
from .link import AudioLink
from .internal import protocol as p


class AudioConnection:
    _link: AudioLink
    _buffer: bytes
    _handlers: list[t.Callable[[AudioMessage], None]]

    def is_connected(self) -> bool:
        return self._link.is_connected()

    def __init__(
        self,
        link: AudioLink,
    ):
        self._link = link
        self._buffer = bytes()
        self._handlers = []

    def add_handler(self, handler: t.Callable[[AudioMessage], None]) -> t.Callable[[], None]:
        def remove_handler():
            self._handlers.remove(handler)

        self._handlers.append(handler)

        return remove_handler

    async def send(self, msg: AudioMessage) -> None:
        # if sending audio data, wait for ack
        raise NotImplementedError()

    async def connect(self) -> None:
        def on_msg(msg: p.AudioMessage):
            for handler in self._handlers:
                # If data, send "ack" back
                handler(audio_message_from_protocol(msg))

        await self._link.connect(on_msg)

    async def disconnect(self) -> None:
        await self._link.disconnect()


class AudioData(t.NamedTuple):
    sbc_data: bytes


class AudioEnd:
    pass


class AudioAck:
    pass


class AudioError(t.NamedTuple):
    message: str


AudioMessage = AudioData | AudioEnd | AudioAck | AudioError


def audio_message_from_protocol(proto: p.AudioMessage) -> AudioMessage:
    match proto:
        case p.AudioData(sbc_data=sbc_data):
            return AudioData(sbc_data)
        case p.AudioEnd():
            return AudioEnd()
        case p.AudioAck():
            return AudioAck()
        case p.AudioError(message=message):
            return AudioError(message)


def audio_message_to_protocol(msg: AudioMessage) -> p.AudioMessage:
    match msg:
        case AudioData(sbc_data=sbc_data):
            return p.AudioData(sbc_data)
        case AudioEnd():
            return p.AudioEnd()
        case AudioAck():
            return p.AudioAck()
        case AudioError(message=message):
            return p.AudioError(message)
