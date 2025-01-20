from __future__ import annotations

from typing_extensions import dataclass_transform, TypeVar as TypeVarDefault, Self
import typing as t
import inspect

from enum import IntEnum, IntFlag, Enum


def reorder_pairs(order: t.Sequence[int], size: int):
    if not all(i < size for i in order) or not all(i >= 0 for i in order):
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
    def __new__(cls, bits: t.Iterable[bool] | str = ()) -> Bits:
        if isinstance(bits, str):
            bits = (bit == "1" for bit in bits if bit in ("0", "1"))
        return super().__new__(cls, tuple(bits))

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
        return f"{self.__class__.__name__}({str_bits!r})"

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
    def from_str(cls, data: str, encoding: str = "utf-8") -> Bits:
        return cls.from_bytes(data.encode(encoding))

    @classmethod
    def from_bytes(cls, data: t.ByteString) -> Bits:
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

    def to_str(self, encoding: str = "utf-8") -> str:
        return self.to_bytes().decode(encoding)


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

        return Bits(self._bits[self._pos:n+self._pos]), BitStream(self._bits, self._pos+n)

    def take_bytes(self, n: int):
        value, stream = self.take(n*8)
        return value.to_bytes(), stream

    def peek(self, n: int = 1):
        if n > self.remaining():
            raise EOFError

        return self._bits[self._pos:n+self._pos]

    def peek_bytes(self, n: int):
        return self.peek(n*8).to_bytes()

    def __repr__(self) -> str:
        str_bits = "".join(str(int(bit)) for bit in self._bits[self._pos:])
        return f"{self.__class__.__name__}({str_bits})"

    def extend(self, other: Bits):
        return BitStream(
            self._bits[self._pos:] + other,
        )

    def extend_bytes(self, data: bytes):
        return self.extend(Bits.from_bytes(data))

    def reorder(self, order: t.Sequence[int]):
        if not order:
            return self

        rebased = self._bits[self._pos:]
        return BitStream(rebased.reorder(order))


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


class NotProvided:
    def __repr__(self): return "<NotProvided>"


NOT_PROVIDED = NotProvided()


_T = t.TypeVar("_T")
_P = t.TypeVar("_P")


def is_provided(x: _T | NotProvided) -> t.TypeGuard[_T]:
    return x is not NOT_PROVIDED


class ValueMapper(t.Protocol[_T, _P]):
    def forward(self, x: _T) -> _P: ...
    def back(self, y: _P) -> _T: ...


class Scale(t.NamedTuple):
    by: float
    n_digits: int | None = None

    def forward(self, x: int):
        value = x * self.by
        return value if self.n_digits is None else round(value, self.n_digits)

    def back(self, y: float):
        return round(y / self.by)


class IntScale(t.NamedTuple):
    by: int

    def forward(self, x: int):
        return x * self.by

    def back(self, y: int):
        return round(y / self.by)


class BFBits(t.NamedTuple):
    n: int
    default: Bits | NotProvided


class BFList(t.NamedTuple):
    inner: BFType
    n: int
    default: t.List[t.Any] | NotProvided


class BFMap(t.NamedTuple):
    inner: BFType
    vm: ValueMapper[t.Any, t.Any]
    default: t.Any | NotProvided


class BFDynSelf(t.NamedTuple):
    fn: t.Callable[[t.Any], BFTypeDisguised[t.Any]]
    default: t.Any | NotProvided


class BFDynSelfN(t.NamedTuple):
    fn: t.Callable[[t.Any, int], BFTypeDisguised[t.Any]]
    default: t.Any | NotProvided


class BFLit(t.NamedTuple):
    inner: BFType
    default: t.Any


class BFBitfield(t.NamedTuple):
    inner: t.Type[Bitfield]
    n: int
    default: Bitfield | NotProvided


class BFNone(t.NamedTuple):
    default: None | NotProvided


BFType = t.Union[
    BFBits,
    BFList,
    BFMap,
    BFDynSelf,
    BFDynSelfN,
    BFLit,
    BFNone,
    BFBitfield,
]


def bftype_length(bftype: BFType) -> int | None:
    match bftype:
        case BFBits(n=n) | BFBitfield(n=n):
            return n

        case BFList(inner=inner, n=n):
            item_len = bftype_length(inner)
            return None if item_len is None else n * item_len

        case BFMap(inner=inner) | BFLit(inner=inner):
            return bftype_length(inner)

        case BFNone():
            return 0

        case BFDynSelf() | BFDynSelfN():
            return None


def bftype_has_children_with_default(bftype: BFType) -> bool:
    match bftype:
        case BFBits() | BFBitfield() | BFNone() | BFDynSelf() | BFDynSelfN():
            return False

        case BFList(inner=inner) | BFMap(inner=inner) | BFLit(inner=inner):
            return is_provided(inner.default) or bftype_has_children_with_default(inner)


def bftype_from_bitstream(bftype: BFType, stream: BitStream, proxy: AttrProxy, opts: t.Any) -> t.Tuple[t.Any, BitStream]:
    match bftype:
        case BFBits(n=n):
            return stream.take(n)

        case BFList(inner=inner, n=n):
            acc: t.List[t.Any] = []
            for _ in range(n):
                item, stream = bftype_from_bitstream(
                    inner, stream, proxy, opts
                )
                acc.append(item)
            return acc, stream

        case BFMap(inner=inner, vm=vm):
            value, stream = bftype_from_bitstream(
                inner, stream, proxy, opts
            )
            return vm.forward(value), stream

        case BFDynSelf(fn=fn):
            return bftype_from_bitstream(undisguise(fn(proxy)), stream, proxy, opts)

        case BFDynSelfN(fn=fn):
            return bftype_from_bitstream(undisguise(fn(proxy, stream.remaining())), stream, proxy, opts)

        case BFLit(inner=inner, default=default):
            value, stream = bftype_from_bitstream(
                inner, stream, proxy, opts
            )
            if value != default:
                raise ValueError(f"expected {default!r}, got {value!r}")
            return value, stream

        case BFNone():
            return None, stream

        case BFBitfield(inner=inner, n=n):
            bits, stream = stream.take(n)
            return inner.from_bits(bits, opts), stream


def is_bitfield(x: t.Any) -> t.TypeGuard[Bitfield[t.Any]]:
    return isinstance(x, Bitfield)


def is_bitfield_class(x: t.Type[t.Any]) -> t.TypeGuard[t.Type[Bitfield[t.Any]]]:
    return issubclass(x, Bitfield)


def bftype_to_bits(bftype: BFType, value: t.Any, proxy: AttrProxy, opts: t.Any) -> Bits:
    match bftype:
        case BFBits(n=n):
            if len(value) != n:
                raise ValueError(f"expected {n} bits, got {len(value)}")
            return Bits(value)

        case BFList(inner=inner, n=n):
            if len(value) != n:
                raise ValueError(f"expected {n} items, got {len(value)}")
            return sum([bftype_to_bits(inner, item, proxy, opts) for item in value], Bits())

        case BFMap(inner=inner, vm=vm):
            return bftype_to_bits(inner, vm.back(value), proxy, opts)

        case BFDynSelf(fn=fn):
            return bftype_to_bits(undisguise(fn(proxy)), value, proxy, opts)

        case BFDynSelfN(fn=fn):
            if is_bitfield(value):
                return value.to_bits(opts)

            if isinstance(value, (bool, bytes)) or value is None:
                return bftype_to_bits(undisguise(value), value, proxy, opts)

            raise TypeError(
                f"dynamic fields that use discriminators with 'n bits remaining' "
                f"can only be used with Bitfield, bool, bytes, or None values. "
                f"{value!r} is not supported"
            )

        case BFLit(inner=inner, default=default):
            if value != default:
                raise ValueError(f"expected {default!r}, got {value!r}")
            return bftype_to_bits(inner, value, proxy, opts)

        case BFNone():
            if value is not None:
                raise ValueError(f"expected None, got {value!r}")
            return Bits()

        case BFBitfield(inner=inner, n=n):
            if not is_bitfield(value):
                raise TypeError(
                    f"expected Bitfield, got {type(value).__name__}"
                )
            out = value.to_bits(opts)
            if len(out) != n:
                raise ValueError(f"expected {n} bits, got {len(out)}")
            return out


BFTypeDisguised = t.Annotated[_T, "BFTypeDisguised"]


def disguise(x: BFType) -> BFTypeDisguised[t.Any]:
    return x  # type: ignore


def undisguise(x: BFTypeDisguised[t.Any]) -> BFType:
    if isinstance(x, BFType):
        return x

    if isinstance(x, type):
        if is_bitfield_class(x):
            field_length = x.length()
            if field_length is None:
                raise TypeError("cannot infer length for dynamic Bitfield")
            return undisguise(bf_bitfield(x, field_length))

        if issubclass(x, bool):
            return undisguise(bf_bool())

    if isinstance(x, bytes):
        return undisguise(bf_lit(bf_bytes(len(x)), default=x))

    if x is None:
        return undisguise(bf_none())

    raise TypeError(f"expected a field type, got {x!r}")


def bf_bits(n: int, *, default: Bits | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[Bits]:
    return disguise(BFBits(n, default))


def bf_map(
    field: BFTypeDisguised[_T],
    vm: ValueMapper[_T, _P], *,
    default: _P | NotProvided = NOT_PROVIDED
) -> BFTypeDisguised[_P]:
    return disguise(BFMap(undisguise(field), vm, default))


@t.overload
def bf_int(n: int, *, default: int) -> BFTypeDisguised[int]: ...


@t.overload
def bf_int(n: int) -> BFTypeDisguised[int]: ...


def bf_int(n: int, *, default: int | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[int]:
    class BitsAsInt:
        def forward(self, x: Bits) -> int:
            return x.to_int()

        def back(self, y: int) -> Bits:
            return Bits.from_int(y, n)

    return bf_map(bf_bits(n), BitsAsInt(), default=default)


def bf_bool(*, default: bool | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[bool]:
    class IntAsBool:
        def forward(self, x: int) -> bool:
            return x == 1

        def back(self, y: bool) -> int:
            return 1 if y else 0

    return bf_map(bf_int(1), IntAsBool(), default=default)


_E = t.TypeVar("_E", bound=IntEnum | IntFlag)


def bf_int_enum(enum: t.Type[_E], n: int, *, default: _E | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[_E]:
    class IntAsEnum:
        def forward(self, x: int) -> _E:
            return enum(x)

        def back(self, y: _E) -> int:
            return y.value

    return bf_map(bf_int(n), IntAsEnum(), default=default)


def bf_list(
    item: t.Type[_T] | BFTypeDisguised[_T],
    n: int, *,
    default: t.List[_T] | NotProvided = NOT_PROVIDED
) -> BFTypeDisguised[t.List[_T]]:

    if is_provided(default) and len(default) != n:
        raise ValueError(
            f"expected default list of length {n}, got {len(default)} ({default!r})"
        )
    return disguise(BFList(undisguise(item), n, default))


_LiteralT = t.TypeVar("_LiteralT", bound=str | int | float | bytes | Enum)


def bf_lit(field: BFTypeDisguised[_LiteralT], *, default: _P) -> BFTypeDisguised[_P]:
    return disguise(BFLit(undisguise(field), default))


def bf_lit_int(n: int, *, default: _LiteralT) -> BFTypeDisguised[_LiteralT]:
    return bf_lit(bf_int(n), default=default)


def bf_bytes(n: int, *, default: bytes | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[bytes]:
    if is_provided(default) and len(default) != n:
        raise ValueError(
            f"expected default bytes of length {n} bytes, got {len(default)} bytes ({default!r})"
        )

    class ListAsBytes:
        def forward(self, x: t.List[int]) -> bytes:
            return bytes(x)

        def back(self, y: bytes) -> t.List[int]:
            return list(y)

    return bf_map(bf_list(bf_int(8), n), ListAsBytes(), default=default)


def bf_str(n: int, encoding: str = "utf-8", *, default: str | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[str]:
    if is_provided(default):
        byte_len = len(default.encode(encoding))
        if byte_len > n:
            raise ValueError(
                f"expected default string of maximum length {n} bytes, got {byte_len} bytes ({default!r})"
            )

    class BytesAsStr:
        def forward(self, x: bytes) -> str:
            return x.decode(encoding).rstrip("\0")

        def back(self, y: str) -> bytes:
            return y.ljust(n, "\0").encode(encoding)

    return bf_map(bf_bytes(n), BytesAsStr(), default=default)


def bf_dyn(
    fn: t.Callable[[t.Any], t.Type[_T] | BFTypeDisguised[_T]] |
        t.Callable[[t.Any, int], t.Type[_T] | BFTypeDisguised[_T]],
    default: _T | NotProvided = NOT_PROVIDED
) -> BFTypeDisguised[_T]:
    n_params = len(inspect.signature(fn).parameters)
    match n_params:
        case 1:
            fn = t.cast(
                t.Callable[[t.Any], t.Type[_T] | BFTypeDisguised[_T]],
                fn
            )
            return disguise(BFDynSelf(fn, default))
        case 2:
            fn = t.cast(
                t.Callable[
                    [t.Any, int], t.Type[_T] | BFTypeDisguised[_T]
                ], fn
            )
            return disguise(BFDynSelfN(fn, default))
        case _:
            raise ValueError(f"unsupported number of parameters: {n_params}")


def bf_none(*, default: None | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[None]:
    return disguise(BFNone(default=default))


def bf_bitfield(
    cls: t.Type[_BitfieldT],
    n: int,
    default: _BitfieldT | NotProvided = NOT_PROVIDED
) -> BFTypeDisguised[_BitfieldT]:
    return disguise(BFBitfield(cls, n, default=default))


_DynOptsT = TypeVarDefault("_DynOptsT", default=None)


@dataclass_transform(
    kw_only_default=True,
    field_specifiers=(
        bf_bits,
        bf_map,
        bf_int,
        bf_bool,
        bf_int_enum,
        bf_bitfield,
        bf_list,
        bf_lit,
        bf_lit_int,
        bf_bytes,
        bf_str,
        bf_dyn,
    )
)
class Bitfield(t.Generic[_DynOptsT]):
    _fields: t.ClassVar[t.Dict[str, BFType]] = {}
    _reorder: t.ClassVar[t.Sequence[int]] = []
    _DYN_OPTS_STR: t.ClassVar[str] = "dyn_opts"
    dyn_opts: _DynOptsT | None = None

    def __init__(self, **kwargs: t.Any):
        for name, field in self._fields.items():
            value = kwargs.get(name, NOT_PROVIDED)

            if not is_provided(value):
                if is_provided(field.default):
                    value = field.default
                else:
                    raise ValueError(f"missing value for field {name!r}")

            setattr(self, name, value)

    def __repr__(self) -> str:
        return "".join((
            self.__class__.__name__,
            "(",
            ', '.join(
                f'{name}={getattr(self, name)!r}' for name in self._fields
            ),
            ")",
        ))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return all((
            getattr(self, name) == getattr(other, name) for name in self._fields
        ))

    @classmethod
    def length(cls) -> int | None:
        acc = 0
        for field in cls._fields.values():
            field_len = bftype_length(field)
            if field_len is None:
                return None
            acc += field_len
        return acc

    @classmethod
    def from_bytes(cls, data: t.ByteString, opts: _DynOptsT | None = None):
        return cls.from_bits(Bits.from_bytes(data), opts)

    @classmethod
    def from_bits(cls, bits: Bits, opts: _DynOptsT | None = None):
        stream = BitStream(bits)

        out, stream = cls.from_bitstream(stream, opts)

        if stream.remaining():
            raise ValueError(
                f"Bits left over after parsing {cls.__name__} ({stream.remaining()})"
            )

        return out

    @classmethod
    def from_bitstream(
        cls,
        stream: BitStream,
        opts: _DynOptsT | None = None
    ):
        proxy: AttrProxy = AttrProxy({cls._DYN_OPTS_STR: opts})

        stream = stream.reorder(cls._reorder)

        for name, field in cls._fields.items():
            try:
                value, stream = bftype_from_bitstream(
                    field, stream, proxy, opts
                )
            except Exception as e:
                # TODO assemble a nicer error message for deeply nested fields
                raise type(e)(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                ) from e

            proxy[name] = value

        return cls(**proxy), stream

    @classmethod
    def from_bitstream_batch(
        cls,
        stream: BitStream,
        opts: _DynOptsT | None = None,
        consume_errors: bool = False
    ) -> t.Tuple[t.List[Self], BitStream]:
        out: t.List[Self] = []

        while stream.remaining():
            try:
                item, stream = cls.from_bitstream(stream, opts)
                out.append(item)
            except EOFError:
                break
            except Exception:
                if consume_errors:
                    _, stream = stream.take_bytes(1)
                else:
                    raise

        return out, stream

    def to_bits(self, opts: _DynOptsT | None = None) -> Bits:
        proxy = AttrProxy({**self.__dict__, self._DYN_OPTS_STR: opts})

        acc: Bits = Bits()

        for name, field in self._fields.items():
            value = getattr(self, name)
            try:
                acc += bftype_to_bits(field, value, proxy, opts)
            except Exception as e:
                # TODO assemble a nicer error message for deeply nested fields
                raise type(e)(
                    f"error in field {name!r} of {self.__class__.__name__!r}: {e}"
                ) from e

        return acc.unreorder(self._reorder)

    def to_bytes(self, opts: _DynOptsT | None = None) -> bytes:
        return self.to_bits(opts).to_bytes()

    def __init_subclass__(cls):
        cls._fields = cls._fields.copy()

        for name, type_hint in t.get_type_hints(cls).items():
            if t.get_origin(type_hint) is t.ClassVar or name == cls._DYN_OPTS_STR:
                continue

            value = getattr(cls, name) if hasattr(cls, name) else NOT_PROVIDED

            try:
                bf_field = distill_field(type_hint, value)

                if bftype_has_children_with_default(bf_field):
                    raise ValueError(
                        f"inner field definitions cannot have defaults set (except literal fields)"
                    )
            except Exception as e:
                # TODO assemble a nicer error message for deeply nested fields
                raise type(e)(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                ) from e

            cls._fields[name] = bf_field


def distill_field(type_hint: t.Any, value: t.Any) -> BFType:
    if value is NOT_PROVIDED:
        if isinstance(type_hint, type) and issubclass(type_hint, (Bitfield, bool)):
            return undisguise(type_hint)

        if t.get_origin(type_hint) is t.Literal:
            args = t.get_args(type_hint)

            if len(args) != 1:
                raise TypeError(
                    f"literal must have exactly one argument"
                )

            return undisguise(args[0])

        raise TypeError(f"missing field definition")

    return undisguise(value)


_BitfieldT = t.TypeVar("_BitfieldT", bound=Bitfield)
