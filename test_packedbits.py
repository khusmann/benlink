from __future__ import annotations
from packedbits import PackedBits, bitfield, union_bitfield, BitStream, set_literal_classvars
from dataclasses import dataclass
import typing as t
import pytest
import re


def test_int_fields():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int = bitfield(16)

    test = Test(a=1, b=2)
    assert test.to_bytes() == b'\x01\x00\x02'
    assert Test.from_bytes(test.to_bytes()) == test


def test_byte_fields():
    class Test(PackedBits):
        a: bytes = bitfield(8)
        b: bytes = bitfield(16)

    test = Test(a=b'\x01', b=b'\x12\x34')
    assert test.to_bytes() == b'\x01\x12\x34'
    assert Test.from_bytes(test.to_bytes()) == test


def test_empty_bytes():
    class Test(PackedBits):
        a: bytes = bitfield(0)

    test = Test(a=b'')
    assert test.to_bytes() == b''
    assert Test.from_bytes(test.to_bytes()) == test


def test_str_fields():
    class Test(PackedBits):
        a: str = bitfield(8)
        b: str = bitfield(16)

    test = Test(a='a', b='bc')
    assert test.to_bytes() == b'abc'
    assert Test.from_bytes(test.to_bytes()) == test


def test_none_fields():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: None = bitfield(0)

    test = Test(a=1, b=None)
    assert test.to_bytes() == b'\x01'
    assert Test.from_bytes(test.to_bytes()) == test


def test_none_union():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int | None = union_bitfield(
            lambda x: (int, 8) if x.a == 2 else None
        )

    test = Test(a=1, b=None)
    assert test.to_bytes() == b'\x01'
    assert Test.from_bytes(test.to_bytes()) == test

    test = Test(a=2, b=9)
    assert test.to_bytes() == b'\x02\x09'
    assert Test.from_bytes(test.to_bytes()) == test


def test_none_packedbits_union():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: Inner | None = union_bitfield(
            lambda x: (Inner, 8) if x.a == 2 else None
        )

    test = Test(a=1, b=None)
    assert test.to_bytes() == b'\x01'
    assert Test.from_bytes(test.to_bytes()) == test

    test = Test(a=2, b=Inner(a=1, b=2))
    assert test.to_bytes() == b'\x02\x12'
    assert Test.from_bytes(test.to_bytes()) == test


def test_none_exception():
    with pytest.raises(ValueError, match=re.escape("None field `a` must have zero bit length")):
        class Bad(PackedBits):
            a: None = bitfield(8)
        print(Bad)


def test_str_alignment():
    class Test(PackedBits):
        a: bool = bitfield(1)
        b: str = bitfield(7)

    with pytest.raises(ValueError, match=re.escape("Field `b` length (7) is not a multiple of 8")):
        Test.from_bytes(b'\x00')


def test_bytes_alignment():
    class Test(PackedBits):
        a: bool = bitfield(1)
        b: bytes = bitfield(7)

    with pytest.raises(ValueError, match=re.escape("Field `b` length (7) is not a multiple of 8")):
        Test.from_bytes(b'\x00')


def test_optional_fields():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: t.Optional[int] = union_bitfield(
            lambda x: (int, 8) if x.a == 2 else (type(None), 0)
        )

    test = Test(a=1, b=None)
    assert test.to_bytes() == b'\x01'
    assert Test.from_bytes(test.to_bytes()) == test

    test = Test(a=2, b=9)
    assert test.to_bytes() == b'\x02\x09'
    assert Test.from_bytes(test.to_bytes()) == test


def test_bool_fields():
    class Test(PackedBits):
        a: bool = bitfield(1)
        b: bool = bitfield(1)
        c: int = bitfield(6)

    test = Test(a=True, b=False, c=63)
    assert test.to_bytes() == b'\xbf'
    assert Test.from_bytes(test.to_bytes()) == test


def test_varlength_fields():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int = bitfield(lambda self: self.a * 8)
        c: int = bitfield(8)

    test = Test(a=3, b=1251, c=3)
    assert test.to_bytes() == b'\x03\x00\x04\xe3\x03'
    assert Test.from_bytes(test.to_bytes()) == test


def test_too_few_bits():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int = bitfield(8)

    with pytest.raises(ValueError, match=re.escape("Not enough bits to parse object")):
        Test.from_bytes(b'\x01')


class Inner(PackedBits):
    a: int = bitfield(4)
    b: int = bitfield(4)


def test_nested_fields():
    class Test(PackedBits):
        x: Inner = bitfield(8)
        y: Inner = bitfield(8)

    test = Test(x=Inner(a=1, b=2), y=Inner(a=3, b=4))
    assert test.to_bytes() == b'\x12\x34'
    assert Test.from_bytes(test.to_bytes()) == test


def test_implicit_nested_fields():
    class Test(PackedBits):
        a: Inner = bitfield()
        b: Inner = bitfield()

    test = Test(a=Inner(a=1, b=2), b=Inner(a=3, b=4))
    assert test.to_bytes() == b'\x12\x34'
    assert Test.from_bytes(test.to_bytes()) == test


def test_union_fields():
    def test_discriminator(incomplete: Test):
        if incomplete.a:
            return (Inner, 8)
        else:
            return (int, 8)

    class Inner(PackedBits):
        a: int = bitfield(4)
        b: int = bitfield(4)

    class Test(PackedBits):
        a: bool = bitfield(1)
        b: int = bitfield(7)
        c: int | Inner = union_bitfield(test_discriminator)

    test = Test(a=True, b=127, c=Inner(a=1, b=2))
    assert test.to_bytes() == b'\xff\x12'
    assert Test.from_bytes(test.to_bytes()) == test

    test2 = Test(a=False, b=127, c=3)
    assert test2.to_bytes() == b'\x7f\x03'
    assert Test.from_bytes(test2.to_bytes()) == test2


def test_defaults():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int = bitfield(8, default=1)
        c: int = bitfield(8, default=10)

    test = Test(a=1)
    assert test.to_bytes() == b'\x01\x01\x0a'
    assert Test.from_bytes(test.to_bytes()) == test


def test_bitfield_exception():
    with pytest.raises(TypeError, match=re.escape("Expected bitfield for field `a`, got 1")):
        class Bad(PackedBits):
            a: int = 1
        print(Bad)


def test_bitfield_exception2():
    with pytest.raises(TypeError, match=re.escape("Expected bitfield for field `a`")):
        class Bad(PackedBits):
            a: int
        print(Bad)


def test_union_field_exception():
    with pytest.raises(TypeError, match=re.escape("Expected union_bitfield() for union field `a`")):
        class Bad(PackedBits):
            a: int | Inner = bitfield(4)
        print(Bad)


def test_union_field_exception2():
    with pytest.raises(TypeError, match=re.escape("Union field `a` cannot contain literal types")):
        def discriminator(_: Bad):
            return (int, 8)

        class Bad(PackedBits):
            a: int | t.Literal[1] = union_bitfield(discriminator)
        print(Bad)


def test_literal_field_exception():
    with pytest.raises(TypeError, match=re.escape("Literal field `a` must have exactly one argument")):
        class Bad(PackedBits):
            a: t.Literal[1, 2] = bitfield(4)
        print(Bad)


def test_literal_field_exception2():
    class Bad(PackedBits):
        a: t.Literal[1] = bitfield(8)
    with pytest.raises(ValueError, match=re.escape("Field `a` has unexpected value (0)")):
        Bad.from_bytes(b'\x00')


def test_literal_field_exception3():
    class Bad(PackedBits):
        a: t.Literal[1] = bitfield(8)

    foo = Bad(a=0)  # type: ignore

    with pytest.raises(ValueError, match=re.escape("Field `a` has unexpected value (0)")):
        foo.to_bytes()


def test_negative_bitfield():
    with pytest.raises(ValueError, match=re.escape("Bitfield length must be non-negative")):
        class Bad(PackedBits):
            a: int = bitfield(-1)
        print(Bad)


def test_negative_bitfield2():
    class Bad(PackedBits):
        a: int = bitfield(lambda x: -1)
    with pytest.raises(ValueError, match=re.escape("Field `a` has non-positive bit length (-1)")):
        Bad.from_bytes(b'\x00')


def test_value_too_large():
    class Bad(PackedBits):
        a: int = bitfield(8)
    with pytest.raises(ValueError, match=re.escape("Value 500 is too large for 8 bits")):
        Bad(a=500).to_bytes()


def test_bitstream_eof():
    foo = BitStream.from_bytes(b'\x01')
    foo.read_int(8)
    with pytest.raises(EOFError):
        foo.read_bool()


def test_bitstream_eof2():
    foo = BitStream.from_bytes(b'\x01')
    foo.read_int(8)
    with pytest.raises(EOFError):
        foo.advance(1)


def test_set_literal_classvars():
    @set_literal_classvars()
    @dataclass()
    class Test:
        a: t.ClassVar[t.Literal[1]]
        b: t.Literal[2]

    assert Test.a == 1

    assert Test(2).b == 2

    with pytest.raises(AttributeError, match=re.escape("type object 'Test' has no attribute 'b'")):
        print(Test.b)


def test_set_literal_classvars_exception():
    @set_literal_classvars()
    @dataclass()
    class Good:
        a: t.ClassVar[t.Literal[1, 2]] = 1
        b: t.ClassVar[bool] = True
    assert Good.a == 1

    with pytest.raises(TypeError, match=re.escape("ClassVar field `a` is defined with multiple literal values but has no default set")):
        @set_literal_classvars()
        @dataclass()
        class Bad:
            a: t.ClassVar[t.Literal[1, 2]]
        print(Bad)
