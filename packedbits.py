import typing as t
from typing_extensions import dataclass_transform


class Bitfield:
    n: int

    def __init__(self, n: int) -> None:
        self.n = n


def bitfield(n: int) -> t.Any:
    return Bitfield(n)


@dataclass_transform(frozen_default=True, kw_only_default=True, field_specifiers=(bitfield,))
class PackedBits:
    _pb_fields: t.List[t.Tuple[str, t.Type[t.Any], Bitfield]] = []

    def to_bytes(self) -> bytes:
        bitstring: t.List[bool] = []

        for name, _, bitfield in self._pb_fields:
            value = getattr(self, name)

            if value >= 1 << bitfield.n:
                raise ValueError(
                    f"{name}({value}) is too large for {bitfield.n} bits"
                )

            for i in range(bitfield.n):
                bitstring.append(value & (1 << (bitfield.n - i - 1)) != 0)

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

            for i in range(bitfield.n):
                curr_byte_idx = cursor // 8
                curr_bit_idx = cursor % 8

                curr_byte = data[curr_byte_idx]
                curr_bit = curr_byte >> (7 - curr_bit_idx) & 1

                value |= curr_bit << (bitfield.n - i - 1)

                cursor += 1

            value_map[name] = field_type(value)

        if cursor / 8 != len(data):
            raise ValueError("Bits left over after parsing")

        return cls(**value_map)

    def __init_subclass__(cls):
        for name, field_type in t.get_type_hints(cls).items():
            if not name.startswith("_pb_"):
                bitfield = getattr(cls, name)
                if isinstance(bitfield, Bitfield):
                    cls._pb_fields.append((name, field_type, bitfield))
                else:
                    print(cls.__annotations__)
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


class Foo(PackedBits):
    a: int = bitfield(4)
    b: bool = bitfield(1)
    c: int = bitfield(3)
    d: int = bitfield(16)


foo = Foo(a=1, b=False, c=3, d=1234566)

print(foo)
print(foo.to_bytes())
print(Foo.from_bytes(foo.to_bytes()))
