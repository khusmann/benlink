from __future__ import annotations

from typing_extensions import dataclass_transform
import typing as t

from enum import IntEnum, IntFlag, Enum

from bits import Bits


class BarEnum(IntEnum):
    A = 1
    B = 2
    C = 3


_T = t.TypeVar("_T")
_P = t.TypeVar("_P")


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
    default: Bits | None

    def __init__(
        self,
        n: int,
        default: Bits | None,
    ):
        self.n = n
        self.default = default

    def __repr__(self) -> str:
        return f"BFBits({self.n})"

    def length(self):
        return self.n


class BFList:
    item: BFType
    n: int
    default: t.List[t.Any] | None

    def __init__(self, item: BFType, n: int, default: t.List[t.Any] | None):
        self.item = item
        self.n = n
        self.default = default

    def __repr__(self) -> str:
        return f"BFList({self.item!r}, {self.n})"

    def length(self) -> int | None:
        len = self.item.length()
        return None if len is None else self.n * len


class BFMap:
    inner: BFType
    vm: ValueMapper[t.Any, t.Any]
    default: t.Any | None

    def __init__(self, inner: BFType, vm: ValueMapper[t.Any, _P], default: _P | None):
        self.inner = inner
        self.vm = vm
        self.default = default

    def __repr__(self) -> str:
        return f"BFMap({self.inner!r})"

    def length(self) -> int | None:
        return self.inner.length()


class BFDyn:
    fn: t.Callable[[t.Any, int], BFTypeDisguised[t.Any]]
    default: t.Any | None

    def __init__(
        self,
        fn: t.Callable[[t.Any, int], BFTypeDisguised[_T]],
        default: _T | None,
    ):
        self.fn = fn
        self.default = default

    def __repr__(self) -> str:
        return f"BFDyn(<fn>)"

    def length(self):
        return None


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


class BFNone:
    def __repr__(self):
        return "BFNone()"

    def length(self):
        return 0


BFType = t.Union[BFBits, BFList, BFMap, BFDyn, BFLit, BFNone]

BFTypeDisguised = t.Annotated[_T, "BFTypeDisguised"]


def disguise(x: BFType) -> BFTypeDisguised[t.Any]:
    return x  # type: ignore


def undisguise(x: BFTypeDisguised[t.Any]) -> BFType:
    if isinstance(x, BFType):
        return x

    if isinstance(x, type) and issubclass(x, Bitfield):
        field_length = x.length()
        if field_length is None:
            raise ValueError("cannot infer length for dynamic Bitfield")
        return undisguise(bf_bitfield(x, field_length))

    if isinstance(x, bytes):
        return undisguise(bf_lit(bf_bytes(len(x)), default=x))

    if isinstance(x, str):
        return undisguise(bf_lit(bf_str(len(x.encode("utf-8"))), default=x))

    if x is None:
        return undisguise(bf_none())

    raise TypeError(f"expected a bitfield type, got {x!r}")


def bf_bits(n: int, *, default: Bits | None = None) -> BFTypeDisguised[Bits]:
    return disguise(BFBits(n, default))


def bf_map(field: BFTypeDisguised[_T], vm: ValueMapper[_T, _P], *, default: _P | None = None) -> BFTypeDisguised[_P]:
    return disguise(BFMap(undisguise(field), vm, default))


def bf_int(n: int, *, default: int | None = None) -> BFTypeDisguised[int]:
    class BitsAsInt:
        def forward(self, x: Bits) -> int:
            return x.to_int()

        def back(self, y: int) -> Bits:
            return Bits.from_int(y, n)

    return bf_map(bf_bits(n), BitsAsInt(), default=default)


def bf_bool(*, default: bool | None = None) -> BFTypeDisguised[bool]:
    class IntAsBool:
        def forward(self, x: int) -> bool:
            return x == 1

        def back(self, y: bool) -> int:
            return 1 if y else 0

    return bf_map(bf_int(1), IntAsBool(), default=default)


_E = t.TypeVar("_E", bound=IntEnum | IntFlag)


def bf_int_enum(enum: t.Type[_E], n: int, default: _E | None = None) -> BFTypeDisguised[_E]:
    class IntAsEnum:
        def forward(self, x: int) -> _E:
            return enum(x)

        def back(self, y: _E) -> int:
            return y.value

    return bf_map(bf_int(n), IntAsEnum(), default=default)


@t.overload
def bf_list(
    item: t.Type[_BitfieldT],
    n: int,
    *,
    default: t.List[_BitfieldT] | None = None
) -> BFTypeDisguised[t.List[_BitfieldT]]: ...


@t.overload
def bf_list(
    item: BFTypeDisguised[_T],
    n: int,
    *,
    default: t.List[_T] | None = None
) -> BFTypeDisguised[t.List[_T]]: ...


def bf_list(
    item: t.Type[_BitfieldT] | BFTypeDisguised[_T],
    n: int, *,
    default: t.List[_BitfieldT] | t.List[_T] | None = None
) -> BFTypeDisguised[t.List[_BitfieldT]] | BFTypeDisguised[t.List[_T]]:

    if default is not None and len(default) != n:
        raise ValueError(f"expected list of length {n}, got {default!r}")
    return disguise(BFList(undisguise(item), n, default))


_LT = t.TypeVar("_LT", bound=str | int | float | bytes | Enum)


def bf_lit(field: BFTypeDisguised[_LT], *, default: _P) -> BFTypeDisguised[_P]:
    return disguise(BFLit(undisguise(field), default))


def bf_bytes(n: int, *, default: bytes | None = None) -> BFTypeDisguised[bytes]:
    if default is not None and len(default) != n:
        raise ValueError(f"expected bytes of length {n}, got {default!r}")

    class ListAsBytes:
        def forward(self, x: t.List[int]) -> bytes:
            return bytes(x)

        def back(self, y: bytes) -> t.List[int]:
            return list(y)

    return bf_map(bf_list(bf_int(8), n), ListAsBytes(), default=default)


def bf_str(n: int, encoding: str = "utf-8", *, default: str | None = None) -> BFTypeDisguised[str]:
    if default is not None:
        byte_len = len(default.encode(encoding))
        if byte_len != n:
            raise ValueError(
                f"expected default string of length {n} bytes, got {byte_len} bytes"
            )

    class BytesAsStr:
        def forward(self, x: bytes) -> str:
            return x.decode(encoding)

        def back(self, y: str) -> bytes:
            return y.encode(encoding)

    return bf_map(bf_bytes(n), BytesAsStr(), default=default)


def bf_dyn(
    fn: t.Callable[[t.Any, int], t.Type[_T] | BFTypeDisguised[_T]],
    default: _T | None = None
) -> BFTypeDisguised[_T]:
    return disguise(BFDyn(fn, default))


def bf_none(*, default: None = None) -> BFTypeDisguised[None]:
    return disguise(BFNone())


def bf_bitfield(
    cls: t.Type[_BitfieldT],
    n: int,
    *,
    default: _BitfieldT | None = None
):
    class BitsAsBitfield:
        def forward(self, x: Bits) -> _BitfieldT:
            return cls.from_bits(x)

        def back(self, y: _BitfieldT) -> Bits:
            return y.to_bits()

    return bf_map(bf_bits(n), BitsAsBitfield(), default=default)


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
    def from_bits(cls, bits: Bits) -> Bitfield:
        raise NotImplementedError

    def to_bits(self) -> Bits:
        raise NotImplementedError

    def __init_subclass__(cls):
        if not hasattr(cls, "_bf_fields"):
            cls._bf_fields = {}

        for name, type_hint in t.get_type_hints(cls).items():
            if t.get_origin(type_hint) is t.ClassVar:
                continue

            value = getattr(cls, name) if hasattr(cls, name) else None

            try:
                bf_field = distill_field_def(type_hint, value)
            except TypeError as e:
                raise TypeError(
                    f"error in field {name!r} of {cls.__name__!r}: {e}"
                )

            cls._bf_fields[name] = bf_field


def distill_field_def(type_hint: t.Any, value: t.Any) -> BFType:
    if value is None and type_hint is not type(None):
        if isinstance(type_hint, type) and issubclass(type_hint, Bitfield):
            return undisguise(type_hint)

        if t.get_origin(type_hint) is t.Literal:
            args = t.get_args(type_hint)

            if len(args) != 1:
                raise TypeError(
                    f"expected literal with one argument, got {args!r}")

            return undisguise(args[0])

    return undisguise(value)


_BitfieldT = t.TypeVar("_BitfieldT", bound=Bitfield)


class Baz(Bitfield):
    a: int = bf_int(3)
    b: int = bf_int(10)


def foo2(x: Bar, n: int):
    if n == 1:
        return None
    else:
        return bf_int(5)


def bar(x: Bar, n: int):
    return None


class Bar(Bitfield):
    a: float = bf_map(bf_int(5), Scale(1 / 100))
    b: t.Literal['hello']
    c: t.Literal[b'hello'] = b'hello'
    d: Baz
    e: t.List[Baz] = bf_list(Baz, 3)
    f: int | None = bf_dyn(foo2)
    g: t.List[None] = bf_list(bf_dyn(bar), 3)


def foo(x: Foo, n: int) -> t.Literal[10] | list[float]:
    if n == 1:
        return bf_list(bf_map(bf_int(5), Scale(100)), 1)
    else:
        return bf_lit(bf_int(5), default=10)


class Foo(Bitfield):
    a: float = bf_map(bf_int(2), Scale(1 / 100))
    _pad: t.Literal[0x5] = bf_lit(bf_int(3), default=0x5)
    ff: Baz
    ay: t.Literal[b'world'] = b'world'
    ab: int = bf_int(10)
    ac: int = bf_int(2)
    zz: BarEnum = bf_int_enum(BarEnum, 2)
    yy: bytes = bf_bytes(2)
    ad: int = bf_int(3)
    b: int | t.Literal["current"] = bf_map(bf_int(2), LocChMap())
    c: t.Literal[10] | list[float] | Baz = bf_dyn(foo)
    d: t.List[int] = bf_list(bf_int(10), 3)
    e: t.List[Baz] = bf_list(Baz, 3)
    f: t.Literal["Hello"] = bf_lit(bf_str(5), default="Hello")
    h: t.Literal["Hello"] = "Hello"
    g: t.List[t.List[int]] = bf_list(bf_list(bf_int(10), 3), 3)
