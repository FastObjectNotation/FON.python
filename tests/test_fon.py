"""
Tests for the fon package (Fast Object Notation).

Run with:  python -m unittest discover -s tests
       or: python -m unittest tests.test_fon
"""

import unittest

from fon import FonCollection, FonDump, FonError, native_version


class TestNativeVersion(unittest.TestCase):
    def test_version(self) -> None:
        """native_version() must match the library version."""
        self.assertEqual(native_version(), "0.3.0")


class TestFonCollectionPrimitives(unittest.TestCase):
    """Round-trip each primitive type through a FonCollection."""

    def test_add_get_int(self) -> None:
        col = FonCollection()
        col.add_int("x", 42)
        self.assertEqual(col.get_int("x"), 42)

    def test_add_get_negative_int(self) -> None:
        col = FonCollection()
        col.add_int("n", -1)
        self.assertEqual(col.get_int("n"), -1)

    def test_add_get_long(self) -> None:
        col = FonCollection()
        col.add_long("ts", 1_700_000_000_000)
        self.assertEqual(col.get_long("ts"), 1_700_000_000_000)

    def test_add_get_double(self) -> None:
        col = FonCollection()
        col.add_double("price", 99.99)
        self.assertAlmostEqual(col.get_double("price"), 99.99, places=10)

    def test_add_get_float(self) -> None:
        col = FonCollection()
        col.add_float("ratio", 3.14)
        self.assertAlmostEqual(col.get_float("ratio"), 3.14, places=5)

    def test_add_get_bool_true(self) -> None:
        col = FonCollection()
        col.add_bool("active", True)
        self.assertTrue(col.get_bool("active"))

    def test_add_get_bool_false(self) -> None:
        col = FonCollection()
        col.add_bool("active", False)
        self.assertFalse(col.get_bool("active"))

    def test_add_get_string(self) -> None:
        col = FonCollection()
        col.add_string("name", "Widget Pro")
        self.assertEqual(col.get_string("name"), "Widget Pro")

    def test_collection_size(self) -> None:
        col = FonCollection()
        self.assertEqual(len(col), 0)
        col.add_int("a", 1)
        self.assertEqual(len(col), 1)
        col.add_string("b", "hi")
        self.assertEqual(len(col), 2)

    def test_get_wrong_type_raises(self) -> None:
        col = FonCollection()
        col.add_string("name", "hello")
        with self.assertRaises(FonError):
            col.get_int("name")

    def test_get_missing_key_raises(self) -> None:
        col = FonCollection()
        with self.assertRaises(FonError):
            col.get_int("nosuchkey")


class TestFonCollectionSerialization(unittest.TestCase):
    """serialize() / FonCollection.deserialize() round-trip."""

    def test_serialize_produces_string(self) -> None:
        col = FonCollection()
        col.add_int("id", 7)
        line = col.serialize()
        self.assertIsInstance(line, str)
        self.assertIn("id", line)

    def test_roundtrip_collection(self) -> None:
        col = FonCollection()
        col.add_int("id", 101)
        col.add_string("name", "Gadget")
        col.add_double("price", 29.95)

        line = col.serialize()
        restored = FonCollection.deserialize(line)

        self.assertEqual(restored.get_int("id"), 101)
        self.assertEqual(restored.get_string("name"), "Gadget")
        self.assertAlmostEqual(restored.get_double("price"), 29.95, places=10)


class TestFonDump(unittest.TestCase):
    """FonDump add / get / size."""

    def test_dump_size_empty(self) -> None:
        dump = FonDump()
        self.assertEqual(len(dump), 0)

    def test_dump_add_and_size(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_int("x", 1)
        dump.add(0, col)
        self.assertEqual(len(dump), 1)

    def test_dump_get_returns_collection(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_string("name", "Alpha")
        dump.add(0, col)

        fetched = dump.get(0)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.get_string("name"), "Alpha")

    def test_dump_get_missing_returns_none(self) -> None:
        dump = FonDump()
        self.assertIsNone(dump.get(999))

    def test_transferred_collection_raises(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_int("v", 5)
        dump.add(0, col)
        with self.assertRaises(RuntimeError):
            col.add_int("v2", 6)


class TestDumpSerializationRoundtrip(unittest.TestCase):
    """
    Primary integration test: build a collection with id/name/price,
    add to a dump, serialize to string, deserialize back, assert values.
    """

    def test_full_roundtrip(self) -> None:
        # Build
        col = FonCollection()
        col.add_int("id", 42)
        col.add_string("name", "Test Item")
        col.add_double("price", 9.99)

        dump = FonDump()
        dump.add(0, col)

        # Serialize
        text = dump.serialize()
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 0)

        # Deserialize
        restored_dump = FonDump.deserialize(text)
        self.assertEqual(len(restored_dump), 1)

        entry = restored_dump.get(0)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get_int("id"), 42)
        self.assertEqual(entry.get_string("name"), "Test Item")
        self.assertAlmostEqual(entry.get_double("price"), 9.99, places=10)

    def test_multi_entry_dump_roundtrip(self) -> None:
        dump = FonDump()
        for i in range(5):
            col = FonCollection()
            col.add_int("index", i)
            col.add_string("label", f"row_{i}")
            dump.add(i, col)

        text = dump.serialize()
        restored = FonDump.deserialize(text)
        self.assertEqual(len(restored), 5)

        for i in range(5):
            entry = restored.get(i)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.get_int("index"), i)
            self.assertEqual(entry.get_string("label"), f"row_{i}")

    def test_boolean_roundtrip(self) -> None:
        col = FonCollection()
        col.add_bool("flag", True)
        line = col.serialize()
        restored = FonCollection.deserialize(line)
        self.assertTrue(restored.get_bool("flag"))

    def test_long_roundtrip(self) -> None:
        col = FonCollection()
        col.add_long("ts", 9_999_999_999_999)
        line = col.serialize()
        restored = FonCollection.deserialize(line)
        self.assertEqual(restored.get_long("ts"), 9_999_999_999_999)


if __name__ == "__main__":
    unittest.main()
