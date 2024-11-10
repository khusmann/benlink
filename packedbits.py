from __future__ import annotations
import typing as t
import types
from typing_extensions import dataclass_transform
from collections.abc import Mapping


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

    @classmethod
    def from_bytes(cls, data: bytes) -> BitStream:
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

    def n_available(self) -> int:
        return len(self._bits) - self._pos

    def _assert_advance(self, n_bits: int) -> None:
        if n_bits < 0:
            raise ValueError("Number of bits to advance must be non-negative")
        if n_bits > self.n_available():
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

    def peek_str(self, n_bytes: int):
        return self.peek_bytes(n_bytes).decode("utf-8")

    def read_str(self, n_bytes: int):
        return self.read_bytes(n_bytes).decode("utf-8")


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


@t.overload
def bitfield() -> t.Any: ...


@t.overload
def bitfield(n: int | t.Callable[[t.Any], int] | None) -> t.Any: ...


@t.overload
def bitfield(n: int | t.Callable[[t.Any], int] | None, default: _T) -> _T: ...


def bitfield(n: int | t.Callable[[t.Any], int] | None = None, default: _T | None = None) -> _T:
    if isinstance(n, int):
        if n < 0:
            raise ValueError("Bitfield length must be non-negative")
        out = FixedLengthField(n, default)
    elif n is None:
        out = FixedLengthField(None, default)
    else:
        out = VariableLengthField(n, default)

    return out  # type: ignore


_T = t.TypeVar("_T")


@t.overload
def union_bitfield(
    discriminator: t.Callable[[t.Any], t.Tuple[t.Type[_T], int]]
) -> _T: ...


@t.overload
def union_bitfield(
    discriminator: t.Callable[[t.Any], t.Tuple[t.Type[_T], int]],
    default: _T
) -> _T: ...


@t.overload
def union_bitfield(
    discriminator: t.Callable[[t.Any], t.Type[_PackedBitsT] | t.Tuple[t.Type[_PackedBitsT] | t.Type[_T], int]],
) -> _PackedBitsT | _T: ...


@t.overload
def union_bitfield(
    discriminator: t.Callable[[t.Any], t.Type[_PackedBitsT] | t.Tuple[t.Type[_PackedBitsT] | t.Type[_T], int]],
    default: _PackedBitsT | _T
) -> _PackedBitsT | _T: ...


def union_bitfield(
    discriminator: t.Callable[[t.Any], t.Type[_PackedBitsT] | t.Tuple[t.Type[_T], int]],
    default: _T | None = None
) -> _PackedBitsT | _T:
    out = UnionField(discriminator, default)
    return out  # type: ignore


class LiteralType:
    value: t.Any
    type: t.Type[t.Any]

    def __init__(self, value: t.Any):
        self.value = value
        self.type = type(value)


TypeLenFn = t.Callable[
    [t.Any],
    t.Type["PackedBits"] | t.Tuple[t.Type[t.Any] | LiteralType, int]
]


class FixedLengthField(t.NamedTuple):
    n: int | None
    default: t.Any

    def build_type_len_fn(self, field_type: t.Type[t.Any] | LiteralType) -> TypeLenFn:
        if not isinstance(field_type, LiteralType) and issubclass(field_type, PackedBits) and self.n is None:
            n = field_type._pb_n_bits  # type: ignore
            if n is None:
                raise ValueError(
                    "Variable length field requires explicit bit length"
                )

            def inner_auto(_: t.Any):
                return (field_type, n)
            return inner_auto
        else:
            n = self.n
            if n is None:
                raise ValueError(
                    "Expected a PackedBits type"
                )

            def inner(_: t.Any):
                return (field_type, n)
            return inner


class VariableLengthField(t.NamedTuple):
    n_fn: t.Callable[[t.Any], int]
    default: t.Any

    def build_type_len_fn(self, field_type: t.Type[t.Any] | LiteralType) -> TypeLenFn:
        def inner(incomplete: t.Any):
            return (field_type, self.n_fn(incomplete))
        return inner


class UnionField(t.NamedTuple):
    type_len_fn: t.Callable[
        [t.Any], t.Type[PackedBits] | t.Tuple[t.Type[t.Any], int]
    ]
    default: t.Any


Bitfield = t.Union[
    FixedLengthField,
    VariableLengthField,
    UnionField,
]


class PBField(t.NamedTuple):
    name: str
    field_type: t.Type[t.Any]
    bitfield: Bitfield
    type_len_fn: TypeLenFn


@dataclass_transform(
    frozen_default=True,
    kw_only_default=True,
    field_specifiers=(bitfield, union_bitfield),
)
class PackedBits:
    _pb_fields: t.List[PBField]
    _pb_n_bits: int | None

    def to_bits(self) -> Bits:
        bits: t.List[bool] = []

        for field in self._pb_fields:
            value = getattr(self, field.name)
            type_len_result = field.type_len_fn(self)
            if isinstance(type_len_result, tuple):
                field_type, value_bit_len = type_len_result
            else:
                field_type = type_len_result
                value_bit_len = self._pb_n_bits
                if value_bit_len is None:
                    raise ValueError(
                        "Variable length field requires explicit bit length"
                    )

            if isinstance(field_type, LiteralType):
                if field_type.value != value:
                    raise ValueError(
                        f"Field `{field.name}` has unexpected value ({value})"
                    )
            else:
                if not isinstance(value, field_type):
                    raise TypeError(
                        f"Discriminator expects field {field.name} to be of type {field_type}, instead got {value}"
                    )

            match value:
                case PackedBits():
                    new_bits = value.to_bits()
                case str():
                    new_bits = Bits.from_str(value)
                case bytes():
                    new_bits = Bits.from_bytes(value)
                case None:
                    new_bits = Bits()
                case _:
                    new_bits = Bits.from_int(value, value_bit_len)

            if len(new_bits) != value_bit_len:
                raise ValueError(
                    f"Field `{field.name}` has incorrect bit length ({len(new_bits)})"
                )

            bits += new_bits

        return Bits(bits)

    @classmethod
    def from_bits(cls, bits: Bits):
        stream = BitStream(bits)

        try:
            out = cls.from_bitstream(stream)
        except EOFError:
            raise ValueError("Not enough bits to parse object")

        if stream.n_available():
            raise ValueError("Bits left over after parsing")
        return out

    @classmethod
    def from_bitstream(cls, stream: BitStream):
        value_map: t.Mapping[str, t.Any] = {}

        for field in cls._pb_fields:
            type_len_result = field.type_len_fn(AttrProxy(value_map))
            if isinstance(type_len_result, tuple):
                field_type, value_bit_len = type_len_result
            else:
                field_type = type_len_result
                value_bit_len = field_type._pb_n_bits
                if value_bit_len is None:
                    raise ValueError(
                        "Variable length field requires explicit bit length"
                    )

            field_type_cnstr = (
                field_type.type if isinstance(field_type, LiteralType)
                else field_type
            )

            if not isinstance(field_type, LiteralType):
                if issubclass(field_type, types.NoneType):
                    if value_bit_len != 0:
                        raise ValueError(
                            f"None field `{field.name}` must have zero bit length"
                        )
                elif issubclass(field_type, str) or issubclass(field_type, bytes):
                    if value_bit_len % 8:
                        raise ValueError(
                            f"Field `{field.name}` length ({value_bit_len}) is not a multiple of 8"
                        )
                    if value_bit_len < 0:
                        raise ValueError(
                            f"Field `{field.name}` has negative bit length ({value_bit_len})"
                        )
                else:
                    if not value_bit_len > 0:
                        raise ValueError(
                            f"Field `{field.name}` has non-positive bit length ({value_bit_len})"
                        )
            if issubclass(field_type_cnstr, PackedBits):
                value = field_type_cnstr.from_bits(
                    stream.read_bits(value_bit_len)
                )
            elif issubclass(field_type_cnstr, str):
                value = field_type_cnstr(
                    stream.read_str(value_bit_len // 8)
                )
            elif issubclass(field_type_cnstr, bytes):
                value = field_type_cnstr(
                    stream.read_bytes(value_bit_len // 8)
                )
            elif issubclass(field_type_cnstr, types.NoneType):
                value = field_type_cnstr()
            else:
                value = field_type_cnstr(stream.read_int(value_bit_len))

            if isinstance(field_type, LiteralType):
                if value != field_type.value:
                    raise ValueError(
                        f"Field `{field.name}` has unexpected value ({value})"
                    )

            value_map[field.name] = value

        return cls(**value_map)

    def to_bytes(self) -> bytes:
        return self.to_bits().to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls.from_bits(Bits.from_bytes(data))

    def __repr__(self) -> str:
        return "".join((
            self.__class__.__qualname__,
            "(",
            ', '.join(
                f'{field.name}={getattr(self, field.name)!r}' for field in self._pb_fields
            ),
            ")",
        ))

    def __init__(self, **kwargs: t.Any):
        for field in self._pb_fields:
            if field.bitfield.default is None:
                if field.name not in kwargs:
                    raise TypeError(f"Missing required field {field.name}")
                setattr(self, field.name, kwargs[field.name])
            else:
                setattr(self, field.name, field.bitfield.default)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return all((
            getattr(self, field.name) == getattr(other, field.name) for field in self._pb_fields
        ))

    def __init_subclass__(cls):
        cls._pb_fields = []
        cls._pb_n_bits = 0

        for name, field_type in t.get_type_hints(cls).items():
            if not name.startswith("_pb_"):
                if name not in vars(cls):
                    raise TypeError(
                        f"Expected bitfield for field `{name}`"
                    )
                bitfield = getattr(cls, name)

                if is_literal_type(field_type):
                    if len(t.get_args(field_type)) != 1:
                        raise TypeError(
                            f"Literal field `{name}` must have exactly one argument"
                        )
                    value = t.get_args(field_type)[0]
                    field_type_constructor = LiteralType(value)
                else:
                    field_type_constructor = field_type

                match bitfield:
                    case UnionField(type_len_fn):
                        if not is_union_type(field_type):
                            raise TypeError(
                                f"Expected union type for field `{name}`, got {field_type}"
                            )
                        if any((is_literal_type(tp) for tp in t.get_args(field_type))):
                            raise TypeError(
                                f"Union field `{name}` cannot contain literal types"
                            )

                        type_len_fn = type_len_fn
                    case FixedLengthField() | VariableLengthField():
                        if is_union_type(field_type):
                            raise TypeError(
                                f"Expected union_bitfield() for union field `{name}`"
                            )

                        type_len_fn = bitfield.build_type_len_fn(
                            field_type_constructor
                        )
                    case _:
                        raise TypeError(
                            f"Expected bitfield for field `{name}`, got {bitfield}"
                        )

                if isinstance(bitfield, FixedLengthField) and field_type_constructor is types.NoneType:
                    if bitfield.n != 0:
                        raise ValueError(
                            f"None field `{name}` must have zero bit length"
                        )

                if isinstance(bitfield, FixedLengthField) and cls._pb_n_bits is not None and bitfield.n is not None:
                    cls._pb_n_bits += bitfield.n
                else:
                    cls._pb_n_bits = None

                cls._pb_fields.append(
                    PBField(
                        name,
                        field_type,
                        bitfield,
                        type_len_fn,
                    )
                )


_PackedBitsT = t.TypeVar("_PackedBitsT", bound=PackedBits)


def is_union_type(tp: t.Type[t.Any]) -> bool:
    return (
        t.get_origin(tp) is t.Union or
        t.get_origin(tp) is types.UnionType
    )


def is_literal_type(tp: t.Type[t.Any]) -> bool:
    return t.get_origin(tp) is t.Literal


def is_classvar_type(tp: t.Type[t.Any]) -> bool:
    return t.get_origin(tp) is t.ClassVar


def set_literal_classvars():
    def inner(cls: t.Type[_T]) -> t.Type[_T]:
        for name, field_type in t.get_type_hints(cls).items():
            if is_classvar_type(field_type):
                field_type_inner = t.get_args(field_type)[0]
                if is_literal_type(field_type_inner):
                    field_type_inner_args = t.get_args(field_type_inner)
                    if len(field_type_inner_args) == 1:
                        value = t.get_args(field_type_inner)[0]
                        setattr(cls, name, value)
                    else:
                        if name not in vars(cls):
                            raise TypeError(
                                f"ClassVar field `{name}` is defined with multiple literal values but has no default set"
                            )
        return cls
    return inner
