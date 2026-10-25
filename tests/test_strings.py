"""
String handling (FON.net issue #1; design section 6, item 2).

Strings of any byte length come back whole, embedded U+0000 survives in keys
and values, keys longer than 512 bytes work, and text is never replaced with
U+FFFD.
"""

import inspect
import unittest
from typing import List

from fon import FonCollection, FonDump


REPLACEMENT_CHARACTER: str = "\ufffd"


def roundtrip_line(col: FonCollection) -> FonCollection:
    return FonCollection.deserialize(col.serialize())


class TestLongStrings(unittest.TestCase):
    def check_scalar_length(self, length: int) -> None:
        value: str = "a" * length
        col = FonCollection()
        col.add_string("v", value)
        self.assertEqual(col.get_string("v"), value)
        restored: FonCollection = roundtrip_line(col)
        self.assertEqual(restored.get_string("v"), value)
        self.assertEqual(len(restored.get_string("v").encode("utf-8")), length)

    def test_8191_bytes_scalar(self) -> None:
        self.check_scalar_length(8191)

    def test_8192_bytes_scalar(self) -> None:
        self.check_scalar_length(8192)

    def test_100000_bytes_scalar(self) -> None:
        self.check_scalar_length(100000)

    def test_long_string_as_middle_array_item(self) -> None:
        for length in (8191, 8192, 100000):
            with self.subTest(length=length):
                items: List[str] = ["x", "b" * length, "y"]
                col = FonCollection()
                col.add_string_array("v", items)
                self.assertEqual(col.get_string_array("v"), items)
                self.assertEqual(roundtrip_line(col).get_string_array("v"), items)

    def test_long_string_as_dump_record_value(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_string("body", "z" * 100000)
        dump.add(0, col)
        restored: FonDump = FonDump.deserialize(dump.serialize())
        self.assertEqual(restored.get(0).get_string("body"), "z" * 100000)


class TestMultiByteText(unittest.TestCase):
    def test_cyrillic_5000_characters_intact(self) -> None:
        value: str = "ж" * 5000
        col = FonCollection()
        col.add_string("v", value)
        result: str = roundtrip_line(col).get_string("v")
        self.assertEqual(result, value)
        self.assertNotIn(REPLACEMENT_CHARACTER, result)

    def test_emoji_2500_characters_intact(self) -> None:
        value: str = "😀" * 2500
        col = FonCollection()
        col.add_string("v", value)
        result: str = roundtrip_line(col).get_string("v")
        self.assertEqual(result, value)
        self.assertNotIn(REPLACEMENT_CHARACTER, result)

    def test_multibyte_inside_string_array(self) -> None:
        items: List[str] = ["ж" * 5000, "😀" * 2500]
        col = FonCollection()
        col.add_string_array("v", items)
        self.assertEqual(roundtrip_line(col).get_string_array("v"), items)


class TestEmbeddedNul(unittest.TestCase):
    def test_nul_in_value(self) -> None:
        value: str = "a\x00b"
        col = FonCollection()
        col.add_string("v", value)
        self.assertEqual(col.get_string("v"), value)
        self.assertEqual(roundtrip_line(col).get_string("v"), value)

    def test_nul_in_key(self) -> None:
        col = FonCollection()
        col.add_int("k\x00ey", 5)
        self.assertEqual(col.get_int("k\x00ey"), 5)
        self.assertEqual(col.keys(), ["k\x00ey"])
        restored: FonCollection = roundtrip_line(col)
        self.assertEqual(restored.keys(), ["k\x00ey"])
        self.assertEqual(restored.get_int("k\x00ey"), 5)

    def test_nul_only_value(self) -> None:
        col = FonCollection()
        col.add_string("v", "\x00")
        self.assertEqual(roundtrip_line(col).get_string("v"), "\x00")

    def test_nul_inside_string_array_item(self) -> None:
        items: List[str] = ["p\x00q", "\x00"]
        col = FonCollection()
        col.add_string_array("v", items)
        self.assertEqual(roundtrip_line(col).get_string_array("v"), items)


class TestKeysAndControlCharacters(unittest.TestCase):
    def test_key_longer_than_512_bytes_enumerates_and_reads_back(self) -> None:
        key: str = "k" * 600
        col = FonCollection()
        col.add_int(key, 42)
        self.assertEqual(col.keys(), [key])
        self.assertEqual(col.get_int(key), 42)
        restored: FonCollection = roundtrip_line(col)
        self.assertEqual(restored.keys(), [key])
        self.assertEqual(restored.get_int(key), 42)

    def test_value_ending_with_backslash(self) -> None:
        value: str = "C:\\dir\\"
        col = FonCollection()
        col.add_string("path", value)
        self.assertEqual(roundtrip_line(col).get_string("path"), value)

    def test_backslash_before_quote_in_array_item(self) -> None:
        items: List[str] = ["a\\", "\\", "b\\\\"]
        col = FonCollection()
        col.add_string_array("v", items)
        self.assertEqual(roundtrip_line(col).get_string_array("v"), items)

    def test_control_characters_round_trip(self) -> None:
        value: str = "\x01\x1b\t\n\r\x08\x0c"
        col = FonCollection()
        col.add_string("v", value)
        self.assertEqual(roundtrip_line(col).get_string("v"), value)

    def test_quotes_commas_brackets_and_braces_inside_strings(self) -> None:
        value: str = 'a"b,c]d}e{f[g],h"'
        col = FonCollection()
        col.add_string("v", value)
        self.assertEqual(roundtrip_line(col).get_string("v"), value)

    def test_special_characters_inside_nested_objects(self) -> None:
        value: str = 'x"y,z]{w}\\'
        inner = FonCollection()
        inner.add_string("text", value)
        inner.add_string_array("list", [value, "]"])
        outer = FonCollection()
        outer.add_collection("inner", inner)
        restored: FonCollection = roundtrip_line(outer)
        nested: FonCollection = restored.get_collection("inner")
        self.assertEqual(nested.get_string("text"), value)
        self.assertEqual(nested.get_string_array("list"), [value, "]"])


class TestGetStringSignature(unittest.TestCase):
    def test_buffer_size_default_does_not_suggest_a_limit(self) -> None:
        parameter: inspect.Parameter = inspect.signature(FonCollection.get_string).parameters["buffer_size"]
        self.assertIsNone(parameter.default)


if __name__ == "__main__":
    unittest.main()
