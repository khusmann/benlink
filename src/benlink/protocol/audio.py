from __future__ import annotations
import typing as t
import sys


def unescape_bytes(b: bytes) -> bytes:
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


def escape_bytes(b: bytes) -> bytes:
    out = bytearray()
    for byte in b:
        if byte in (0x7d, 0x7e):
            out.append(0x7d)
            out.append(byte ^ 0x20)
        else:
            out.append(byte)
    return bytes(out)


def framed_read_bytes(b: bytes, framing_char: bytes) -> t.Tuple[bytes | None, bytes]:
    start = b.find(framing_char)

    if start == -1:
        return None, b

    end = b.find(framing_char, start + 1)

    if end == -1:
        return None, b

    if start != 0:
        print("Warning: Discarding garbage audio data", file=sys.stderr)

    return b[start:end+1], b[end+1:]


def next_audio_message(b: bytes) -> t.Tuple[AudioMessage | None, bytes]:
    frame, rest = framed_read_bytes(b, b'\x7e')
    if frame is None:
        return None, rest
    return audio_message_from_bytes(frame), rest


def audio_message_from_bytes(frame: bytes) -> AudioMessage:
    assert len(frame) > 3
    assert frame[0] == 0x7e
    assert frame[-1] == 0x7e

    unescaped_frame = unescape_bytes(frame[1:-1])

    match unescaped_frame[0]:
        case 0x00:
            return AudioData(sbc_data=unescaped_frame[1:])
        case 0x01:
            return AudioEnd()
        case 0x02:
            return AudioAck()
        case _:
            return AudioUnknown(type=unescaped_frame[0], data=unescaped_frame[1:])


def audio_message_to_bytes(msg: AudioMessage) -> bytes:
    match msg:
        case AudioData(sbc_data=sbc_data):
            unescaped_frame = b'\x00' + sbc_data
        case AudioEnd():
            unescaped_frame = b'\x01' + b'\x00' * 8
        case AudioAck():
            unescaped_frame = b'\x02' + b'\x00' * 8
        case AudioUnknown(type=type, data=data):
            unescaped_frame = bytes([type]) + data

    return b'\x7e' + escape_bytes(unescaped_frame) + b'\x7e'


class AudioData(t.NamedTuple):
    sbc_data: bytes


class AudioEnd:
    pass


class AudioAck:
    pass


class AudioUnknown(t.NamedTuple):
    type: int
    data: bytes


AudioMessage = AudioData | AudioEnd | AudioAck | AudioUnknown
