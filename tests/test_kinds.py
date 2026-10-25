"""
Round-trip every value kind (design section 6, item 1).

Each kind is added, read back, serialized, deserialized and read back again.
Min and max values of every integer type and NaN / infinities for the float
types are included.
"""

import math
import sys
import unittest
from typing import Any, List

from fon import FonCollection, FonDump, FonKind


def roundtrip_line(col: FonCollection) -> FonCollection:
    return FonCollection.deserialize(col.serialize())


class TestScalarKinds(unittest.TestCase):
    def test_byte_min_max(self) -> None:
        for value in (0, 255):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_byte("v", value)
                self.assertEqual(col.get_byte("v"), value)
                self.assertEqual(roundtrip_line(col).get_byte("v"), value)

    def test_short_min_max(self) -> None:
        for value in (-32768, 32767):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_short("v", value)
                self.assertEqual(col.get_short("v"), value)
                self.assertEqual(roundtrip_line(col).get_short("v"), value)

    def test_int_min_max(self) -> None:
        for value in (-(2 ** 31), 2 ** 31 - 1):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_int("v", value)
                self.assertEqual(col.get_int("v"), value)
                self.assertEqual(roundtrip_line(col).get_int("v"), value)

    def test_uint_min_max(self) -> None:
        for value in (0, 2 ** 32 - 1):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_uint("v", value)
                self.assertEqual(col.get_uint("v"), value)
                self.assertEqual(roundtrip_line(col).get_uint("v"), value)

    def test_long_min_max(self) -> None:
        for value in (-(2 ** 63), 2 ** 63 - 1):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_long("v", value)
                self.assertEqual(col.get_long("v"), value)
                self.assertEqual(roundtrip_line(col).get_long("v"), value)

    def test_ulong_min_max(self) -> None:
        for value in (0, 2 ** 64 - 1):
            with self.subTest(value=value):
                col = FonCollection()
                col.add_ulong("v", value)
                self.assertEqual(col.get_ulong("v"), value)
                self.assertEqual(roundtrip_line(col).get_ulong("v"), value)

    def test_float_limits_and_special_values(self) -> None:
        values: List[float] = [
            3.4028234663852886e38,
            -3.4028234663852886e38,
            1.1754943508222875e-38,
            0.0,
            math.inf,
            -math.inf,
        ]
        for value in values:
            with self.subTest(value=value):
                col = FonCollection()
                col.add_float("v", value)
                self.assertEqual(col.get_float("v"), value)
                self.assertEqual(roundtrip_line(col).get_float("v"), value)

    def test_float_nan(self) -> None:
        col = FonCollection()
        col.add_float("v", math.nan)
        self.assertTrue(math.isnan(col.get_float("v")))
        self.assertTrue(math.isnan(roundtrip_line(col).get_float("v")))

    def test_double_limits_and_special_values(self) -> None:
        values: List[float] = [
            sys.float_info.max,
            -sys.float_info.max,
            sys.float_info.min,
            0.0,
            math.inf,
            -math.inf,
        ]
        for value in values:
            with self.subTest(value=value):
                col = FonCollection()
                col.add_double("v", value)
                self.assertEqual(col.get_double("v"), value)
                self.assertEqual(roundtrip_line(col).get_double("v"), value)

    def test_double_nan(self) -> None:
        col = FonCollection()
        col.add_double("v", math.nan)
        self.assertTrue(math.isnan(col.get_double("v")))
        self.assertTrue(math.isnan(roundtrip_line(col).get_double("v")))

    def test_bool_both_values(self) -> None:
        col = FonCollection()
        col.add_bool("t", True)
        col.add_bool("f", False)
        restored: FonCollection = roundtrip_line(col)
        self.assertTrue(restored.get_bool("t"))
        self.assertFalse(restored.get_bool("f"))

    def test_string_and_raw(self) -> None:
        payload: bytes = bytes(range(256))
        col = FonCollection()
        col.add_string("s", "hello, world")
        col.add_raw("r", payload)
        restored: FonCollection = roundtrip_line(col)
        self.assertEqual(restored.get_string("s"), "hello, world")
        self.assertEqual(restored.get_raw("r"), payload)

    def test_raw_empty(self) -> None:
        col = FonCollection()
        col.add_raw("r", b"")
        self.assertEqual(roundtrip_line(col).get_raw("r"), b"")


class TestArrayKinds(unittest.TestCase):
    def test_byte_array(self) -> None:
        values: List[int] = [0, 1, 127, 128, 255]
        col = FonCollection()
        col.add_byte_array("v", values)
        self.assertEqual(col.get_byte_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_byte_array("v"), values)

    def test_short_array(self) -> None:
        values: List[int] = [-32768, -1, 0, 32767]
        col = FonCollection()
        col.add_short_array("v", values)
        self.assertEqual(col.get_short_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_short_array("v"), values)

    def test_int_array(self) -> None:
        values: List[int] = [-(2 ** 31), -1, 0, 2 ** 31 - 1]
        col = FonCollection()
        col.add_int_array("v", values)
        self.assertEqual(col.get_int_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_int_array("v"), values)

    def test_uint_array(self) -> None:
        values: List[int] = [0, 1, 2 ** 32 - 1]
        col = FonCollection()
        col.add_uint_array("v", values)
        self.assertEqual(col.get_uint_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_uint_array("v"), values)

    def test_long_array(self) -> None:
        values: List[int] = [-(2 ** 63), -1, 0, 2 ** 63 - 1]
        col = FonCollection()
        col.add_long_array("v", values)
        self.assertEqual(col.get_long_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_long_array("v"), values)

    def test_ulong_array(self) -> None:
        values: List[int] = [0, 1, 2 ** 64 - 1]
        col = FonCollection()
        col.add_ulong_array("v", values)
        self.assertEqual(col.get_ulong_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_ulong_array("v"), values)

    def test_float_array_special_values(self) -> None:
        values: List[float] = [3.4028234663852886e38, -math.inf, 0.5, 0.0]
        col = FonCollection()
        col.add_float_array("v", values)
        self.assertEqual(col.get_float_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_float_array("v"), values)

    def test_float_array_nan(self) -> None:
        col = FonCollection()
        col.add_float_array("v", [math.nan, math.inf])
        restored: List[float] = roundtrip_line(col).get_float_array("v")
        self.assertTrue(math.isnan(restored[0]))
        self.assertEqual(restored[1], math.inf)

    def test_double_array_special_values(self) -> None:
        values: List[float] = [sys.float_info.max, -sys.float_info.max, -math.inf, 0.25]
        col = FonCollection()
        col.add_double_array("v", values)
        self.assertEqual(col.get_double_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_double_array("v"), values)

    def test_bool_array(self) -> None:
        values: List[bool] = [True, False, False, True]
        col = FonCollection()
        col.add_bool_array("v", values)
        self.assertEqual(col.get_bool_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_bool_array("v"), values)

    def test_string_array(self) -> None:
        values: List[str] = ["alpha", "", "é", "😀"]
        col = FonCollection()
        col.add_string_array("v", values)
        self.assertEqual(col.get_string_array("v"), values)
        self.assertEqual(roundtrip_line(col).get_string_array("v"), values)

    def test_empty_arrays_of_every_kind(self) -> None:
        col = FonCollection()
        col.add_byte_array("b", [])
        col.add_short_array("h", [])
        col.add_int_array("i", [])
        col.add_uint_array("u", [])
        col.add_long_array("l", [])
        col.add_ulong_array("g", [])
        col.add_float_array("f", [])
        col.add_double_array("d", [])
        col.add_bool_array("z", [])
        col.add_string_array("s", [])
        restored: FonCollection = roundtrip_line(col)
        self.assertEqual(restored.get_byte_array("b"), [])
        self.assertEqual(restored.get_short_array("h"), [])
        self.assertEqual(restored.get_int_array("i"), [])
        self.assertEqual(restored.get_uint_array("u"), [])
        self.assertEqual(restored.get_long_array("l"), [])
        self.assertEqual(restored.get_ulong_array("g"), [])
        self.assertEqual(restored.get_float_array("f"), [])
        self.assertEqual(restored.get_double_array("d"), [])
        self.assertEqual(restored.get_bool_array("z"), [])
        self.assertEqual(restored.get_string_array("s"), [])


class TestNestedKinds(unittest.TestCase):
    def test_nested_collection(self) -> None:
        inner = FonCollection()
        inner.add_int("x", 7)
        outer = FonCollection()
        outer.add_collection("c", inner)
        restored: FonCollection = roundtrip_line(outer)
        self.assertEqual(restored.get_collection("c").get_int("x"), 7)

    def test_collection_array(self) -> None:
        children: List[FonCollection] = []
        for index in range(3):
            child = FonCollection()
            child.add_long("i", index)
            children.append(child)
        outer = FonCollection()
        outer.add_collection_array("rows", children)
        restored: FonCollection = roundtrip_line(outer)
        rows: List[FonCollection] = restored.get_collection_array("rows")
        self.assertEqual([row.get_long("i") for row in rows], [0, 1, 2])


class TestKindIntrospection(unittest.TestCase):
    def test_kind_names_for_all_kinds(self) -> None:
        col = FonCollection()
        col.add_byte("byte", 1)
        col.add_short("short", 1)
        col.add_int("int", 1)
        col.add_uint("uint", 1)
        col.add_long("long", 1)
        col.add_ulong("ulong", 1)
        col.add_float("float", 1.0)
        col.add_double("double", 1.0)
        col.add_bool("bool", True)
        col.add_string("string", "s")
        col.add_raw("raw", b"r")
        col.add_int_array("int_array", [1])
        col.add_collection("object", FonCollection())
        col.add_collection_array("object_array", [FonCollection()])

        self.assertEqual(col.kind("byte"), FonKind("byte", False))
        self.assertEqual(col.kind("short"), FonKind("short", False))
        self.assertEqual(col.kind("int"), FonKind("int", False))
        self.assertEqual(col.kind("uint"), FonKind("uint", False))
        self.assertEqual(col.kind("long"), FonKind("long", False))
        self.assertEqual(col.kind("ulong"), FonKind("ulong", False))
        self.assertEqual(col.kind("float"), FonKind("float", False))
        self.assertEqual(col.kind("double"), FonKind("double", False))
        self.assertEqual(col.kind("bool"), FonKind("bool", False))
        self.assertEqual(col.kind("string"), FonKind("string", False))
        self.assertEqual(col.kind("raw"), FonKind("raw", False))
        self.assertEqual(col.kind("int_array"), FonKind("int", True))
        self.assertEqual(col.kind("object"), FonKind("object", False))
        self.assertEqual(col.kind("object_array"), FonKind("object", True))
        self.assertIsNone(col.kind("missing"))

    def test_dynamic_get_returns_typed_values(self) -> None:
        col = FonCollection()
        col.add_int("n", -5)
        col.add_string("s", "x")
        col.add_raw("r", b"\x00\x01")
        col.add_bool_array("z", [True, False])
        values: List[Any] = [col.get("n"), col.get("s"), col.get("r"), col.get("z")]
        self.assertEqual(values, [-5, "x", b"\x00\x01", [True, False]])


class TestDumpRoundtripAllKinds(unittest.TestCase):
    def test_dump_roundtrip_every_kind(self) -> None:
        col = FonCollection()
        col.add_byte("byte", 255)
        col.add_short("short", -32768)
        col.add_int("int", -(2 ** 31))
        col.add_uint("uint", 2 ** 32 - 1)
        col.add_long("long", -(2 ** 63))
        col.add_ulong("ulong", 2 ** 64 - 1)
        col.add_float("float", 1.5)
        col.add_double("double", -2.25)
        col.add_bool("bool", True)
        col.add_string("string", "text")
        col.add_raw("raw", b"\x00\xff")
        col.add_byte_array("byte_array", [1, 2])
        col.add_short_array("short_array", [-1, 2])
        col.add_int_array("int_array", [-1, 2])
        col.add_uint_array("uint_array", [1, 2])
        col.add_long_array("long_array", [-1, 2])
        col.add_ulong_array("ulong_array", [1, 2])
        col.add_float_array("float_array", [1.5, -2.5])
        col.add_double_array("double_array", [0.125])
        col.add_bool_array("bool_array", [False, True])
        col.add_string_array("string_array", ["a", "b"])
        child = FonCollection()
        child.add_int("c", 1)
        col.add_collection("collection", child)
        grand = FonCollection()
        grand.add_int("g", 2)
        col.add_collection_array("collection_array", [grand])

        dump = FonDump()
        dump.add(0, col)
        restored: FonDump = FonDump.deserialize(dump.serialize())
        entry: FonCollection = restored.get(0)
        self.assertEqual(entry.get_byte("byte"), 255)
        self.assertEqual(entry.get_short("short"), -32768)
        self.assertEqual(entry.get_int("int"), -(2 ** 31))
        self.assertEqual(entry.get_uint("uint"), 2 ** 32 - 1)
        self.assertEqual(entry.get_long("long"), -(2 ** 63))
        self.assertEqual(entry.get_ulong("ulong"), 2 ** 64 - 1)
        self.assertEqual(entry.get_float("float"), 1.5)
        self.assertEqual(entry.get_double("double"), -2.25)
        self.assertTrue(entry.get_bool("bool"))
        self.assertEqual(entry.get_string("string"), "text")
        self.assertEqual(entry.get_raw("raw"), b"\x00\xff")
        self.assertEqual(entry.get_byte_array("byte_array"), [1, 2])
        self.assertEqual(entry.get_short_array("short_array"), [-1, 2])
        self.assertEqual(entry.get_int_array("int_array"), [-1, 2])
        self.assertEqual(entry.get_uint_array("uint_array"), [1, 2])
        self.assertEqual(entry.get_long_array("long_array"), [-1, 2])
        self.assertEqual(entry.get_ulong_array("ulong_array"), [1, 2])
        self.assertEqual(entry.get_float_array("float_array"), [1.5, -2.5])
        self.assertEqual(entry.get_double_array("double_array"), [0.125])
        self.assertEqual(entry.get_bool_array("bool_array"), [False, True])
        self.assertEqual(entry.get_string_array("string_array"), ["a", "b"])
        self.assertEqual(entry.get_collection("collection").get_int("c"), 1)
        self.assertEqual(entry.get_collection_array("collection_array")[0].get_int("g"), 2)


if __name__ == "__main__":
    unittest.main()
