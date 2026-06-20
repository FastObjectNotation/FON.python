"""
Extended tests covering the new C-ABI surface added in the second binding pass.

Run with:  python -m unittest discover -s tests
       or: python -m unittest tests.test_fon_extended
"""

import os
import tempfile
import unittest

import fon
from fon import FonCollection, FonDump, FonError, deserialize_dump_from_file


class TestConfigFunctions(unittest.TestCase):
    """set_raw_unpack / set_max_depth must not raise."""

    def test_set_raw_unpack_true(self) -> None:
        fon.set_raw_unpack(True)
        fon.set_raw_unpack(False)  # restore

    def test_set_max_depth(self) -> None:
        fon.set_max_depth(32)
        fon.set_max_depth(64)  # restore to default


class TestIntArrayRoundtrip(unittest.TestCase):
    """add_int_array / get_int_array."""

    def test_basic_roundtrip(self) -> None:
        col = FonCollection()
        values = [1, -2, 300, 0, 2147483647]
        col.add_int_array("nums", values)
        result = col.get_int_array("nums")
        self.assertEqual(result, values)

    def test_empty_array(self) -> None:
        col = FonCollection()
        col.add_int_array("empty", [])
        result = col.get_int_array("empty")
        self.assertEqual(result, [])

    def test_serialize_deserialize(self) -> None:
        col = FonCollection()
        col.add_int_array("ids", [10, 20, 30])
        line = col.serialize()
        restored = FonCollection.deserialize(line)
        self.assertEqual(restored.get_int_array("ids"), [10, 20, 30])

    def test_wrong_type_raises(self) -> None:
        col = FonCollection()
        col.add_int("scalar", 5)
        with self.assertRaises(FonError):
            col.get_int_array("scalar")


class TestFloatArrayRoundtrip(unittest.TestCase):
    """add_float_array / get_float_array."""

    def test_basic_roundtrip(self) -> None:
        col = FonCollection()
        values = [1.5, -2.25, 3.0]
        col.add_float_array("fs", values)
        result = col.get_float_array("fs")
        self.assertEqual(len(result), 3)
        for got, want in zip(result, values):
            self.assertAlmostEqual(got, want, places=5)

    def test_empty_array(self) -> None:
        col = FonCollection()
        col.add_float_array("empty", [])
        result = col.get_float_array("empty")
        self.assertEqual(result, [])

    def test_serialize_deserialize(self) -> None:
        col = FonCollection()
        col.add_float_array("prices", [9.99, 4.5, 0.01])
        line = col.serialize()
        restored = FonCollection.deserialize(line)
        result = restored.get_float_array("prices")
        self.assertEqual(len(result), 3)
        for got, want in zip(result, [9.99, 4.5, 0.01]):
            self.assertAlmostEqual(got, want, places=4)


class TestNestedCollectionRoundtrip(unittest.TestCase):
    """add_collection / get_collection — object inside object."""

    def test_basic_nested(self) -> None:
        inner = FonCollection()
        inner.add_int("x", 7)
        inner.add_string("label", "inner")

        outer = FonCollection()
        outer.add_collection("nested", inner)

        # inner must now be marked transferred
        self.assertTrue(inner._transferred)

        retrieved = outer.get_collection("nested")
        self.assertFalse(retrieved._owns)
        self.assertEqual(retrieved.get_int("x"), 7)
        self.assertEqual(retrieved.get_string("label"), "inner")

    def test_nested_serialize_deserialize(self) -> None:
        inner = FonCollection()
        inner.add_int("qty", 5)
        inner.add_double("price", 2.50)

        outer = FonCollection()
        outer.add_string("type", "order")
        outer.add_collection("item", inner)

        line = outer.serialize()
        restored = FonCollection.deserialize(line)

        self.assertEqual(restored.get_string("type"), "order")
        item = restored.get_collection("item")
        self.assertEqual(item.get_int("qty"), 5)
        self.assertAlmostEqual(item.get_double("price"), 2.50, places=10)

    def test_transferred_child_raises_on_use(self) -> None:
        child = FonCollection()
        child.add_int("v", 1)
        parent = FonCollection()
        parent.add_collection("c", child)
        with self.assertRaises(RuntimeError):
            child.add_int("v2", 2)

    def test_get_collection_missing_key_raises(self) -> None:
        col = FonCollection()
        with self.assertRaises(FonError):
            col.get_collection("nosuchkey")


class TestCollectionArrayRoundtrip(unittest.TestCase):
    """add_collection_array / get_collection_array — array of objects."""

    def _make_item(self, qty: int) -> FonCollection:
        c = FonCollection()
        c.add_int("qty", qty)
        return c

    def test_basic_roundtrip(self) -> None:
        items = [self._make_item(5), self._make_item(3)]
        parent = FonCollection()
        parent.add_collection_array("items", items)

        # Children must be transferred.
        for item in items:
            self.assertTrue(item._transferred)

        retrieved = parent.get_collection_array("items")
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0].get_int("qty"), 5)
        self.assertEqual(retrieved[1].get_int("qty"), 3)

    def test_serialize_deserialize(self) -> None:
        items = [self._make_item(10), self._make_item(20), self._make_item(30)]
        parent = FonCollection()
        parent.add_collection_array("rows", items)

        line = parent.serialize()
        restored = FonCollection.deserialize(line)

        rows = restored.get_collection_array("rows")
        self.assertEqual(len(rows), 3)
        for row, expected_qty in zip(rows, [10, 20, 30]):
            self.assertEqual(row.get_int("qty"), expected_qty)

    def test_empty_array(self) -> None:
        parent = FonCollection()
        parent.add_collection_array("items", [])
        result = parent.get_collection_array("items")
        self.assertEqual(result, [])


class TestFileRoundtrip(unittest.TestCase):
    """serialize_to_file / deserialize_dump_from_file."""

    def test_full_file_roundtrip(self) -> None:
        # Build a dump with two entries.
        dump = FonDump()

        col0 = FonCollection()
        col0.add_int("id", 1)
        col0.add_string("name", "Alpha")
        col0.add_double("score", 99.5)
        dump.add(0, col0)

        col1 = FonCollection()
        col1.add_int("id", 2)
        col1.add_string("name", "Beta")
        col1.add_bool("active", True)
        col1.add_int_array("tags", [10, 20, 30])
        dump.add(1, col1)

        with tempfile.NamedTemporaryFile(suffix=".fon", delete=False) as tf:
            tmp_path = tf.name

        try:
            dump.serialize_to_file(tmp_path)
            self.assertTrue(os.path.isfile(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 0)

            restored = deserialize_dump_from_file(tmp_path)
            self.assertEqual(len(restored), 2)

            entry0 = restored.get(0)
            self.assertIsNotNone(entry0)
            self.assertEqual(entry0.get_int("id"), 1)
            self.assertEqual(entry0.get_string("name"), "Alpha")
            self.assertAlmostEqual(entry0.get_double("score"), 99.5, places=10)

            entry1 = restored.get(1)
            self.assertIsNotNone(entry1)
            self.assertEqual(entry1.get_int("id"), 2)
            self.assertEqual(entry1.get_string("name"), "Beta")
            self.assertTrue(entry1.get_bool("active"))
            self.assertEqual(entry1.get_int_array("tags"), [10, 20, 30])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_deserialize_nonexistent_file_raises(self) -> None:
        with self.assertRaises(FonError):
            deserialize_dump_from_file("nonexistent_file_12345.fon")


if __name__ == "__main__":
    unittest.main()
