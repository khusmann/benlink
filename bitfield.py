from __future__ import annotations

from typing_extensions import dataclass_transform, TypeVar as TypeVarDefault
import typing as t
import inspect

from enum import IntEnum, IntFlag, Enum

from bits import Bits, BitStream, AttrProxy


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


def bftype_from_bitstream(bftype: BFType, stream: BitStream, proxy: AttrProxy, context: t.Any) -> t.Tuple[t.Any, BitStream]:
    match bftype:
        case BFBits(n=n):
            return stream.take(n)

        case BFList(inner=inner, n=n):
            acc: t.List[t.Any] = []
            for _ in range(n):
                item, stream = bftype_from_bitstream(
                    inner, stream, proxy, context
                )
                acc.append(item)
            return acc, stream

        case BFMap(inner=inner, vm=vm):
            value, stream = bftype_from_bitstream(
                inner, stream, proxy, context
            )
            return vm.forward(value), stream

        case BFDynSelf(fn=fn):
            return bftype_from_bitstream(undisguise(fn(proxy)), stream, proxy, context)

        case BFDynSelfN(fn=fn):
            return bftype_from_bitstream(undisguise(fn(proxy, stream.remaining())), stream, proxy, context)

        case BFLit(inner=inner, default=default):
            value, stream = bftype_from_bitstream(
                inner, stream, proxy, context
            )
            if value != default:
                raise ValueError(f"expected {default!r}, got {value!r}")
            return value, stream

        case BFNone():
            return None, stream

        case BFBitfield(inner=inner, n=n):
            bits, stream = stream.take(n)
            return inner.from_bits(bits, context), stream


def is_bitfield(x: t.Any) -> t.TypeGuard[Bitfield[t.Any]]:
    return isinstance(x, Bitfield)


def is_bitfield_class(x: t.Type[t.Any]) -> t.TypeGuard[t.Type[Bitfield[t.Any]]]:
    return issubclass(x, Bitfield)


def bftype_to_bits(bftype: BFType, value: t.Any, parent: Bitfield[t.Any], context: t.Any) -> Bits:
    match bftype:
        case BFBits(n=n):
            if len(value) != n:
                raise ValueError(f"expected {n} bits, got {len(value)}")
            return Bits(value)

        case BFList(inner=inner, n=n):
            if len(value) != n:
                raise ValueError(f"expected {n} items, got {len(value)}")
            return sum([bftype_to_bits(inner, item, parent, context) for item in value], Bits())

        case BFMap(inner=inner, vm=vm):
            return bftype_to_bits(inner, vm.back(value), parent, context)

        case BFDynSelf(fn=fn):
            return bftype_to_bits(undisguise(fn(parent)), value, parent, context)

        case BFDynSelfN(fn=fn):
            if is_bitfield(value):
                field = type(value)
            elif isinstance(value, (str, bytes)) or value is None:
                field = value
            else:
                raise TypeError(
                    f"dynamic fields that use discriminators with 'n bits remaining' "
                    f"can only be used with Bitfield, str, bytes, or None values. "
                    f"{value!r} is not supported"
                )
            return bftype_to_bits(undisguise(field), value, parent, context)

        case BFLit(inner=inner, default=default):
            if value != default:
                raise ValueError(f"expected {default!r}, got {value!r}")
            return bftype_to_bits(inner, value, parent, context)

        case BFNone():
            if value is not None:
                raise ValueError(f"expected None, got {value!r}")
            return Bits()

        case BFBitfield(inner=inner, n=n):
            if not is_bitfield(value):
                raise TypeError(
                    f"expected Bitfield, got {type(value).__name__}"
                )
            out = value.to_bits(context)
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

    if isinstance(x, str):
        return undisguise(bf_lit(bf_str(len(x.encode("utf-8"))), default=x))

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
        if byte_len != n:
            raise ValueError(
                f"expected default string of length {n} bytes, got {byte_len} bytes ({default!r})"
            )

    class BytesAsStr:
        def forward(self, x: bytes) -> str:
            return x.decode(encoding)

        def back(self, y: str) -> bytes:
            return y.encode(encoding)

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
    *,
    default: _BitfieldT | NotProvided = NOT_PROVIDED
) -> BFTypeDisguised[_BitfieldT]:
    return disguise(BFBitfield(cls, n, default=default))


_ContextT = TypeVarDefault("_ContextT", default=None)


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
class Bitfield(t.Generic[_ContextT]):
    _fields: t.ClassVar[t.Dict[str, BFType]]
    _reorder: t.ClassVar[t.Sequence[int]] = []
    bitfield_context: _ContextT | None = None

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
    def from_bytes(cls, data: bytes, context: _ContextT | None = None):
        return cls.from_bits(Bits.from_bytes(data), context)

    @classmethod
    def from_bits(cls, bits: Bits, context: _ContextT | None = None):
        stream = BitStream(bits)

        out, stream = cls.from_bitstream(stream, context)

        if stream.remaining():
            raise ValueError(
                f"Bits left over after parsing {cls.__name__} ({stream.remaining()})"
            )

        return out

    @classmethod
    def from_bitstream(
        cls,
        stream: BitStream,
        context: _ContextT | None = None
    ):
        proxy: AttrProxy = AttrProxy({})
        proxy["bitfield_context"] = context

        stream = stream.reorder(cls._reorder)

        for name, field in cls._fields.items():
            try:
                value, stream = bftype_from_bitstream(
                    field, stream, proxy, context
                )
            except Exception as e:
                raise type(e)(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )

            proxy[name] = value

        return cls(**proxy), stream

    def to_bits(self, context: _ContextT | None = None) -> Bits:
        setattr(self, "bitfield_context", context)
        acc: Bits = Bits()

        for name, field in self._fields.items():
            value = getattr(self, name)
            try:
                acc += bftype_to_bits(field, value, self, context)
            except Exception as e:
                raise type(e)(
                    f"error in field {name!r} of {self.__class__.__name__!r}: {e}"
                )

        return acc.unreorder(self._reorder)

    def to_bytes(self, context: t.Any = None) -> bytes:
        return self.to_bits(context).to_bytes()

    def __init_subclass__(cls):
        if not hasattr(cls, "_bf_fields"):
            cls._fields = {}
        else:
            cls._fields = cls._fields.copy()

        for name, type_hint in t.get_type_hints(cls).items():
            if t.get_origin(type_hint) is t.ClassVar or name == "bitfield_context":
                continue

            value = getattr(cls, name) if hasattr(cls, name) else NOT_PROVIDED

            try:
                bf_field = distill_field(type_hint, value)

                if bftype_has_children_with_default(bf_field):
                    raise ValueError(
                        f"inner field definitions cannot have defaults set (except literal fields)"
                    )
            except Exception as e:
                raise type(e)(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )

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
