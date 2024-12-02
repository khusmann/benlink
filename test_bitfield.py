from __future__ import annotations

import typing as t
import pytest
import re

from enum import IntEnum

from bitfield import (
    Bitfield,
    bf_str,
    bf_bytes,
    bf_list,
    bf_int,
    bf_dyn,
    bf_map,
    bf_lit,
    bf_int_enum,
    Scale
)


def test_basic():
    class Work(Bitfield):
        a: int = bf_int(4)
        b: t.List[int] = bf_list(bf_int(3), 4)
        c: str = bf_str(3)
        d: bytes = bf_bytes(4)

    work = Work(a=1, b=[1, 2, 3, 4], c="abc", d=b"abcd")
    assert work.to_bytes() == b'\x12\x9cabcabcd'
    assert Work.from_bytes(work.to_bytes()) == work


class BarEnum(IntEnum):
    A = 1
    B = 2
    C = 3


def foo(x: Foo, _: t.Any) -> t.Literal[10] | list[float]:
    if x.ab == 1:
        return bf_list(bf_map(bf_int(5), Scale(100)), 1)
    else:
        return bf_lit(bf_int(5), default=10)


class Baz(Bitfield):
    a: int = bf_int(3)
    b: int = bf_int(10)


class Foo(Bitfield):
    a: float = bf_map(bf_int(2), Scale(1 / 2))
    _pad: t.Literal[0x5] = bf_lit(bf_int(3), default=0x5)
    ff: Baz
    ay: t.Literal[b'world'] = b'world'
    ab: int = bf_int(10)
    ac: int = bf_int(2)
    zz: BarEnum = bf_int_enum(BarEnum, 2)
    yy: bytes = bf_bytes(2)
    ad: int = bf_int(3)
    c: t.Literal[10] | list[float] | Baz = bf_dyn(foo)
    d: t.List[int] = bf_list(bf_int(10), 3)
    e: t.List[Baz] = bf_list(Baz, 3)
    f: t.Literal["Hello"] = bf_lit(bf_str(5), default="Hello")
    h: t.Literal["Hello"] = "Hello"
    g: t.List[t.List[int]] = bf_list(bf_list(bf_int(10), 3), 3)
    xx: int = bf_int(1)


def test_kitchen_sink():
    f = Foo(
        a=0.5,
        ff=Baz(a=1, b=2),
        ab=0x3ff,
        ac=3,
        zz=BarEnum.B,
        yy=b'hi',
        ad=3,
        c=10,
        d=[1, 2, 3],
        e=[Baz(a=1, b=2), Baz(a=3, b=4), Baz(a=5, b=6)],
        g=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        xx=1,
    )

    assert f.to_bytes() == b'i\x00\x9d\xdb\xdc\x9b\x19?\xfehij\x00@ \x0c\x80L\x04\xa02C+cczC+ccx\x02\x01\x00` \n\x03\x00\xe0@\x13'
    assert Foo.from_bytes(f.to_bytes()) == f


def test_default_len_err():
    class Work(Bitfield):
        a: str = bf_str(4, default="ทt")
        b: bytes = bf_bytes(3, default=b"abc")
        c: t.Literal["ทt"] = "ทt"
        d: t.List[int] = bf_list(bf_int(3), 4, default=[1, 2, 3, 4])

    assert Work.length() == 11*8 + 3*4

    with pytest.raises(ValueError, match=re.escape("expected default string of length 3 bytes, got 4 bytes ('ทt')")):
        class Fail1(Bitfield):
            a: str = bf_str(3, default="ทt")
        print(Fail1)

    with pytest.raises(ValueError, match=re.escape("expected default bytes of length 4 bytes, got 3 bytes (b'abc')")):
        class Fail2(Bitfield):
            a: bytes = bf_bytes(4, default=b"abc")
        print(Fail2)

    with pytest.raises(ValueError, match=re.escape("expected default list of length 4, got 3 ([1, 2, 3])")):
        class Fail3(Bitfield):
            a: t.List[int] = bf_list(bf_int(3), 4, default=[1, 2, 3])
        print(Fail3)


def test_incorrect_field_types():
    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail1': expected a field type, got 1")):
        class Fail1(Bitfield):
            a: int = 1
        print(Fail1)

    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail2': missing field definition")):
        class Fail2(Bitfield):
            a: int
        print(Fail2)


class DynFoo(Bitfield):
    a: int = bf_dyn(lambda _, __: bf_int(4))


def test_dyn_infer_err():
    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail': cannot infer length for dynamic Bitfield")):
        class Fail(Bitfield):
            a: DynFoo
        print(Fail)


def test_lit_field_err():
    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail': literal must have exactly one argument")):
        class Fail(Bitfield):
            a: t.Literal[1, 2]
        print(Fail)


def test_default_children_err():
    with pytest.raises(ValueError, match=re.escape("error in field 'a' of 'Fail': inner field definitions cannot have defaults set (except literal fields)")):
        class Fail(Bitfield):
            a: t.List[int] = bf_list(bf_int(4, default=10), 4)
        print(Fail)