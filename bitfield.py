from __future__ import annotations

from typing_extensions import dataclass_transform
import typing as t
import inspect

from enum import IntEnum, IntFlag, Enum

from bits import Bits, BitStream, AttrProxy


class NotProvided:
    pass


NOT_PROVIDED = NotProvided()


_T = t.TypeVar("_T")
_P = t.TypeVar("_P")


def is_provided(x: _T | NotProvided) -> t.TypeGuard[_T]:
    return x is not NOT_PROVIDED


class ValueMapper(t.Protocol[_T, _P]):
    def forward(self, x: _T) -> _P:
        ...

    def back(self, y: _P) -> _T:
        ...


class Scale:
    def __init__(self, by: float) -> None:
        self.by = by

    def forward(self, x: int):
        return x * self.by

    def back(self, y: float):
        return round(y / self.by)


class LocChMap:
    def forward(self, x: int) -> int | t.Literal["current"]:
        return x - 1 if x > 0 else "current"

    def back(self, y: int | t.Literal["current"]):
        return 0 if y == "current" else y + 1


class BFBits:
    n: int
    default: Bits | NotProvided

    def __init__(
        self,
        n: int,
        default: Bits | NotProvided,
    ):
        self.n = n
        self.default = default

    def __repr__(self) -> str:
        return f"BFBits({self.n})"

    def length(self):
        return self.n

    def has_children_with_default(self):
        return False

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return stream.read_bits(self.n)

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        if len(value) != self.n:
            raise ValueError(f"expected {self.n} bits, got {len(value)}")
        return Bits(value)


class BFList:
    item: BFType
    n: int
    default: t.List[t.Any] | NotProvided

    def __init__(self, item: BFType, n: int, default: t.List[t.Any] | NotProvided):
        self.item = item
        self.n = n
        self.default = default

    def __repr__(self) -> str:
        return f"BFList({self.item!r}, {self.n})"

    def length(self) -> int | None:
        len = self.item.length()
        return None if len is None else self.n * len

    def has_children_with_default(self) -> bool:
        return is_provided(self.item.default) or self.item.has_children_with_default()

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return [self.item.from_bitstream(stream, proxy, context) for _ in range(self.n)]

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        if len(value) != self.n:
            raise ValueError(f"expected {self.n} items, got {len(value)}")
        return sum([self.item.to_bits(item, proxy, context) for item in value], Bits())


class BFMap:
    inner: BFType
    vm: ValueMapper[t.Any, t.Any]
    default: t.Any | NotProvided

    def __init__(self, inner: BFType, vm: ValueMapper[t.Any, _P], default: _P | NotProvided):
        self.inner = inner
        self.vm = vm
        self.default = default

    def __repr__(self) -> str:
        return f"BFMap({self.inner!r})"

    def length(self) -> int | None:
        return self.inner.length()

    def has_children_with_default(self) -> bool:
        return is_provided(self.inner.default) or self.inner.has_children_with_default()

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return self.vm.forward(self.inner.from_bitstream(stream, proxy, context))

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        return self.inner.to_bits(self.vm.back(value), proxy, context)


_Params = t.ParamSpec("_Params")


class BFDyn(t.Generic[_Params]):
    fn: t.Callable[_Params, BFTypeDisguised[t.Any]]
    default: t.Any | NotProvided

    def __init__(
        self,
        fn: t.Callable[_Params, BFTypeDisguised[_T]],
        default: _T | NotProvided,
    ):
        self.fn = fn
        self.default = default

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(<fn>)"

    def length(self):
        return None

    def has_children_with_default(self):
        return False


class BFDynSelf(BFDyn[t.Any]):
    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return undisguise(self.fn(proxy)).from_bitstream(stream, proxy, context)

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        return undisguise(self.fn(proxy)).to_bits(value, proxy, context)


class BFDynSelfCtx(BFDyn[t.Any, t.Any]):
    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return undisguise(self.fn(proxy, context)).from_bitstream(stream, proxy, context)

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        return undisguise(self.fn(proxy, context)).to_bits(value, proxy, context)


class BFDynSelfCtxN(BFDyn[t.Any, t.Any, int]):
    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return undisguise(
            self.fn(proxy, context, stream.remaining())
        ).from_bitstream(stream, proxy, context)

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        field = type(value) if isinstance(value, Bitfield) else value
        #
        # TODO support lists of these types?
        #
        if not isinstance(field, (Bitfield, str, bytes)) and field is not None:
            raise TypeError(
                f"dynamic fields that use discriminators with 'n bits remaining' "
                f"can only be used with Bitfield, str, bytes, or None values. "
                f"{field!r} is not supported"
            )
        return undisguise(field).to_bits(value, proxy, context)


class BFLit:
    field: BFType
    default: t.Any

    def __init__(self, field: BFType, default: t.Any):
        self.field = field
        self.default = default

    def __repr__(self):
        return f"BFLit({self.field!r}, default={self.default!r})"

    def length(self) -> int | None:
        return self.field.length()

    def has_children_with_default(self) -> bool:
        return is_provided(self.field.default) or self.field.has_children_with_default()

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        value = self.field.from_bitstream(stream, proxy, context)
        if value != self.default:
            raise ValueError(f"expected {self.default!r}, got {value!r}")
        return value

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        if value != self.default:
            raise ValueError(f"expected {self.default!r}, got {value!r}")
        return self.field.to_bits(value, proxy, context)


class BFBitfield:
    field: t.Type[Bitfield]
    n: int
    default: Bitfield | NotProvided

    def __init__(self, field: t.Type[Bitfield], n: int, default: Bitfield | NotProvided):
        self.field = field
        self.n = n
        self.default = default

    def __repr__(self):
        return f"BFBitfield({self.field!r})"

    def length(self):
        return self.field.length()

    def has_children_with_default(self):
        return False

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> Bitfield:
        return self.field.from_bits(stream.read_bits(self.n), context)

    def to_bits(self, value: Bitfield, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        out = value.to_bits(context)
        if len(out) != self.n:
            raise ValueError(f"expected {self.n} bits, got {len(out)}")
        return out


class BFNone:
    default: None | NotProvided

    def __init__(self, *, default: None | NotProvided) -> None:
        self.default = default

    def __repr__(self):
        return "BFNone()"

    def length(self):
        return 0

    def has_children_with_default(self):
        return False

    def from_bitstream(self, stream: BitStream, proxy: AttrProxy | Bitfield, context: t.Any) -> t.Any:
        return None

    def to_bits(self, value: t.Any, proxy: AttrProxy | Bitfield, context: t.Any) -> Bits:
        if value is not None:
            raise ValueError(f"expected None, got {value!r}")
        return Bits()


BFType = t.Union[
    BFBits,
    BFList,
    BFMap,
    BFDynSelf,
    BFDynSelfCtx,
    BFDynSelfCtxN,
    BFLit,
    BFNone,
    BFBitfield,
]

BFTypeDisguised = t.Annotated[_T, "BFTypeDisguised"]


def disguise(x: BFType) -> BFTypeDisguised[t.Any]:
    return x  # type: ignore


def undisguise(x: BFTypeDisguised[t.Any]) -> BFType:
    if isinstance(x, BFType):
        return x

    if isinstance(x, type) and issubclass(x, Bitfield):
        field_length = x.length()
        if field_length is None:
            raise TypeError("cannot infer length for dynamic Bitfield")
        return undisguise(bf_bitfield(x, field_length))

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


def bf_int_enum(enum: t.Type[_E], n: int, default: _E | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[_E]:
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
        t.Callable[[t.Any, t.Any], t.Type[_T] | BFTypeDisguised[_T]] |
        t.Callable[[t.Any, t.Any, int], t.Type[_T] | BFTypeDisguised[_T]],
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
                t.Callable[[t.Any, t.Any], t.Type[_T] | BFTypeDisguised[_T]],
                fn
            )
            return disguise(BFDynSelfCtx(fn, default))
        case 3:
            fn = t.cast(
                t.Callable[
                    [t.Any, t.Any, int], t.Type[_T] | BFTypeDisguised[_T]
                ], fn
            )
            return disguise(BFDynSelfCtxN(fn, default))
        case _:
            raise ValueError(f"unsupported number of parameters: {n_params}")


def bf_none(*, default: None | NotProvided = NOT_PROVIDED) -> BFTypeDisguised[None]:
    return disguise(BFNone(default=default))


def bf_bitfield(
    cls: t.Type[_BitfieldT],
    n: int,
    *,
    default: _BitfieldT | NotProvided = NOT_PROVIDED
):
    return disguise(BFBitfield(cls, n, default=default))


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
        bf_bytes,
        bf_str,
        bf_dyn,
    )
)
class Bitfield:
    _bf_fields: t.ClassVar[t.Dict[str, BFType]]

    def __init__(self, **kwargs: t.Any):
        for name, field in self._bf_fields.items():
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
                f'{name}={getattr(self, name)!r}' for name in self._bf_fields
            ),
            ")",
        ))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return all((
            getattr(self, name) == getattr(other, name) for name in self._bf_fields
        ))

    @classmethod
    def length(cls) -> int | None:
        acc = 0
        for field in cls._bf_fields.values():
            field_len = field.length()
            if field_len is None:
                return None
            acc += field_len
        return acc

    @classmethod
    def from_bytes(cls, data: bytes, context: t.Any = None) -> Bitfield:
        return cls.from_bits(Bits.from_bytes(data), context)

    @classmethod
    def from_bits(cls, bits: Bits, context: t.Any = None) -> Bitfield:
        stream = BitStream(bits)

        out = cls.from_bitstream(stream, context)

        if stream.remaining():
            raise ValueError(
                f"Bits left over after parsing ({stream.remaining()})"
            )

        return out

    @classmethod
    def from_bitstream(
        cls,
        stream: BitStream,
        context: t.Any = None
    ):
        proxy: AttrProxy = AttrProxy({})

        for name, field in cls._bf_fields.items():
            try:
                value = field.from_bitstream(
                    stream, proxy, context
                )
            except ValueError as e:
                raise ValueError(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )
            except EOFError as e:
                raise EOFError(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )

            proxy[name] = value

        return cls(**proxy)

    def to_bits(self, context: t.Any = None) -> Bits:
        acc: Bits = Bits()
        for name, field in self._bf_fields.items():
            value = getattr(self, name)
            try:
                acc += field.to_bits(value, self, context)
            except ValueError as e:
                raise ValueError(
                    f"error in field {name!r} of {self.__class__.__name__!r}: {e}"
                )
        return acc

    def to_bytes(self, context: t.Any = None) -> bytes:
        return self.to_bits(context).to_bytes()

    def __init_subclass__(cls):
        if not hasattr(cls, "_bf_fields"):
            cls._bf_fields = {}

        for name, type_hint in t.get_type_hints(cls).items():
            if t.get_origin(type_hint) is t.ClassVar:
                continue

            value = getattr(cls, name) if hasattr(cls, name) else NOT_PROVIDED

            try:
                bf_field = distill_field(type_hint, value)
            except TypeError as e:
                raise TypeError(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )

            if bf_field.has_children_with_default():
                raise ValueError(
                    f"field {name!r} of {cls.__name__!r} has defaults set in nested field definitions"
                )

            cls._bf_fields[name] = bf_field


def distill_field(type_hint: t.Any, value: t.Any) -> BFType:
    if value is NOT_PROVIDED:
        if isinstance(type_hint, type) and issubclass(type_hint, Bitfield):
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
