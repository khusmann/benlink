import typing as t
from typing_extensions import dataclass_transform
from collections.abc import Mapping


class AttrProxy(Mapping[str, t.Any]):
    _data: t.Mapping[str, t.Any]

    def __init__(self, **kwargs: t.Mapping[str, t.Any]) -> None:
        self._data = kwargs

    def __getitem__(self, key: str):
        return self._data[key]

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


class Bitfield:
    n_fn: t.Callable[[t.Any], int]

    def __init__(self, n_fn: t.Callable[[t.Any], int]) -> None:
        self.n_fn = n_fn


def bitfield(n: int | t.Callable[[t.Any], int]) -> t.Any:
    if isinstance(n, int):
        return Bitfield(lambda _: n)
    else:
        return Bitfield(n)


@dataclass_transform(frozen_default=True, kw_only_default=True, field_specifiers=(bitfield,))
class PackedBits:
    _pb_fields: t.List[t.Tuple[str, t.Type[t.Any], Bitfield]]

    def to_bytes(self) -> bytes:
        bitstring: t.List[bool] = []

        for name, _, bitfield in self._pb_fields:
            value = getattr(self, name)
            value_bit_len = bitfield.n_fn(self)

            if not value_bit_len > 0:
                raise ValueError(
                    f"{name} has non-positive bit length ({value_bit_len})"
                )

            if value >= 1 << value_bit_len:
                raise ValueError(
                    f"{name} is too large for {value_bit_len} bits ({value})"
                )

            for i in range(value_bit_len):
                bitstring.append(
                    value & (1 << (value_bit_len - i - 1)) != 0
                )

        if len(bitstring) % 8:
            raise ValueError("Result is not byte aligned (multiple of 8 bits)")

        result = bytearray()

        for i in range(0, len(bitstring), 8):
            value = 0
            for j in range(8):
                value |= bitstring[i + j] << (7 - j)
            result.append(value)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes):
        value_map: t.Mapping[str, t.Any] = {}
        cursor = 0

        for name, field_type, bitfield in cls._pb_fields:
            value = 0

            value_bit_len = bitfield.n_fn(AttrProxy(**value_map))

            if not value_bit_len > 0:
                raise ValueError(
                    f"{name} has non-positive bit length ({value_bit_len})"
                )

            for i in range(value_bit_len):
                curr_byte_idx = cursor // 8
                curr_bit_idx = cursor % 8

                curr_byte = data[curr_byte_idx]
                curr_bit = curr_byte >> (7 - curr_bit_idx) & 1

                value |= curr_bit << (value_bit_len - i - 1)

                cursor += 1

            value_map[name] = field_type(value)

        if cursor / 8 != len(data):
            raise ValueError("Bits left over after parsing")

        return cls(**value_map)

    def __init_subclass__(cls):
        cls._pb_fields = []

        for name, field_type in t.get_type_hints(cls).items():
            if not name.startswith("_pb_"):
                bitfield = getattr(cls, name)
                if isinstance(bitfield, Bitfield):
                    cls._pb_fields.append((name, field_type, bitfield))
                else:
                    raise TypeError(
                        f"Expected bitfield for {name}, got {bitfield}"
                    )

        def pb_repr(self: PackedBits) -> str:
            return "".join((
                self.__class__.__qualname__,
                "(",
                ', '.join(
                    f'{name}={getattr(self, name)!r}' for name, _, _ in self._pb_fields
                ),
                ")",
            ))

        def pb_init(self: PackedBits, **kwargs: t.Mapping[str, t.Any]):
            for name, _, _ in self._pb_fields:
                if name not in kwargs:
                    raise TypeError(f"Missing required field {name}")
                setattr(self, name, kwargs[name])

        cls.__repr__ = pb_repr
        cls.__init__ = pb_init


class Bar(PackedBits):
    y: int = bitfield(4)
    z: int = bitfield(4)


class Foo(PackedBits):
    a: int = bitfield(4)
    b: bool = bitfield(1)
    c: int = bitfield(lambda x: x.a)
    d: int = bitfield(16)
#    e: Bar = bitfield(8)


foo = Foo(a=3, b=False, c=3, d=1234)  # , e=Bar(y=1, z=2))

print(foo)
print(foo.to_bytes())
print(Foo.from_bytes(foo.to_bytes()))
