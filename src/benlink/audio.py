"""
# Overview

Audio support is very much a work in progress. The radio uses SBC audio encoding, there doesn't exist
yet a good way to decode SBC in Python. At some point I'm looking into creating bindings for google's
libsbc, but that's a bit of a ways off. (Issue thread [here](https://github.com/khusmann/benlink/issues/11))

In the meantime I have a hacky approach for decoding via pyav (ffmpeg bindings for python). I have
two proofs of concept, one for receiving audio, the other for sending. To run the receiving audio
POC, run:

```
python -m benlink.examples.audiomonitor <UUID> <CHANNEL>
```

Where `<UUID>` is the UUID of the device you want to connect to, and `<CHANNEL>` is the RFCOMM audio channel.
When the radio receives audio, it will play the audio to the default audio output device using pyaudio.

Similarly, to run the sending audio POC, run:

```
python -m benlink.examples.audiotransmit <UUID> <CHANNEL>
```

This example uses pyaudio to record audio from the default audio input device and sends it to the radio.
"""

from __future__ import annotations
import typing as t
import asyncio
from .link import AudioLink, RfcommAudioLink
from . import protocol as p


class AudioConnection:
    _link: AudioLink
    _handlers: list[t.Callable[[AudioMessage], None]]

    def is_connected(self) -> bool:
        return self._link.is_connected()

    def __init__(
        self,
        link: AudioLink,
    ):
        self._link = link
        self._handlers = []

    @classmethod
    def new_rfcomm(cls, device_uuid: str, channel: int | t.Literal["auto"] = "auto") -> AudioConnection:
        return AudioConnection(
            RfcommAudioLink(device_uuid, channel)
        )

    def add_event_handler(self, handler: t.Callable[[AudioEvent], None]) -> t.Callable[[], None]:
        def on_message(msg: AudioMessage):
            if isinstance(msg, AudioEvent):
                handler(msg)
        return self._add_message_handler(on_message)

    def _add_message_handler(self, handler: t.Callable[[AudioMessage], None]) -> t.Callable[[], None]:
        def remove_handler():
            self._handlers.remove(handler)

        self._handlers.append(handler)

        return remove_handler

    async def send_message(self, msg: AudioMessage) -> None:
        await self._link.send(audio_message_to_protocol(msg))

    async def send_message_expect_reply(self, msg: AudioMessage, reply: t.Type[AudioMessageT]) -> AudioMessageT:
        queue: asyncio.Queue[AudioMessageT] = asyncio.Queue()

        def on_rcv(msg: AudioMessage):
            if isinstance(msg, reply):
                queue.put_nowait(msg)

        remove_handler = self._add_message_handler(on_rcv)

        await self.send_message(msg)

        out = await queue.get()

        remove_handler()

        return out

    async def connect(self) -> None:
        def on_msg(msg: p.AudioMessage):
            for handler in self._handlers:
                handler(audio_message_from_protocol(msg))
        await self._link.connect(on_msg)

    async def disconnect(self) -> None:
        await self._link.disconnect()

    # Audio API

    async def send_audio_data(self, sbc_data: bytes) -> None:
        # Radio does not send an ack for audio data
        await self.send_message(AudioData(sbc_data))

    async def send_audio_end(self) -> None:
        # Radio does not send an ack for audio end
        await self.send_message(AudioEnd())

    # Async Context Manager
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: t.Any,
        exc_value: t.Any,
        traceback: t.Any,
    ) -> None:
        # Send extra audio end message to ensure radio stops transmitting
        await self.send_audio_end()
        # Wait for the audio end message to be fully sent
        # before disconnecting, otherwise radio
        # gets stuck in transmit mode (no ack from radio, unfortunately)
        await asyncio.sleep(1.5)
        await self.disconnect()


class AudioData(t.NamedTuple):
    sbc_data: bytes


class AudioEnd:
    pass


class AudioAck:
    pass


class AudioUnknown(t.NamedTuple):
    type: int
    data: bytes


AudioEvent = AudioData | AudioEnd | AudioUnknown

AudioMessage = AudioEvent | AudioAck

AudioMessageT = t.TypeVar("AudioMessageT", bound=AudioMessage)


def audio_message_from_protocol(proto: p.AudioMessage) -> AudioMessage:
    match proto:
        case p.AudioData(sbc_data=sbc_data):
            return AudioData(sbc_data)
        case p.AudioEnd():
            return AudioEnd()
        case p.AudioAck():
            return AudioAck()
        case p.AudioUnknown(type=type, data=data):
            return AudioUnknown(type, data)


def audio_message_to_protocol(msg: AudioMessage) -> p.AudioMessage:
    match msg:
        case AudioData(sbc_data=sbc_data):
            return p.AudioData(sbc_data)
        case AudioEnd():
            return p.AudioEnd()
        case AudioAck():
            return p.AudioAck()
        case AudioUnknown(type=type, data=data):
            return p.AudioUnknown(type, data)
