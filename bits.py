from __future__ import annotations
import typing as t


def reorder_pairs(order: t.Sequence[int], size: int):
    if not all(i < size for i in order) or not all(i > 0 for i in order):
        raise ValueError(
            f"some indices in the reordering are out-of-bounds"
        )

    order_set = frozenset(order)

    if len(order_set) != len(order):
        raise ValueError(
            f"duplicate indices in reordering"
        )

    return zip(
        range(size),
        (*order, *(i for i in range(size) if i not in order_set))
    )


class Bits(t.Tuple[bool, ...]):
    @t.overload
    def __getitem__(self, index: t.SupportsIndex) -> bool:
        ...

    @t.overload
    def __getitem__(self, index: slice) -> Bits:
        ...

    def __getitem__(self, index: t.SupportsIndex | slice) -> bool | Bits:
        if isinstance(index, slice):
            return Bits(super().__getitem__(index))
        return super().__getitem__(index)

    def __add__(self, other: t.Tuple[object, ...]) -> Bits:
        return Bits(super().__add__(tuple(bool(bit) for bit in other)))

    def __repr__(self) -> str:
        str_bits = "".join(str(int(bit)) for bit in self)
        return f"0b{str_bits}"

    def reorder(self, order: t.Sequence[int]):
        if not order:
            return self

        pairs = reorder_pairs(order, len(self))

        return Bits(self[i] for _, i in pairs)

    def unreorder(self, order: t.Sequence[int]):
        if not order:
            return self

        pairs = sorted(reorder_pairs(order, len(self)), key=lambda x: x[1])

        return Bits(self[i] for i, _ in pairs)

    @classmethod
    def from_str(cls, data: str) -> Bits:
        return cls.from_bytes(data.encode("utf-8"))

    @classmethod
    def from_bytes(cls, data: bytes) -> Bits:
        bits: t.List[bool] = []
        for byte in data:
            bits += cls.from_int(byte, 8)
        return cls(bits)

    @classmethod
    def from_int(cls, value: int, n_bits: int) -> Bits:
        if n_bits <= 0:
            raise ValueError("Number of bits must be positive")
        if value >= 1 << n_bits:
            raise ValueError(f"Value {value} is too large for {n_bits} bits")
        return cls(
            value & (1 << (n_bits - i - 1)) != 0 for i in range(n_bits)
        )

    def to_int(self) -> int:
        out = 0
        for i, bit in enumerate(self):
            out |= bit << (len(self) - i - 1)
        return out

    def to_bytes(self) -> bytes:
        if len(self) % 8:
            raise ValueError("Bits is not byte aligned (multiple of 8 bits)")
        return bytes(self[i:i+8].to_int() for i in range(0, len(self), 8))

    def to_str(self) -> str:
        return self.to_bytes().decode("utf-8")


class BitStream:
    _bits: Bits
    _pos: int

    def __init__(self, bits: Bits = Bits(), pos: int = 0) -> None:
        self._bits = bits
        self._pos = pos

    def remaining(self):
        return len(self._bits) - self._pos

    def take(self, n: int):
        if n > self.remaining():
            raise EOFError

        return self._bits[self._pos:n+self._pos], BitStream(self._bits, self._pos+n)

    def __repr__(self) -> str:
        str_bits = "".join(str(int(bit)) for bit in self._bits[self._pos:])
        return f"{self.__class__.__name__}({str_bits})"

    def extend(self, other: Bits):
        return BitStream(
            self._bits[self._pos:] + other,
        )


class BitStreamOld:
    _bits: Bits
    _pos: int

    def __init__(self, bits: Bits = Bits(), pos: int = 0) -> None:
        self._bits = bits
        self._pos = pos

    @classmethod
    def from_bytes(cls, data: bytes) -> BitStreamOld:
        return cls(Bits.from_bytes(data))

    def extend(self, data: Bits) -> None:
        self._bits += data

    def extend_bytes(self, data: bytes) -> None:
        self.extend(Bits.from_bytes(data))

    def rebase(self):
        if self._pos != 0:
            self._bits = self._bits[self._pos:]
            self._pos = 0

    def is_byte_aligned(self) -> bool:
        return self._pos % 8 == 0

    def remaining(self) -> int:
        return len(self._bits) - self._pos

    def _assert_advance(self, n_bits: int) -> None:
        if n_bits < 0:
            raise ValueError("Number of bits to advance must be non-negative")
        if n_bits > self.remaining():
            raise EOFError

    def advance(self, n_bits: int) -> None:
        self._assert_advance(n_bits)
        self._pos += n_bits

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int) -> None:
        if pos < 0:
            raise ValueError("Position must be non-negative")
        if pos > len(self._bits):
            raise EOFError
        self._pos = pos

    def peek_bits(self, n_bits: int) -> Bits:
        self._assert_advance(n_bits)
        return self._bits[self._pos:self._pos+n_bits]

    def read_bits(self, n_bits: int) -> Bits:
        out = self.peek_bits(n_bits)
        self.advance(n_bits)
        return out

    def peek_bool(self) -> bool:
        return self.peek_bits(1)[0]

    def read_bool(self) -> bool:
        return self.read_bits(1)[0]

    def peek_int(self, n_bits: int):
        return self.peek_bits(n_bits).to_int()

    def read_int(self, n_bits: int):
        out = self.peek_int(n_bits)
        self.advance(n_bits)
        return out

    def peek_bytes(self, n_bytes: int):
        return self.peek_bits(n_bytes * 8).to_bytes()

    def read_bytes(self, n_bytes: int):
        out = self.peek_bytes(n_bytes)
        self.advance(n_bytes * 8)
        return out

    def peek_str(self, n_bytes: int, encoding: str = "utf-8"):
        return self.peek_bytes(n_bytes).decode(encoding)

    def read_str(self, n_bytes: int, encoding: str = "utf-8"):
        return self.read_bytes(n_bytes).decode(encoding)


class AttrProxy(t.Mapping[str, t.Any]):
    _data: t.Dict[str, t.Any]

    def __init__(self, data: t.Mapping[str, t.Any] = {}) -> None:
        self._data = dict(data)

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, value: t.Any):
        self._data[key] = value

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getattr__(self, key: str):
        if key in self._data:
            return self._data[key]
        raise AttributeError(
            f"'AttrProxy' object has no attribute '{key}'"
        )

    def __repr__(self):
        return f"AttrProxy({self._data})"
