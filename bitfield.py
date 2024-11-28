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
    def __init__(self, by: int) -> None:
        self.by = by

    def forward(self, x: int):
        return x / self.by

    def back(self, y: float):
        return round(y * self.by)


class LocChMap:
    def forward(self, x: int) -> int | t.Literal["current"]:
        return x - 1 if x > 0 else "current"

    def back(self, y: int | t.Literal["current"]):
        return 0 if y == "current" else y + 1


def assert_bf_type(x: BFType[_T] | BFTypeDisguised[_T]) -> BFType[_T]:
    if isinstance(x, type) and issubclass(x, Bitfield):
        # TODO
        x = bf_bitfield(x, 9000)  # type: ignore
    if not isinstance(x, (BFBits, BFList, BFMap, BFDyn, BFLit)):
        raise TypeError(f"field must be a field type, got {x!r}")
    x = t.cast(BFType[_T], x)
    return x


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


class BFList(t.Generic[_T]):
    item: BFType[_T]
    n: int
    default: t.List[_T] | None

    def __init__(self, item: BFType[_T], n: int, default: t.List[_T] | None):
        self.item = item
        self.n = n
        self.default = default

    def __repr__(self) -> str:
        return f"BFList({self.item!r}, {self.n})"


class BFMap(t.Generic[_T, _P]):
    inner: BFType[_T]
    vm: ValueMapper[_T, _P]
    default: _P | None

    def __init__(self, inner: BFType[_T], vm: ValueMapper[_T, _P], default: _P | None):
        self.inner = inner
        self.vm = vm
        self.default = default

    def __repr__(self) -> str:
        return f"BFMap({self.inner!r})"


class BFDyn(t.Generic[_T]):
    fn: t.Callable[[t.Any, int], BFType[_T] | BFTypeDisguised[_T]]
    default: _T | None

    def __init__(
        self,
        fn: t.Callable[[t.Any, int], BFType[_T] | BFTypeDisguised[_T]],
        default: _T | None,
    ):
        self.fn = fn
        self.default = default

    def __repr__(self) -> str:
        return f"BFDyn(<fn>)"


class BFLit(t.Generic[_T]):
    field: BFType[t.Any]
    default: _T

    def __init__(self, field: BFType[t.Any], default: _T):
        self.field = field
        self.default = default

    def __repr__(self):
        return f"BFLit({self.field!r})"


BFType = t.Union[BFBits, BFList[_T], BFMap[t.Any, _T], BFDyn[_T], BFLit[_T]]

BFTypeDisguised = t.Type[_T] | _T


def bf_bits(n: int, *, default: Bits | None = None) -> Bits:
    out = BFBits(n, default)
    return out  # type: ignore


def bf_map(field: BFType[_T] | BFTypeDisguised[_T], vm: ValueMapper[_T, _P], *, default: _P | None = None) -> _P:
    out = BFMap[_T, _P](assert_bf_type(field), vm, default)
    return out  # type: ignore


def bf_int(n: int, *, default: int | None = None) -> int:
    class BitsAsInt:
        def forward(self, x: Bits) -> int:
            return x.to_int()

        def back(self, y: int) -> Bits:
            return Bits.from_int(y, n)

    return bf_map(bf_bits(n), BitsAsInt(), default=default)


def bf_bool(*, default: bool | None = None) -> bool:
    class IntAsBool:
        def forward(self, x: int) -> bool:
            return x == 1

        def back(self, y: bool) -> int:
            return 1 if y else 0

    return bf_map(bf_int(1), IntAsBool(), default=default)


_E = t.TypeVar("_E", bound=IntEnum | IntFlag)


def bf_int_enum(enum: t.Type[_E], n: int, default: _E | None = None) -> _E:
    class IntAsEnum:
        def forward(self, x: int) -> _E:
            return enum(x)

        def back(self, y: _E) -> int:
            return y.value

    return bf_map(bf_int(n), IntAsEnum(), default=default)


def bf_list(item: BFType[_T] | BFTypeDisguised[_T], n: int, *, default: t.List[_T] | None = None) -> t.List[_T]:
    if default is not None and len(default) != n:
        raise ValueError(f"expected list of length {n}, got {default!r}")
    out = BFList[_T](assert_bf_type(item), n, default)
    return out  # type: ignore


_LT = t.TypeVar("_LT", bound=str | int | float | bytes | Enum)


def bf_lit(field: BFType[_LT] | BFTypeDisguised[_LT], *, default: _P) -> _P:
    out = BFLit(assert_bf_type(field), default)
    return out  # type: ignore


def bf_bytes(n: int, *, default: bytes | None = None) -> bytes:
    if default is not None and len(default) != n:
        raise ValueError(f"expected bytes of length {n}, got {default!r}")

    class ListAsBytes:
        def forward(self, x: t.List[int]) -> bytes:
            return bytes(x)

        def back(self, y: bytes) -> t.List[int]:
            return list(y)

    return bf_map(bf_list(bf_int(8), n), ListAsBytes(), default=default)


def bf_str(n: int, encoding: str = "utf-8", *, default: str | None = None) -> str:
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
    fn: t.Callable[[t.Any, int], BFType[_T] | BFTypeDisguised[_T]],
    default: _T | None = None
) -> _T:
    out = BFDyn(fn, default)
    return out  # type: ignore


def bf_bitfield(
    cls: t.Type[_BFT],
    n: int,
    *,
    default: _BFT | None = None
):
    class BitsAsBitfield:
        def forward(self, x: Bits) -> _BFT:
            return cls.from_bits(x)

        def back(self, y: _BFT) -> Bits:
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
    _bf_fields: t.ClassVar[t.Dict[str, BFType[t.Any]]]

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

            bf_field = distill_bitfield(name, type_hint, value)

            cls._bf_fields[name] = bf_field


def distill_bitfield(name: str, type_hint: t.Any, value: t.Any) -> BFType[t.Any]:
    if isinstance(value, (BFBits, BFList, BFMap, BFDyn, BFLit)):
        value = t.cast(BFType[t.Any], value)
        return value

    if t.get_origin(type_hint) is t.Literal:
        args = t.get_args(type_hint)

        if len(args) != 1:
            raise TypeError(
                f"field {name}: expected literal with one argument, got {args!r}")

        match args[0]:
            case bytes():
                out = bf_bytes(len(args[0]))
                return out  # type: ignore
            case str():
                out = bf_str(len(args[0].encode("utf-8")))
                return out  # type: ignore
            case _:
                raise TypeError(
                    f"field {name}: unsupported literal type {args[0]!r}")

    if isinstance(type_hint, type) and issubclass(type_hint, Bitfield) and value is None:
        out = bf_bitfield(type_hint, 9000)
        return out  # type: ignore

    if value is None:
        raise TypeError(f"field {name}: missing field definition")
    else:
        raise TypeError(f"field {name}: invalid field definition")


_BFT = t.TypeVar("_BFT", bound=Bitfield)


class Bar(Bitfield):
    a: int = bf_int(5)
    b: t.Literal[b'hello']
    c: t.Literal[b'hello'] = b'hello'

# def foo(x: Foo, n: int) -> t.Literal[10] | list[float]:
#    if n == 1:
#        return bf_list(bf_map(bf_int(5), Scale(100)), 1)
#    else:
#        return bf_lit(bf_int(5), default=10)


# class Foo(Bitfield):
#    a: float = bf_map(bf_int(2), Scale(100))
#    _pad: t.Literal[0x5] = bf_lit(bf_int(3), default=0x5)
#    ff: Bar
#    ay: t.Literal[b'world'] = b'world'
#    ab: int = bf_int(10)
#    ac: int = bf_int(2)
#    zz: BarEnum = bf_int_enum(BarEnum, 2)
#    yy: bytes = bf_bytes(2)
#    ad: int = bf_int(3)
#    b: int | t.Literal["current"] = bf_map(bf_int(2), LocChMap())
#    c: t.Literal[10] | list[float] | Bar = bf_dyn(foo)
#    d: t.List[int] = bf_list(bf_int(10), 3)
#    e: t.List[Bar] = bf_list(Bar, 3)
#    f: t.Literal["Hello"] = bf_lit(bf_str(5), default="Hello")
#    h: t.Literal["Hello"] = "Hello"
#    g: t.List[t.List[int]] = bf_list(bf_list(bf_int(10), 3), 3)
#
#    _bits_reorder = [*range(0, 4), *range(20, 24)]
