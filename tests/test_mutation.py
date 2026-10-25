"""
Mutation (design section 6, item 4).

add fails on an existing key or id, set is an upsert, replace requires an
existing id, remove reports whether something was removed, and serialization
after removal renumbers the records.
"""

import unittest

from fon import AlreadyExistsError, FonCollection, FonDump, NotFoundError


class TestCollectionMutation(unittest.TestCase):
    def test_add_existing_key_raises_already_exists(self) -> None:
        col = FonCollection()
        col.add_int("k", 1)
        with self.assertRaises(AlreadyExistsError):
            col.add_int("k", 2)
        self.assertEqual(col.get_int("k"), 1)

    def test_add_existing_key_of_other_type_raises(self) -> None:
        col = FonCollection()
        col.add_string("k", "x")
        with self.assertRaises(AlreadyExistsError):
            col.add_long("k", 2)

    def test_set_is_upsert_and_may_change_type(self) -> None:
        col = FonCollection()
        col.set_int("k", 1)
        col.set_int("k", 2)
        self.assertEqual(col.get_int("k"), 2)
        col.set_string("k", "now a string")
        self.assertEqual(col.get_string("k"), "now a string")
        self.assertEqual(col.kind("k").type, "string")

    def test_indexer_assignment_is_upsert(self) -> None:
        col = FonCollection()
        col["k"] = 1
        col["k"] = 2
        self.assertEqual(col.get_long("k"), 2)

    def test_remove_returns_true_then_false(self) -> None:
        col = FonCollection()
        col.add_int("k", 1)
        self.assertTrue(col.remove("k"))
        self.assertFalse(col.remove("k"))
        self.assertFalse(col.has("k"))

    def test_remove_of_nested_value_drops_it(self) -> None:
        col = FonCollection()
        col.add_collection("c", FonCollection())
        self.assertTrue(col.remove("c"))
        self.assertFalse(col.has("c"))


class TestDumpMutation(unittest.TestCase):
    def make_record(self, value: int) -> FonCollection:
        col = FonCollection()
        col.add_long("v", value)
        return col

    def test_add_existing_id_raises_already_exists(self) -> None:
        dump = FonDump()
        dump.add(1, self.make_record(1))
        with self.assertRaises(AlreadyExistsError):
            dump.add(1, self.make_record(2))
        self.assertEqual(dump.get(1).get_long("v"), 1)

    def test_set_is_upsert(self) -> None:
        dump = FonDump()
        dump.set(1, self.make_record(1))
        dump.set(1, self.make_record(2))
        self.assertEqual(len(dump), 1)
        self.assertEqual(dump.get(1).get_long("v"), 2)

    def test_replace_absent_id_raises_not_found(self) -> None:
        dump = FonDump()
        with self.assertRaises(NotFoundError):
            dump.replace(5, self.make_record(1))
        self.assertEqual(len(dump), 0)

    def test_replace_existing_id(self) -> None:
        dump = FonDump()
        dump.add(5, self.make_record(1))
        dump.replace(5, self.make_record(9))
        self.assertEqual(dump.get(5).get_long("v"), 9)

    def test_remove_returns_true_then_false(self) -> None:
        dump = FonDump()
        dump.add(3, self.make_record(3))
        self.assertTrue(dump.remove(3))
        self.assertFalse(dump.remove(3))
        self.assertIsNone(dump.get(3))

    def test_remove_many_counts_only_live_distinct_ids(self) -> None:
        dump = FonDump()
        for record_id in range(5):
            dump.add(record_id, self.make_record(record_id))
        removed: int = dump.remove_many([1, 1, 3, 99, 100])
        self.assertEqual(removed, 2)
        self.assertEqual(dump.ids(), [0, 2, 4])

    def test_remove_many_empty_list(self) -> None:
        dump = FonDump()
        dump.add(0, self.make_record(0))
        self.assertEqual(dump.remove_many([]), 0)
        self.assertEqual(dump.ids(), [0])

    def test_other_ids_unchanged_after_remove(self) -> None:
        dump = FonDump()
        for record_id in range(4):
            dump.add(record_id, self.make_record(record_id * 100))
        dump.remove(2)
        self.assertEqual(dump.ids(), [0, 1, 3])
        self.assertEqual(dump.get(0).get_long("v"), 0)
        self.assertEqual(dump.get(1).get_long("v"), 100)
        self.assertEqual(dump.get(3).get_long("v"), 300)

    def test_serialize_after_remove_renumbers_lines(self) -> None:
        dump = FonDump()
        for record_id in range(3):
            dump.add(record_id, self.make_record(record_id * 10))
        dump.remove(1)
        restored: FonDump = FonDump.deserialize(dump.serialize())
        self.assertEqual(restored.ids(), [0, 1])
        self.assertEqual(restored.get(0).get_long("v"), 0)
        self.assertEqual(restored.get(1).get_long("v"), 20)


if __name__ == "__main__":
    unittest.main()
