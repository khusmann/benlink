from __future__ import annotations
import typing as t
import sys


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
        print("Warning: Discarding garbage audio data", file=sys.stderr)

    return b[start+1:end], b[end+1:]


def audio_frame_to_message(frame: bytes) -> AudioMessage:
    assert len(frame)
    match frame[0]:
        case 0x00:
            return AudioData(sbc_data=frame[1:])
        case 0x01:
            return AudioEnd()
        case 0x02:
            return AudioAck()
        case _:
            return AudioError(f"Unknown frame type: {frame}")


class AudioData(t.NamedTuple):
    sbc_data: bytes


class AudioEnd:
    pass


class AudioAck:
    pass


class AudioError(t.NamedTuple):
    message: str


AudioMessage = AudioData | AudioEnd | AudioAck | AudioError
