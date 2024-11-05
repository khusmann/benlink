from __future__ import annotations
import typing as t
import types
from typing_extensions import dataclass_transform
from collections.abc import Mapping


class AttrProxy(Mapping[str, t.Any]):
    _data: t.Mapping[str, t.Any]

    def __init__(self, data: t.Mapping[str, t.Any]) -> None:
        self._data = data

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


def bitfield(n: int | t.Callable[[t.Any], int]) -> t.Any:
    if isinstance(n, int):
        return FixedLengthField(n)
    else:
        return VariableLengthField(n)


_T = t.TypeVar("_T")


def union_bitfield(discriminator: t.Callable[[t.Any], t.Tuple[t.Type[_T], int]]) -> _T:
    return UnionField(discriminator)  # type: ignore


TypeLenFn = t.Callable[[t.Any], t.Tuple[t.Type[t.Any], int]]


class FixedLengthField(t.NamedTuple):
    n: int

    def get_type_len_fn(self, field_type: t.Type[t.Any]) -> TypeLenFn:
        def inner(_: t.Any) -> t.Tuple[t.Type[t.Any], int]:
            return (field_type, self.n)
        return inner


class VariableLengthField(t.NamedTuple):
    n_fn: t.Callable[[t.Any], int]

    def get_type_len_fn(self, field_type: t.Type[t.Any]) -> TypeLenFn:
        def inner(incomplete: t.Any) -> t.Tuple[t.Type[t.Any], int]:
            return (field_type, self.n_fn(incomplete))
        return inner


class UnionField(t.NamedTuple):
    type_fn: t.Callable[[t.Any], t.Tuple[t.Type[t.Any], int]]

    def get_type_len_fn(self, _: t.Type[t.Any]) -> TypeLenFn:
        return self.type_fn


Bitfield = t.Union[
    FixedLengthField,
    VariableLengthField,
    UnionField,
]


@dataclass_transform(
    frozen_default=True,
    kw_only_default=True,
    field_specifiers=(bitfield, union_bitfield),
)
class PackedBits:
    _pb_fields: t.List[t.Tuple[str, TypeLenFn]]

    def to_bitarray(self) -> t.List[bool]:
        bitstring: t.List[bool] = []

        for name, type_len_fn in self._pb_fields:
            value = getattr(self, name)
            field_type, value_bit_len = type_len_fn(self)

            if not isinstance(value, field_type):
                raise TypeError(
                    f"Discriminator expects field {name} to be of type {field_type}, instead got {value}"
                )

            match value:
                case PackedBits():
                    new_bits = value.to_bitarray()
                    if len(new_bits) != value_bit_len:
                        raise ValueError(
                            f"Field {name} has incorrect bit length ({len(new_bits)})"
                        )
                    bitstring += new_bits
                case str():
                    raise NotImplementedError
                case bytes():
                    raise NotImplementedError
                case _:
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

        return bitstring

    @classmethod
    def from_bitarray(cls, bitarray: t.Sequence[bool]):
        value_map: t.Mapping[str, t.Any] = {}

        cursor = 0

        for name, type_len_fn in cls._pb_fields:
            field_type, value_bit_len = type_len_fn(AttrProxy(value_map))
            if not value_bit_len > 0:
                raise ValueError(
                    f"{name} has non-positive bit length ({value_bit_len})"
                )

            match field_type:
                case field_type if issubclass(field_type, PackedBits):
                    value_map[name] = field_type.from_bitarray(
                        bitarray[cursor:cursor+value_bit_len]
                    )
                    cursor += value_bit_len
                case field_type if field_type is str:
                    raise NotImplementedError
                case field_type if field_type is bytes:
                    raise NotImplementedError
                case _:
                    value = 0
                    for i in range(value_bit_len):
                        value |= bitarray[cursor] << (value_bit_len - i - 1)
                        cursor += 1

                    value_map[name] = field_type(value)

        if cursor != len(bitarray):
            raise ValueError("Bits left over after parsing")

        return cls(**value_map)

    def to_bytes(self) -> bytes:
        bits = self.to_bitarray()

        if len(bits) % 8:
            raise ValueError("Result is not byte aligned (multiple of 8 bits)")

        result = bytearray()

        for i in range(0, len(bits), 8):
            value = 0
            for j in range(8):
                value |= bits[i + j] << (7 - j)
            result.append(value)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes):
        bits: t.List[bool] = []

        for byte in data:
            for i in range(8):
                bits.append(byte & (1 << (7 - i)) != 0)

        return cls.from_bitarray(bits)

    def __repr__(self) -> str:
        return "".join((
            self.__class__.__qualname__,
            "(",
            ', '.join(
                f'{name}={getattr(self, name)!r}' for name, _ in self._pb_fields
            ),
            ")",
        ))

    def __init__(self, **kwargs: t.Any):
        for name, _, in self._pb_fields:
            if name not in kwargs:
                raise TypeError(f"Missing required field {name}")
            setattr(self, name, kwargs[name])

    def __init_subclass__(cls):
        cls._pb_fields = []

        for name, field_type in t.get_type_hints(cls).items():
            if not name.startswith("_pb_"):
                bitfield = getattr(cls, name)

                if not isinstance(bitfield, Bitfield):
                    raise TypeError(
                        f"Expected bitfield for {name}, got {bitfield}"
                    )

                is_union_field_type = (
                    t.get_origin(field_type) is t.Union or
                    t.get_origin(field_type) is types.UnionType
                )

                if is_union_field_type and not isinstance(bitfield, UnionField):
                    raise TypeError(
                        f"Expected union_bitfield() for union field {name}"
                    )

                cls._pb_fields.append(
                    (name, bitfield.get_type_len_fn(field_type))
                )


class Bar(PackedBits):
    y: int = bitfield(4)
    z: int = bitfield(4)


def foo_discriminator(foo: Foo):
    if foo.b:
        return (bool, 8)
    else:
        return (int, 16)


class Foo(PackedBits):
    a: int = bitfield(4)
    b: bool = bitfield(1)
    c: int = bitfield(lambda x: x.a)
    d: int | bool = union_bitfield(foo_discriminator)
    e: Bar = bitfield(8)


foo = Foo(a=3, b=False, c=3, d=1234, e=Bar(y=10, z=2))

print(foo)
print(foo.to_bytes())
print(Foo.from_bytes(foo.to_bytes()))

bar = Foo(a=3, b=True, c=3, d=False, e=Bar(y=10, z=2))

print(bar)
print(bar.to_bytes())
print(Foo.from_bytes(bar.to_bytes()))
