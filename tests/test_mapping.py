"""
Mapping protocol and inference on FonCollection and FonDump.
"""

import unittest

from fon import FonCollection, FonDump, FonKind, NotFoundError


class TestCollectionMapping(unittest.TestCase):
    def test_inference_of_scalar_kinds(self) -> None:
        col = FonCollection()
        col["flag"] = True
        col["count"] = 7
        col["ratio"] = 0.5
        col["name"] = "text"
        col["blob"] = b"\x00\x01"
        self.assertEqual(col.kind("flag"), FonKind("bool", False))
        self.assertEqual(col.kind("count"), FonKind("long", False))
        self.assertEqual(col.kind("ratio"), FonKind("double", False))
        self.assertEqual(col.kind("name"), FonKind("string", False))
        self.assertEqual(col.kind("blob"), FonKind("raw", False))
        self.assertTrue(col.get_bool("flag"))
        self.assertEqual(col.get_long("count"), 7)
        self.assertEqual(col.get_double("ratio"), 0.5)
        self.assertEqual(col.get_string("name"), "text")
        self.assertEqual(col.get_raw("blob"), b"\x00\x01")

    def test_inference_of_list_kinds(self) -> None:
        col = FonCollection()
        col["bools"] = [True, False]
        col["ints"] = [1, 2, 3]
        col["floats"] = [1.5, 2.5]
        col["mixed_numbers"] = [1, 2.5]
        col["strings"] = ["a", "b"]
        col["children"] = [FonCollection(), FonCollection()]
        self.assertEqual(col.kind("bools"), FonKind("bool", True))
        self.assertEqual(col.kind("ints"), FonKind("long", True))
        self.assertEqual(col.kind("floats"), FonKind("double", True))
        self.assertEqual(col.kind("mixed_numbers"), FonKind("double", True))
        self.assertEqual(col.kind("strings"), FonKind("string", True))
        self.assertEqual(col.kind("children"), FonKind("object", True))
        self.assertEqual(col.get_double_array("mixed_numbers"), [1.0, 2.5])

    def test_empty_list_is_type_error(self) -> None:
        col = FonCollection()
        with self.assertRaises(TypeError):
            col["empty"] = []

    def test_mixed_list_is_type_error(self) -> None:
        col = FonCollection()
        with self.assertRaises(TypeError):
            col["mixed"] = [1, "two"]
        with self.assertRaises(TypeError):
            col["bool_and_int"] = [True, 2]

    def test_unsupported_value_is_type_error(self) -> None:
        col = FonCollection()
        with self.assertRaises(TypeError):
            col["none"] = None

    def test_getitem_missing_key_raises_key_error(self) -> None:
        col = FonCollection()
        with self.assertRaises(KeyError):
            col["missing"]
        with self.assertRaises(NotFoundError):
            col.get("missing")

    def test_getitem_returns_nested_view(self) -> None:
        col = FonCollection()
        child = FonCollection()
        child.add_int("x", 3)
        col["child"] = child
        self.assertEqual(col["child"].get_int("x"), 3)

    def test_delitem_contains_len_and_iteration(self) -> None:
        col = FonCollection()
        col["a"] = 1
        col["b"] = 2
        self.assertEqual(len(col), 2)
        self.assertIn("a", col)
        self.assertNotIn("zz", col)
        self.assertEqual(list(col), ["a", "b"])
        del col["a"]
        self.assertNotIn("a", col)
        self.assertEqual(len(col), 1)
        with self.assertRaises(KeyError):
            del col["a"]

    def test_context_manager_closes_owned_collection(self) -> None:
        with FonCollection() as col:
            col.add_int("x", 1)
        with self.assertRaises(RuntimeError):
            col.get_int("x")

    def test_close_is_idempotent(self) -> None:
        col = FonCollection()
        col.close()
        col.close()
        with self.assertRaises(RuntimeError):
            len(col)


class TestDumpMapping(unittest.TestCase):
    def make_record(self, value: int) -> FonCollection:
        col = FonCollection()
        col.add_long("v", value)
        return col

    def test_setitem_getitem_contains_len_and_delitem(self) -> None:
        dump = FonDump()
        dump[5] = self.make_record(50)
        dump[5] = self.make_record(55)
        self.assertEqual(len(dump), 1)
        self.assertIn(5, dump)
        self.assertNotIn(6, dump)
        self.assertEqual(dump[5].get_long("v"), 55)
        del dump[5]
        self.assertNotIn(5, dump)
        with self.assertRaises(KeyError):
            dump[5]
        with self.assertRaises(KeyError):
            del dump[5]

    def test_items_and_iteration_yield_ids_and_views(self) -> None:
        dump = FonDump()
        dump.add(9, self.make_record(9))
        dump.add(3, self.make_record(3))
        self.assertEqual(list(dump), [3, 9])
        self.assertEqual([(record_id, view.get_long("v")) for record_id, view in dump.items()], [(3, 3), (9, 9)])

    def test_has_and_remove_many_with_out_of_range_ids(self) -> None:
        dump = FonDump()
        dump.add(1, self.make_record(1))
        self.assertFalse(dump.has(-1))
        self.assertIsNone(dump.get(2 ** 64))
        self.assertFalse(dump.remove(-1))

    def test_context_manager_closes_dump(self) -> None:
        with FonDump() as dump:
            dump.add(0, self.make_record(0))
        with self.assertRaises(RuntimeError):
            len(dump)


if __name__ == "__main__":
    unittest.main()
