from __future__ import annotations

import typing as t
import pytest
import re

from bitfield import (
    Bitfield,
    bf_str,
    bf_bytes,
    bf_list,
    bf_int,
    bf_dyn,
)


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
    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail1': expected a bitfield type, got 1")):
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
    with pytest.raises(ValueError, match=re.escape("cannot infer length for dynamic Bitfield")):
        class Fail(Bitfield):
            a: DynFoo
        print(Fail)


def test_lit_field_err():
    with pytest.raises(TypeError, match=re.escape("error in field 'a' of 'Fail': literal must have exactly one argument")):
        class Fail(Bitfield):
            a: t.Literal[1, 2]
        print(Fail)
