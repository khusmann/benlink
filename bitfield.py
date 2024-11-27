from __future__ import annotations

from typing_extensions import dataclass_transform
import typing as t

from enum import IntEnum, IntFlag


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


class Identity(t.Generic[_T]):
    def forward(self, x: _T) -> _T:
        return x

    def back(self, y: _T) -> _T:
        return y


_E = t.TypeVar("_E", bound=IntEnum | IntFlag)


class AsEnum(t.Generic[_E]):
    enum: t.Type[_E]

    def __init__(self, enum: t.Type[_E]):
        self.enum = enum

    def forward(self, x: int) -> _E:
        return self.enum(x)

    def back(self, y: _E) -> int:
        return y.value


_IntValue = t.TypeVar("_IntValue", bound=int)


class AssertValue(t.Generic[_IntValue]):
    def __init__(self, value: _IntValue):
        self.value = value

    def forward(self, x: t.Any) -> _IntValue:
        if x != self.value:
            raise ValueError(f"expected {self.value!r}, got {x!r}")
        return x

    def back(self, y: _IntValue) -> t.Any:
        if y != self.value:
            raise ValueError(f"expected {self.value!r}, got {y!r}")
        return y


class ScaledBy:
    def __init__(self, by: int) -> None:
        self.by = by

    def forward(self, x: int):
        return x / self.by

    def back(self, y: float):
        return round(y * self.by)


class LocChMap:
    def forward(self, x: int):
        return x - 1 if x > 0 else None

    def back(self, y: int | None):
        return 0 if y is None else y + 1


class Bits(t.Generic[_T]):
    n: int
    transform: ValueMapper[int, _T]
    default: _T | None

    def __init__(
        self,
        n: int,
        transform: ValueMapper[int, _T] = Identity[int](),
        default: _T | None = None
    ):
        self.n = n
        self.transform = transform
        self.default = default


class Bytes(t.Generic[_T]):
    n: int
    transform: ValueMapper[bytes, _T]
    default: _T | None

    def __init__(
        self,
        n: int,
        transform: ValueMapper[bytes, _T] = Identity[bytes](),
        default: _T | None = None
    ):
        self.n = n
        self.transform = transform
        self.default = default


class Items(t.Generic[_T]):
    item: Bits[_T] | Bytes[_T] | Items[_T]
    n: int

    def __init__(self, item: Bits[_T] | Bytes[_T] | Items[_T], n: int):
        self.item = item
        self.n = n


def bf_dyn(
    fn: t.Callable[[t.Any, int], t.Tuple[t.Type[_T], Bits[_T] | Bytes[_T] | Items[_T] | _T]],
    default: _T | None = None
) -> _T:
    return 5  # type: ignore


def bf_int(
    n: int,
    map: ValueMapper[int, _T] = Identity[int](),
    default: _T | None = None,
) -> _T:
    out = Bits(n, map, default)
    return out  # type: ignore


def bf_const(
    n: int,
    *,
    default: _IntValue
) -> _IntValue:
    return bf_int(
        n, map=AssertValue(default), default=default
    )


def bf_byte(
    n: int,
    transform: ValueMapper[bytes, _T] = Identity[bytes](),
    default: _T | None = None,
) -> _T:
    out = Bytes(n, transform, default)
    return out  # type: ignore


def bf_seq(
    item: Bits[_T] | Bytes[_T] | Items[_T] | t.Type[_T] | _T,
    n: int,
) -> t.List[_T]:
    if not isinstance(item, (Bits, Bytes, Items)):
        raise TypeError(f"item must be Bits or Bytes, got {item!r}")
    item = t.cast(Bits[_T] | Bytes[_T] | Items[_T], item)
    out = Items(item, n)
    return out  # type: ignore


@dataclass_transform(
    kw_only_default=True,
    field_specifiers=(
        bf_dyn,
        bf_int,
        bf_byte,
        bf_seq,
        bf_const,
    )
)
class Bitfield:
    pass


class Bar(Bitfield):
    a: int = bf_int(5)

    _bits_reorder: t.ClassVar[t.Sequence[int]] = []


def foo(x: Foo, n: int):
    if n == 1:
        return (t.List[float], bf_seq(bf_int(5, map=ScaledBy(100)), 1))
    else:
        return (int, bf_int(3))


class Foo(Bitfield):
    a: float = bf_int(2, map=ScaledBy(100))
    aa: t.Literal[5] = bf_int(3, map=AssertValue(5), default=5)
    _pad: t.Literal[0x5] = bf_const(3, default=0x5)
    ay: t.Literal[b'world'] = b'world'
    ab: int = bf_int(10)
    ac: int = bf_int(2)
    zz: BarEnum = bf_int(2, map=AsEnum(BarEnum))
    yy: bytes = bf_byte(2)
    ad: int = bf_int(1)
    b: int | None = bf_int(2, map=LocChMap())
    c: int | None | list[float] = bf_dyn(foo)
    d: t.List[int] = bf_seq(bf_int(10), 3)
    e: t.List[Bar] = bf_seq(Bar, 3)
    f: Bar
    g: t.List[t.List[int]] = bf_seq(bf_seq(bf_int(10), 3), 3)

    _bits_reorder = [*range(0, 4), *range(20, 24)]
