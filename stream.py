from __future__ import annotations

Bit = bool


class BitStream:
    buffer: bytes
    cursor: int = 0

    def __init__(self, buffer: bytes):
        self.buffer = buffer

    def eof(self) -> bool:
        return self.available() < 1

    def read_bit(self) -> Bit:
        byte = self.buffer[self.cursor // 8]
        bit = Bit((byte >> (7 - self.cursor % 8)) & 1)
        self.cursor += 1
        return bit

    def available(self) -> int:
        return len(self.buffer) * 8 - self.cursor

    def read_int(self, n_bits: int) -> int:
        result = 0
        for _ in range(n_bits):
            result = (result << 1) | self.read_bit()
        return result

    def read_bool(self) -> bool:
        return bool(self.read_bit())

    def read_bytes(self, n_bytes: int) -> bytes:
        result = bytearray()
        for _ in range(n_bytes):
            result.append(self.read_int(8))
        return bytes(result)

    def read_string(self, n_bytes: int) -> str:
        return self.read_bytes(n_bytes).decode("utf-8")


class ByteStream:
    buffer: bytes
    cursor: int = 0

    def __init__(self, buffer: bytes):
        self.buffer = buffer

    def eof(self) -> bool:
        return self.available() < 1

    def available(self) -> int:
        return len(self.buffer) - self.cursor

    def read(self, n_bytes: int = 1) -> bytes:
        if self.available() < n_bytes:
            raise ValueError("Not enough bytes available to read")
        result = self.buffer[self.cursor:self.cursor + n_bytes]
        self.cursor += n_bytes
        return result

    def peek(self, n_bytes: int = 1) -> bytes:
        if self.available() < n_bytes:
            raise ValueError("Not enough bytes available to peek")
        return self.buffer[self.cursor:self.cursor + n_bytes]

    def append(self, data: bytes):
        self.buffer = self.buffer[self.cursor:] + data
        self.cursor = 0
