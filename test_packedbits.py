from packedbits import PackedBits, bitfield


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


def test_nested_fields():
    class Inner(PackedBits):
        a: int = bitfield(4)
        b: int = bitfield(4)

    class Test(PackedBits):
        a: Inner = bitfield(8)
        b: Inner = bitfield(8)

    test = Test(a=Inner(a=1, b=2), b=Inner(a=3, b=4))
    assert test.to_bytes() == b'\x12\x34'
    assert Test.from_bytes(test.to_bytes()) == test
