from __future__ import annotations
from packedbits import PackedBits, bitfield, union_bitfield


def test_int_fields():
    class Test(PackedBits):
        a: int = bitfield(8)
        b: int = bitfield(16)

    test = Test(a=1, b=2)
    assert test.to_bytes() == b'\x01\x00\x02'
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


class Inner(PackedBits):
    a: int = bitfield(4)
    b: int = bitfield(4)


def test_nested_fields():
    class Test(PackedBits):
        a: Inner = bitfield(8)
        b: Inner = bitfield(8)

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
